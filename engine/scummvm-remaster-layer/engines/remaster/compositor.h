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

#ifndef ENGINES_REMASTER_COMPOSITOR_H
#define ENGINES_REMASTER_COMPOSITOR_H

#include "common/array.h"
#include "common/hashmap.h"
#include "common/rect.h"
#include "common/str.h"
#include "graphics/pixelformat.h"
#include "graphics/surface.h"

#include "engines/remaster/assetpack.h"

namespace Remaster {

/** HD font atlas (RFNT) */
struct FontAtlas {
	struct Glyph {
		uint16 ax, ay, w, h;
		int16 bx, by;
		uint16 adv;
	};
	bool ok = false;
	int scale = 3, line = 0, ascent = 0, outline = 0;
	Glyph g[256];
	Common::Array<byte> fill, stroke;	// coverage planes
	int aw = 0, ah = 0;

	bool load(const AssetPack &pack, const Common::String &name);
	/** width in original pixels of a string in the game code page */
	int width(const Common::String &s) const;
};

/**
 * Composes the true colour frame from the 8-bit back buffer of the engine.
 *
 * The game keeps running at its own resolution and palette. For every output
 * pixel the compositor takes, in order of preference:
 *  1. the remastered sprite frame that drew the pixel (id buffer filled by the
 *     engine's own blitters, so masks, clipping and scaling stay the engine's);
 *  2. the HD background, when the 8-bit pixel still is the background's;
 *  3. the frame upscaled with Scale2x/Scale3x on palette indices.
 * Palette fades and grayscale views are applied to HD pixels; other palette
 * effects fall back to (3) for the colours involved.
 * In classic mode it shows the original frame with sharp pixels.
 *
 * Games drawn for non-square pixels (e.g. 320x200 shown on a 4:3 monitor) can
 * be stretched vertically (setAspect): the frame is composed at the square
 * scale and its rows are resampled with an area filter to the final height.
 */
class Compositor {
public:
	Compositor(const AssetPack &pack, int scale, int screenW, int screenH, const Graphics::PixelFormat &fmt);
	~Compositor();

	int scale() const { return _scale; }
	int outputWidth() const { return (_screenW + _maxExtL + _maxExtR) * _scale; }
	int outputHeight() const { return _outH ? _outH : _screenH * _scale; }
	void setMaxExtension(int left, int right) { _maxExtL = left; _maxExtR = right; }
	/**
	 * Vertical stretch for games made for non-square pixels: the output is
	 * round(screenH * scale * pixelAspect) rows high (1.0: no stretch).
	 */
	void setAspect(float pixelAspect);
	bool stretched() const { return _outH != 0; }
	/** columns to add on each side for a 16:9 view (same count per side) */
	static int sideExtension(int screenW, int screenH, float pixelAspect);
	int extLeft() const { return _maxExtL; }

	void setClassic(bool c) { _classic = c; }
	bool classic() const { return _classic; }

	void setPalette(const byte *rgb, uint start, uint num);
	void setBackground(const Common::String &scene, const Graphics::Surface &bg8, const byte *rgb, int bgX, int bgY, bool widescreen);
	const WideInfo &wide() const { return _wide; }

	// sprites
	void beginScene(int bbW, int bbH);
	uint32 spriteSlot(const byte *pixels, int w, int h, int pitch, byte transparent);
	uint32 *ids() { return _ids; }
	int idPitch() const { return _idW; }
	void clearIds(const Common::Rect &r);

	// text drawn with HD fonts on top of the frame (cleared by beginScene)
	bool hasFont(int id) const { return id >= 0 && id < (int)_fonts.size() && _fonts[id].ok; }
	int loadFont(const Common::String &name);
	void addText(int font, int x, int y, const Common::String &s, byte colorIndex, byte outlineIndex, int boxW);

	/**
	 * Compose the frame. scrollX256 / scrollY are the camera position in the back buffer
	 * (X in 1/256 pixel for smooth scrolling). Returns the composed surface.
	 */
	const Graphics::Surface &compose(const Graphics::Surface &bb8, int scrollX256, int scrollY);

	/** Output (HD) coordinates -> engine screen coordinates. */
	Common::Point toGame(const Common::Point &p, int scrollX) const;
	/** Engine screen coordinates -> output (HD) coordinates (centre of the pixel; inverse of toGame) */
	Common::Point toScreen(const Common::Point &p) const;

private:
	enum Mode { kSame = 0, kFade = 1, kGray = 2, kLowRes = 3 };
	struct Sprite {
		Common::Array<uint32> px;	// ARGB at _scale
		int w = 0, h = 0;
		uint16 pal = 0;
		uint32 used[8];
	};
	struct Slot {
		const Sprite *spr;
		byte mode[256];
		uint16 factor[256];
	};
	struct Text {
		int font, x, y, boxW;
		Common::String s;
		byte color, outline;
	};

	const AssetPack &_pack;
	int _scale, _screenW, _screenH;
	int _maxExtL = 0, _maxExtR = 0;
	int _outH = 0;				// stretched output height (0: square pixels)
	Graphics::PixelFormat _fmt;
	bool _classic = false;

	Graphics::Surface _frame;	// composed at the square scale
	Graphics::Surface _out;		// _frame stretched vertically (only with setAspect)
	Graphics::Surface _hdBg;	// ARGB at _scale
	Graphics::Surface _origBg;	// 8-bit copy of the original background
	Graphics::Surface _wideBg;	// ARGB at _scale, scene + extensions
	WideInfo _wide;
	int _bgX = 0, _bgY = 0;

	byte _bgPal[768];
	byte _curPal[768];
	uint32 _palPixel[256];
	byte _mode[256];
	uint16 _factor[256];
	bool _modesDirty = true;
	byte _wideMode = 0;			// palette effect applied to the invented side areas
	uint16 _wideFactor = 256;
	int _lastViewLeft = 0, _lastSx = 0;

	Common::Array<byte> _scaled;	// scaled indices of the composed area
	int _scaledW = 0;

	uint32 *_ids = nullptr;
	int _idW = 0, _idH = 0;
	Common::Array<Slot> _slots;
	Common::HashMap<uint32, uint32> _slotOfKey;
	Common::HashMap<uint32, Sprite *> _sprCache;

	Common::Array<FontAtlas> _fonts;
	Common::Array<Text> _texts;

	void computeModes(const byte *ref, byte *mode, uint16 *factor) const;
	Sprite *loadSprite(uint32 key, const SpriteEntry &e);
	void scaleIndices(const Graphics::Surface &bb8, int x0, int y0, int w, int h);
	uint32 hdPixel(uint32 argb, byte mode, uint16 factor) const;
	void drawTexts(int originX);
	void drawText(const Text &t, int originX);
	void resampleTo(const Graphics::Surface &src, int srcScale, Graphics::Surface &dst) const;
	const Graphics::Surface &finish();
	void stretchRows(const Graphics::Surface &src, Graphics::Surface &dst) const;
};

} // End of namespace Remaster

#endif
