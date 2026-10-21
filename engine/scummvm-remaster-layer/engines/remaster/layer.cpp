/* ScummVM - Graphic Adventure Engine
 *
 * ScummVM is the legal property of its developers, whose names
 * are too numerous to list here. Please refer to the COPYRIGHT
 * file distributed with this source distribution.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

#include "audio/audiostream.h"
#include "common/config-manager.h"
#include "common/debug.h"
#include "common/file.h"
#include "common/fs.h"
#include "common/language.h"
#include "common/system.h"
#include "common/textconsole.h"
#include "common/translation.h"
#include "common/ustr.h"
#include "engines/util.h"
#include "graphics/cursorman.h"

#include "engines/remaster/layer.h"

namespace Remaster {

static bool confBool(const char *key, bool def) {
	return ConfMan.hasKey(key) ? ConfMan.getBool(key) : def;
}

Layer *Layer::create(const Desc &desc) {
	if (!confBool("remaster", true))
		return nullptr;
	AssetPack *pack = new AssetPack();
	if (!pack->open()) {
		delete pack;
		return nullptr;
	}
	int scale = ConfMan.hasKey("remaster_scale") ? ConfMan.getInt("remaster_scale") : pack->scale();
	scale = CLIP(scale, 2, 4);

	Graphics::PixelFormat fmt(4, 8, 8, 8, 8, 24, 16, 8, 0);
	Common::List<Graphics::PixelFormat> formats = g_system->getSupportedFormats();
	for (Common::List<Graphics::PixelFormat>::iterator it = formats.begin(); it != formats.end(); ++it) {
		if (it->bytesPerPixel == 4) {
			fmt = *it;
			break;
		}
	}
	Layer *l = new Layer(desc, pack, scale, fmt);
	initGraphics(l->_comp->outputWidth(), l->_comp->outputHeight(), &fmt);
	if (g_system->getScreenFormat() != fmt) {
		warning("Remaster: true colour not available, using the original graphics");
		delete l;
		return nullptr;
	}
	return l;
}

Layer::Layer(const Desc &desc, AssetPack *pack, int scale, const Graphics::PixelFormat &fmt) :
	_desc(desc), _pack(pack), _fmt(fmt) {
	_comp = new Compositor(*pack, scale, desc.screenW, desc.screenH, fmt);
	_widescreen = confBool("remaster_widescreen", true);
	_smooth = confBool("remaster_smooth", true);
	_voices = confBool("remaster_voices", true);
	_toggleKey = ConfMan.hasKey("remaster_toggle_key") ? CLIP(ConfMan.getInt("remaster_toggle_key"), 1, 12) : 8;
	memset(_pal, 0, sizeof(_pal));

	if (_widescreen) {
		// same number of pixels on each side, as in the pipeline tools (rstool widescreen geometry)
		float target = desc.screenH * desc.pixelAspect * 16.0f / 9.0f;
		float half = (target - desc.screenW) / 2.0f - 1e-4f;
		int side = (int)half;
		if (half > side)
			side++;
		side = MAX(0, side);
		_comp->setMaxExtension(side, side);
	}

	_lang = desc.language;
	if (_lang.empty() && ConfMan.hasKey("language"))
		_lang = Common::getLanguageCode(Common::parseLanguage(ConfMan.get("language")));
	if (ConfMan.hasKey("remaster_language"))
		_lang = ConfMan.get("remaster_language");
	if (!_lang.empty())
		_pack->loadTexts(_lang);
	_pack->setLanguage(_lang);

	if (ConfMan.hasKey("remaster_dump"))
		_dumpDir = ConfMan.get("remaster_dump");

	_comp->setClassic(confBool("remaster_classic", false));
	debug(1, "Remaster: %dx%d -> %dx%d (scale %d, widescreen %d, language %s)", desc.screenW, desc.screenH,
		_comp->outputWidth(), _comp->outputHeight(), scale, _widescreen, _lang.c_str());
}

Layer::~Layer() {
	stopVoice();
	if (_textDump) {
		_textDump->finalize();
		delete _textDump;
	}
	delete _comp;
	delete _pack;
}

void Layer::setClassic(bool c) {
	_comp->setClassic(c);
	ConfMan.setBool("remaster_classic", c, ConfMan.getActiveDomainName());
	if (_bb)
		show(_scrollTo << 8);
	if (c)
		stopVoice();
}

void Layer::toggle() {
	bool c = !classic();
	setClassic(c);
	ConfMan.flushToDisk();
	g_system->displayMessageOnOSD(c ? _("Original version") : _("Remastered version"));
}

// ---------------------------------------------------------------------------

void Layer::setPalette(const byte *rgb, uint start, uint num) {
	for (uint i = start; i < start + num && i < 256; i++)
		memcpy(&_pal[i * 3], &rgb[(i - start) * 3], 3);
	_comp->setPalette(rgb, start, num);
	// CLUT8 cursors keep following the game palette in true colour mode
	CursorMan.replaceCursorPalette(rgb, start, num);
}

void Layer::setBackground(const Common::String &scene, const Graphics::Surface &bg8, const byte *rgb, int bgX, int bgY) {
	_comp->setBackground(scene, bg8, rgb, bgX, bgY, _widescreen);
	if (!_dumpDir.empty() && bg8.getPixels() && !scene.empty()) {
		Common::String name = scene;
		for (uint i = 0; i < name.size(); i++)
			if (name[i] == '/' || name[i] == '\\')
				name.setChar('_', i);
		dumpRaw("bg/" + name + ".raw", (const byte *)bg8.getPixels(), bg8.w, bg8.h, bg8.pitch, 255, rgb);
	}
}

void Layer::beginScene(int bbW, int bbH) {
	_comp->beginScene(bbW, bbH);
	_ids = _comp->ids();
	_idW = _comp->idPitch();
	_idH = bbH;
	_slot = 0;
}

uint32 Layer::beginSprite(const byte *pixels, int w, int h, int pitch, byte transparent) {
	if (!_dumpDir.empty() && w > 0 && h > 0 && w < 1024 && h < 1024) {
		uint32 key = frameKey(pixels, w, h, pitch);
		if (!_dumped.contains(key)) {
			_dumped[key] = true;
			dumpRaw("spr/" + keyToString(key) + ".raw", pixels, w, h, pitch, transparent, _pal);
		}
	}
	_slot = _comp->spriteSlot(pixels, w, h, pitch, transparent);
	return _slot;
}

void Layer::clearArea(int x, int y, int w, int h) {
	_comp->clearIds(Common::Rect(x, y, x + w, y + h));
}

int Layer::font(const Common::String &name) {
	return _comp->loadFont(name);
}

bool Layer::addText(int f, int x, int y, const Common::String &s, byte color, byte outline, int boxW) {
	if (classic() || !_comp->hasFont(f))
		return false;
	_comp->addText(f, x, y, s, color, outline, boxW);
	return true;
}

// ---------------------------------------------------------------------------

void Layer::show(int scrollX256) {
	if (!_bb)
		return;
	const Graphics::Surface &out = _comp->compose(*_bb, scrollX256, _scrollY);
	g_system->copyRectToScreen(out.getPixels(), out.pitch, 0, 0, out.w, out.h);
	g_system->updateScreen();
}

void Layer::present(const Graphics::Surface &bb8, int scrollX, int scrollY) {
	_bb = &bb8;
	_scrollFrom = _scrollTo;
	_scrollTo = scrollX;
	_scrollY = scrollY;
	_tickStart = g_system->getMillis();
	// cuts (location change, big jumps) are never interpolated
	if (!_smooth || !_paced || classic() || ABS(_scrollTo - _scrollFrom) > _desc.screenW / 4)
		_scrollFrom = _scrollTo;
	show(_scrollFrom << 8);
}

void Layer::pace(uint32 tickMs) {
	_paced = true;
	const uint32 frameMs = 16;
	while (true) {
		uint32 now = g_system->getMillis();
		uint32 elapsed = now - _tickStart;
		if (elapsed + 2 >= tickMs)
			break;
		g_system->delayMillis(MIN<uint32>(frameMs, tickMs - elapsed - 1));
		if (_scrollFrom != _scrollTo && _bb) {
			uint32 e = MIN<uint32>(g_system->getMillis() - _tickStart, tickMs);
			int x256 = (_scrollFrom << 8) + (int)(((int64)(_scrollTo - _scrollFrom) * 256 * e) / tickMs);
			show(x256);
		}
	}
	if (_scrollFrom != _scrollTo && _bb) {
		_scrollFrom = _scrollTo;
		show(_scrollTo << 8);
	}
}

// ---------------------------------------------------------------------------

bool Layer::handleEvent(Common::Event &ev) {
	switch (ev.type) {
	case Common::EVENT_KEYDOWN:
		if (ev.kbd.keycode == (Common::KeyCode)(Common::KEYCODE_F1 + _toggleKey - 1)) {
			if (!ev.kbdRepeat)
				toggle();
			return true;
		}
		return false;
	case Common::EVENT_KEYUP:
		return ev.kbd.keycode == (Common::KeyCode)(Common::KEYCODE_F1 + _toggleKey - 1);
	case Common::EVENT_MOUSEMOVE:
	case Common::EVENT_LBUTTONDOWN:
	case Common::EVENT_LBUTTONUP:
	case Common::EVENT_RBUTTONDOWN:
	case Common::EVENT_RBUTTONUP:
	case Common::EVENT_MBUTTONDOWN:
	case Common::EVENT_MBUTTONUP:
	case Common::EVENT_WHEELUP:
	case Common::EVENT_WHEELDOWN:
		ev.mouse = _comp->toGame(ev.mouse, _scrollTo);
		return false;
	default:
		return false;
	}
}

// ---------------------------------------------------------------------------

Common::String Layer::text(const Common::String &original, const char *kind, const char *location, const char *speaker, int boxW) {
	if (!_dumpDir.empty())
		dumpText(original, kind, location, speaker, boxW);
	if (classic())
		return original;
	Common::String utf8;
	if (!_pack->text(textKey(original), utf8))
		return original;
	Common::U32String u(utf8.c_str(), Common::kUtf8);
	return u.encode(_desc.codePage);
}

bool Layer::playVoice(const Common::String &original) {
	if (!_voices || classic() || _lang.empty() || original.empty())
		return false;
	Common::String base = _pack->voicePath(textKey(original), _lang);
	if (base.empty())
		return false;
	Audio::SeekableAudioStream *stream = Audio::SeekableAudioStream::openStreamFile(Common::Path(base, '/'));
	if (!stream)
		return false;
	g_system->getMixer()->stopHandle(_voice);
	g_system->getMixer()->playStream(Audio::Mixer::kSpeechSoundType, &_voice, stream);
	return true;
}

void Layer::stopVoice() {
	g_system->getMixer()->stopHandle(_voice);
}

bool Layer::isVoicePlaying() const {
	return g_system->getMixer()->isSoundHandleActive(_voice);
}

// ---------------------------------------------------------------------------

void Layer::dumpRaw(const Common::String &file, const byte *pixels, int w, int h, int pitch, byte transparent, const byte *pal) {
	Common::DumpFile out;
	Common::Path path(_dumpDir + "/" + file, '/');
	if (!out.open(path, true)) {
		warning("Remaster: can't write %s", file.c_str());
		return;
	}
	out.writeUint16LE(w);
	out.writeUint16LE(h);
	out.writeByte(transparent);
	out.write(pal, 768);
	for (int y = 0; y < h; y++)
		out.write(pixels + y * pitch, w);
	out.finalize();
}

void Layer::dumpText(const Common::String &original, const char *kind, const char *location, const char *speaker, int boxW) {
	uint32 key = textKey(original) ^ 0x5bd1e995;
	if (original.empty() || _dumped.contains(key))
		return;
	_dumped[key] = true;
	Common::String hex;
	for (uint i = 0; i < original.size(); i++)
		hex += Common::String::format("%02x", (byte)original[i]);
	if (!_textDump) {
		_textDump = new Common::DumpFile();
		if (!_textDump->open(Common::Path(_dumpDir + "/text.jsonl", '/'), true)) {
			delete _textDump;
			_textDump = nullptr;
			return;
		}
	}
	_textDump->writeString(Common::String::format("{\"hex\": \"%s\", \"kind\": \"%s\", \"location\": \"%s\", \"speaker\": \"%s\", \"box_w\": %d}\n",
		hex.c_str(), kind, location, speaker, boxW));
	_textDump->flush();
}

} // End of namespace Remaster
