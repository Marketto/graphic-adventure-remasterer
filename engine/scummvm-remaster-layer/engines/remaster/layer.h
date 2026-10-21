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

#ifndef ENGINES_REMASTER_LAYER_H
#define ENGINES_REMASTER_LAYER_H

#include "audio/mixer.h"
#include "common/events.h"
#include "common/file.h"
#include "common/hashmap.h"
#include "common/str-enc.h"
#include "common/str.h"
#include "graphics/surface.h"

#include "engines/remaster/assetpack.h"
#include "engines/remaster/compositor.h"
#include "engines/remaster/keys.h"

namespace Remaster {

/**
 * Remaster Layer: HD graphics, 16:9, smooth scrolling, corrected/translated
 * texts and recorded voices for 8-bit adventure engines, switchable to the
 * original at any moment (F8 by default).
 *
 * Integration (see engine/scummvm-remaster-layer/INTEGRAZIONE.md):
 *   init     Layer *l = Layer::create(desc); if (!l) initGraphics(w, h);
 *   scene    l->setBackground(name, bg8, rgb, x, y);
 *   palette  l->setPalette(rgb, start, n) instead of the PaletteManager
 *   frame    l->beginScene(bbW, bbH); blitters: slot = l->beginSprite(...); l->mark(...)
 *   texts    if (!l->addText(font, x, y, s, color, outline, boxW)) <draw as before>
 *   show     l->present(bb8, scrollX, scrollY); l->pace(tickMs) instead of delayMillis
 *   input    for every polled event: if (l->handleEvent(ev)) continue;
 *   strings  s = l->text(original); l->playVoice(original)
 */
class Layer {
public:
	struct Desc {
		Common::String gameId;
		int screenW = 320, screenH = 200;
		float pixelAspect = 1.0f;			///< 1.0: square pixels (640x400 -> 36 px per side); 1.2 with 4:3 aspect correction
		Common::CodePage codePage = Common::kDos850;
		Common::String language;			///< "it", "en"... (empty: from the ScummVM settings)
	};

	/**
	 * Initializes the graphics mode when a remaster pack is installed and the
	 * remaster is enabled; returns nullptr otherwise (the engine then calls
	 * initGraphics() as usual).
	 */
	static Layer *create(const Desc &desc);
	~Layer();

	bool classic() const { return _comp->classic(); }
	void setClassic(bool c);
	void toggle();
	int scale() const { return _comp->scale(); }

	// --- graphics -------------------------------------------------------
	void setPalette(const byte *rgb, uint start, uint num);
	void setBackground(const Common::String &scene, const Graphics::Surface &bg8, const byte *rgb, int bgX = 0, int bgY = 0);
	void beginScene(int bbW, int bbH);
	/** call before blitting a sprite frame; returns its slot (0: drawn as original) */
	uint32 beginSprite(const byte *pixels, int w, int h, int pitch, byte transparent);
	/** call for every pixel the blitter writes: (x, y) in the back buffer, (sx, sy) in the frame */
	inline void mark(int x, int y, int sx, int sy) {
		if (_ids && x >= 0 && y >= 0 && x < _idW && y < _idH)
			_ids[y * _idW + x] = (_slot && sx < 1024 && sy < 1024) ? ((_slot << 20) | (sx << 10) | sy) : 0;
	}
	void endSprite() { _slot = 0; }
	/** the engine copied plain pixels over an area (no sprite): forget the sprite ids there */
	void clearArea(int x, int y, int w, int h);

	int font(const Common::String &name);
	/** true if drawn in HD (the engine must then skip its own rasterization) */
	bool addText(int font, int x, int y, const Common::String &s, byte color, byte outline = 0, int boxW = 0);

	void present(const Graphics::Surface &bb8, int scrollX, int scrollY);
	/** wait for the next logic tick, presenting interpolated frames meanwhile */
	void pace(uint32 tickMs);

	// --- input ----------------------------------------------------------
	/** toggle key and mouse remapping; true when the event was consumed */
	bool handleEvent(Common::Event &ev);

	// --- texts and voices -------------------------------------------------
	/** corrected or translated string in the game code page (original in classic mode) */
	Common::String text(const Common::String &original, const char *kind = "", const char *location = "", const char *speaker = "", int boxW = 0);
	bool playVoice(const Common::String &original);
	void stopVoice();
	bool isVoicePlaying() const;

private:
	Layer(const Desc &desc, AssetPack *pack, int scale, const Graphics::PixelFormat &fmt);

	Desc _desc;
	AssetPack *_pack;
	Compositor *_comp;
	Graphics::PixelFormat _fmt;
	bool _widescreen;
	bool _smooth;
	bool _voices;
	int _toggleKey;
	Common::String _lang;

	uint32 *_ids = nullptr;
	int _idW = 0, _idH = 0;
	uint32 _slot = 0;

	// smooth scrolling
	const Graphics::Surface *_bb = nullptr;
	int _scrollFrom = 0, _scrollTo = 0, _scrollY = 0;
	uint32 _tickStart = 0;
	bool _paced = false;
	void show(int scrollX256);

	Audio::SoundHandle _voice;

	// developer dump (remaster_dump=<folder>)
	Common::String _dumpDir;
	Common::HashMap<uint32, bool> _dumped;
	Common::DumpFile *_textDump = nullptr;
	byte _pal[768];
	void dumpRaw(const Common::String &file, const byte *pixels, int w, int h, int pitch, byte transparent, const byte *pal);
	void dumpText(const Common::String &original, const char *kind, const char *location, const char *speaker, int boxW);
};

} // End of namespace Remaster

#endif
