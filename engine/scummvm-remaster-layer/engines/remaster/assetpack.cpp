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

#include "common/archive.h"
#include "common/config-manager.h"
#include "common/debug.h"
#include "common/endian.h"
#include "common/formats/json.h"
#include "common/textconsole.h"
#include "image/jpeg.h"
#include "image/png.h"

#include "engines/remaster/assetpack.h"

namespace Remaster {

static const Graphics::PixelFormat kARGB(4, 8, 8, 8, 8, 16, 8, 0, 24);

AssetPack::AssetPack() : _open(false), _scale(3), _spriteScale(0) {
}

AssetPack::~AssetPack() {
	if (_open && SearchMan.hasArchive("remaster-pack"))
		SearchMan.remove("remaster-pack");
}

bool AssetPack::open() {
	_open = false;
	Common::FSNode gameDir(ConfMan.getPath("path"));
	if (!gameDir.exists())
		return false;
	Common::FSNode r = gameDir.getChild("remaster");
	if (!r.exists() || !r.isDirectory())
		return false;
	_root = r;
	_open = true;
	// low priority: the game's own files always win
	if (!SearchMan.hasArchive("remaster-pack"))
		SearchMan.addDirectory("remaster-pack", _root, -10, 4);
	loadManifest();
	loadSpriteIndex();
	debug(1, "Remaster: pack found, scale %d, %d sprites", _scale, _sprites.size());
	return true;
}

Common::FSNode AssetPack::node(const Common::String &relPath) const {
	Common::FSNode n = _root;
	Common::String rest = relPath;
	while (true) {
		int slash = rest.findFirstOf('/');
		if (slash < 0)
			break;
		n = n.getChild(rest.substr(0, slash));
		rest = rest.substr(slash + 1);
	}
	return n.getChild(rest);
}

bool AssetPack::exists(const Common::String &relPath) const {
	if (!_open)
		return false;
	Common::FSNode n = node(relPath);
	return n.exists() && !n.isDirectory();
}

Common::SeekableReadStream *AssetPack::openFile(const Common::String &relPath) const {
	if (!_open)
		return nullptr;
	Common::FSNode n = node(relPath);
	if (!n.exists() || n.isDirectory())
		return nullptr;
	return n.createReadStream();
}

void AssetPack::loadManifest() {
	Common::SeekableReadStream *s = openFile("manifest.json");
	if (!s)
		return;
	Common::String text = s->readString(0, s->size());
	delete s;
	Common::JSONValue *v = Common::JSON::parse(text);
	if (!v)
		return;
	if (v->isObject()) {
		const Common::JSONObject &o = v->asObject();
		if (o.contains("scale") && o["scale"]->isIntegerNumber())
			_scale = CLIP<int>((int)o["scale"]->asIntegerNumber(), 1, 6);
		if (o.contains("game") && o["game"]->isString())
			_gameId = o["game"]->asString();
	}
	delete v;
}

Graphics::Surface *AssetPack::loadImage(const Common::String &relPathNoExt) const {
	Image::PNGDecoder png;
	Image::JPEGDecoder jpeg;
	jpeg.setOutputPixelFormat(Graphics::PixelFormat(4, 8, 8, 8, 8, 24, 16, 8, 0));
	Image::ImageDecoder *dec = &png;
	Common::SeekableReadStream *s = openFile(relPathNoExt + ".png");
	if (!s) {
		s = openFile(relPathNoExt + ".jpg");
		dec = &jpeg;
	}
	if (!s)
		return nullptr;
	bool ok = dec->loadStream(*s);
	delete s;
	if (!ok || !dec->getSurface()) {
		warning("Remaster: can't decode %s", relPathNoExt.c_str());
		return nullptr;
	}
	const Graphics::Surface *src = dec->getSurface();
	return src->convertTo(kARGB, dec->getPalette().data(), dec->getPalette().size());
}

// scene keys may contain '/' (e.g. "part1/bg/room"): files are flat, '/' becomes '_'
static Common::String sceneFile(const Common::String &scene) {
	Common::String s = scene;
	for (uint i = 0; i < s.size(); i++)
		if (s[i] == '/' || s[i] == '\\')
			s.setChar('_', i);
	return "gfx/bg/" + s;
}

Graphics::Surface *AssetPack::loadBackground(const Common::String &scene, int origW, int origH, int &scale) const {
	Common::String base = sceneFile(scene);
	Graphics::Surface *s = loadImage(base);
	if (!s)
		return nullptr;
	if (origW <= 0 || origH <= 0 || s->w % origW || s->h % origH || s->w / origW != s->h / origH) {
		warning("Remaster: %s is %dx%d, not an integer multiple of %dx%d", scene.c_str(), s->w, s->h, origW, origH);
		s->free();
		delete s;
		return nullptr;
	}
	scale = s->w / origW;
	return s;
}

WideInfo AssetPack::wideInfo(const Common::String &scene) const {
	WideInfo wi;
	Common::SeekableReadStream *s = openFile(sceneFile(scene) + ".wide.json");
	if (!s)
		return wi;
	Common::String text = s->readString(0, s->size());
	delete s;
	Common::JSONValue *v = Common::JSON::parse(text);
	if (v && v->isObject()) {
		const Common::JSONObject &o = v->asObject();
		if (o.contains("left") && o["left"]->isIntegerNumber())
			wi.left = (int)o["left"]->asIntegerNumber();
		if (o.contains("right") && o["right"]->isIntegerNumber())
			wi.right = (int)o["right"]->asIntegerNumber();
		if (o.contains("camera") && o["camera"]->isString())
			wi.clampCamera = o["camera"]->asString() == "clamp";
		if (o.contains("pillarbox"))
			wi.pillarbox = true;
	}
	delete v;
	wi.hasImage = exists(sceneFile(scene) + ".wide.png") || exists(sceneFile(scene) + ".wide.jpg");
	return wi;
}

Graphics::Surface *AssetPack::loadWideBackground(const Common::String &scene) const {
	return loadImage(sceneFile(scene) + ".wide");
}

void AssetPack::loadSpriteIndex() {
	Common::SeekableReadStream *f = openFile("gfx/spr/index.dat");
	if (!f)
		return;
	uint32 tag = f->readUint32BE();
	if (tag != MKTAG('R', 'S', 'P', 'R')) {
		warning("Remaster: bad sprite index");
		delete f;
		return;
	}
	f->readUint16LE();	// version
	_spriteScale = f->readUint16LE();
	uint16 numPal = f->readUint16LE();
	_spritePalettes.resize(numPal * 768);
	if (numPal)
		f->read(&_spritePalettes[0], numPal * 768);
	uint32 n = f->readUint32LE();
	for (uint32 i = 0; i < n && !f->eos(); i++) {
		uint32 key = f->readUint32LE();
		SpriteEntry e;
		e.palette = f->readUint16LE();
		e.w = f->readUint16LE();
		e.h = f->readUint16LE();
		if (e.palette < numPal)
			_sprites[key] = e;
	}
	delete f;
}

const SpriteEntry *AssetPack::sprite(uint32 key) const {
	Common::HashMap<uint32, SpriteEntry>::const_iterator it = _sprites.find(key);
	return it == _sprites.end() ? nullptr : &it->_value;
}

const byte *AssetPack::spritePalette(uint16 index) const {
	if ((uint)(index + 1) * 768 > _spritePalettes.size())
		return nullptr;
	return &_spritePalettes[index * 768];
}

bool AssetPack::loadTexts(const Common::String &lang) {
	_texts.clear();
	Common::SeekableReadStream *f = openFile("text/" + lang + ".tsv");
	if (!f)
		return false;
	while (!f->eos() && !f->err()) {
		Common::String line = f->readLine();
		if (line.empty() || line[0] == '#' || line.size() < 10 || line[8] != '\t')
			continue;
		uint32 key = (uint32)strtoul(line.substr(0, 8).c_str(), nullptr, 16);
		_texts[key] = line.substr(9);
	}
	delete f;
	debug(1, "Remaster: %d texts for '%s'", _texts.size(), lang.c_str());
	return true;
}

bool AssetPack::text(uint32 key, Common::String &utf8) const {
	Common::HashMap<uint32, Common::String>::const_iterator it = _texts.find(key);
	if (it == _texts.end())
		return false;
	utf8 = it->_value;
	return true;
}

Common::String AssetPack::voicePath(uint32 key, const Common::String &lang) const {
	static const char *const exts[] = { ".ogg", ".flac", ".mp3", ".wav" };
	Common::String base = Common::String::format("voice/%s/%08x", lang.c_str(), key);
	for (int i = 0; i < ARRAYSIZE(exts); i++) {
		if (exists(base + exts[i]))
			return base;
	}
	return Common::String();
}

} // End of namespace Remaster
