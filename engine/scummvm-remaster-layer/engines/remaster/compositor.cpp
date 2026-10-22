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

#include "common/debug.h"
#include "common/endian.h"
#include "common/textconsole.h"
#include "common/util.h"

#include "engines/remaster/compositor.h"
#include "engines/remaster/keys.h"

namespace Remaster {

static const Graphics::PixelFormat kARGB(4, 8, 8, 8, 8, 16, 8, 0, 24);

// ---------------------------------------------------------------------------
// Fonts
// ---------------------------------------------------------------------------

bool FontAtlas::load(const AssetPack &pack, const Common::String &name) {
	ok = false;
	Common::SeekableReadStream *dat = pack.openFile("fonts/" + name + ".dat");
	if (!dat)
		return false;
	uint32 tag = dat->readUint32BE();
	if (tag != MKTAG('R', 'F', 'N', 'T')) {
		delete dat;
		return false;
	}
	dat->readUint16LE();	// version
	scale = MAX<int>(1, dat->readUint16LE());
	line = dat->readUint16LE();
	ascent = dat->readUint16LE();
	outline = dat->readUint16LE();
	for (int i = 0; i < 256; i++) {
		g[i].ax = dat->readUint16LE();
		g[i].ay = dat->readUint16LE();
		g[i].w = dat->readUint16LE();
		g[i].h = dat->readUint16LE();
		g[i].bx = dat->readSint16LE();
		g[i].by = dat->readSint16LE();
		g[i].adv = dat->readUint16LE();
	}
	bool err = dat->err();
	delete dat;
	if (err)
		return false;
	Graphics::Surface *img = pack.loadImage("fonts/" + name);
	if (!img)
		return false;
	aw = img->w;
	ah = img->h;
	fill.resize(aw * ah);
	stroke.resize(aw * ah);
	for (int y = 0; y < ah; y++) {
		const uint32 *p = (const uint32 *)img->getBasePtr(0, y);
		for (int x = 0; x < aw; x++) {
			fill[y * aw + x] = (p[x] >> 16) & 0xff;
			stroke[y * aw + x] = (p[x] >> 8) & 0xff;
		}
	}
	img->free();
	delete img;
	ok = true;
	return true;
}

int FontAtlas::width(const Common::String &s) const {
	int w = 0;
	for (uint i = 0; i < s.size(); i++)
		w += g[(byte)s[i]].adv;
	return (w + scale - 1) / scale;
}

// ---------------------------------------------------------------------------

Compositor::Compositor(const AssetPack &pack, int scale, int screenW, int screenH, const Graphics::PixelFormat &fmt) :
	_pack(pack), _scale(scale), _screenW(screenW), _screenH(screenH), _fmt(fmt) {
	memset(_bgPal, 0, sizeof(_bgPal));
	memset(_curPal, 0, sizeof(_curPal));
	memset(_palPixel, 0, sizeof(_palPixel));
	memset(_mode, kLowRes, sizeof(_mode));
	memset(_factor, 0, sizeof(_factor));
	_slots.resize(1);
}

Compositor::~Compositor() {
	_frame.free();
	_out.free();
	_hdBg.free();
	_origBg.free();
	_wideBg.free();
	delete[] _ids;
	for (Common::HashMap<uint32, Sprite *>::iterator it = _sprCache.begin(); it != _sprCache.end(); ++it)
		delete it->_value;
}

void Compositor::setPalette(const byte *rgb, uint start, uint num) {
	for (uint i = start; i < start + num && i < 256; i++) {
		_curPal[i * 3] = rgb[(i - start) * 3];
		_curPal[i * 3 + 1] = rgb[(i - start) * 3 + 1];
		_curPal[i * 3 + 2] = rgb[(i - start) * 3 + 2];
		_palPixel[i] = _fmt.RGBToColor(_curPal[i * 3], _curPal[i * 3 + 1], _curPal[i * 3 + 2]);
	}
	_modesDirty = true;
}

void Compositor::computeModes(const byte *ref, byte *mode, uint16 *factor) const {
	for (int i = 0; i < 256; i++) {
		int r0 = ref[i * 3], g0 = ref[i * 3 + 1], b0 = ref[i * 3 + 2];
		int r1 = _curPal[i * 3], g1 = _curPal[i * 3 + 1], b1 = _curPal[i * 3 + 2];
		if (r0 == r1 && g0 == g1 && b0 == b1) {
			mode[i] = kSame;
			continue;
		}
		int m0 = MAX(r0, MAX(g0, b0));
		if (m0 > 0) {
			int f = (MAX(r1, MAX(g1, b1)) * 256 + m0 / 2) / m0;
			if (f <= 256 && ABS(r0 * f / 256 - r1) <= 4 && ABS(g0 * f / 256 - g1) <= 4 && ABS(b0 * f / 256 - b1) <= 4) {
				mode[i] = kFade;	// palette fade: every component scaled alike
				factor[i] = f;
				continue;
			}
			if (r1 == g1 && g1 == b1) {
				mode[i] = kGray;	// grayscale view
				factor[i] = (r1 * 256 + m0 / 2) / m0;
				continue;
			}
		} else if (r1 == 0 && g1 == 0 && b1 == 0) {
			mode[i] = kSame;
			continue;
		}
		mode[i] = kLowRes;
	}
}

void Compositor::resampleTo(const Graphics::Surface &src, int srcScale, Graphics::Surface &dst) const {
	// area average (alpha weighted) from srcScale x to _scale x; src and dst are ARGB
	const int S = _scale;
	for (int y = 0; y < dst.h; y++) {
		int sy0 = y * srcScale, sy1 = (y + 1) * srcScale;
		uint32 *d = (uint32 *)dst.getBasePtr(0, y);
		for (int x = 0; x < dst.w; x++) {
			int sx0 = x * srcScale, sx1 = (x + 1) * srcScale;
			uint32 aa = 0, ar = 0, ag = 0, ab = 0, aw = 0;
			for (int yy = sy0 / S; yy * S < sy1 && yy < src.h; yy++) {
				int wy = MIN(sy1, (yy + 1) * S) - MAX(sy0, yy * S);
				const uint32 *sp = (const uint32 *)src.getBasePtr(0, yy);
				for (int xx = sx0 / S; xx * S < sx1 && xx < src.w; xx++) {
					int wx = MIN(sx1, (xx + 1) * S) - MAX(sx0, xx * S);
					uint32 c = sp[xx], a = c >> 24, wgt = wx * wy;
					aa += a * wgt;
					ar += ((c >> 16) & 0xff) * a * wgt;
					ag += ((c >> 8) & 0xff) * a * wgt;
					ab += (c & 0xff) * a * wgt;
					aw += wgt;
				}
			}
			d[x] = aa ? (((aa / aw) << 24) | ((ar / aa) << 16) | ((ag / aa) << 8) | (ab / aa)) : 0;
		}
	}
}

void Compositor::setBackground(const Common::String &scene, const Graphics::Surface &bg8, const byte *rgb, int bgX, int bgY, bool widescreen) {
	_hdBg.free();
	_origBg.free();
	_wideBg.free();
	_wide = WideInfo();
	_bgX = bgX;
	_bgY = bgY;
	memcpy(_bgPal, rgb, 768);
	_modesDirty = true;
	if (scene.empty() || !bg8.getPixels())
		return;

	int k = 0;
	Graphics::Surface *hd = _pack.loadBackground(scene, bg8.w, bg8.h, k);
	if (hd) {
		_origBg.copyFrom(bg8);
		_hdBg.create(bg8.w * _scale, bg8.h * _scale, kARGB);
		if (k == _scale)
			_hdBg.copyFrom(*hd);
		else
			resampleTo(*hd, k, _hdBg);
		hd->free();
		delete hd;
	}
	if (widescreen) {
		_wide = _pack.wideInfo(scene);
		if (_wide.hasImage) {
			Graphics::Surface *w = _pack.loadWideBackground(scene);
			int ww = bg8.w + _wide.left + _wide.right;
			if (w && w->h % bg8.h == 0 && w->w == ww * (w->h / bg8.h)) {
				int kw = w->h / bg8.h;
				_wideBg.create(ww * _scale, bg8.h * _scale, kARGB);
				if (kw == _scale)
					_wideBg.copyFrom(*w);
				else
					resampleTo(*w, kw, _wideBg);
			} else if (w) {
				warning("Remaster: %s.wide has an unexpected size", scene.c_str());
			}
			if (w) {
				w->free();
				delete w;
			}
		}
	}
}

// ---------------------------------------------------------------------------
// Sprites
// ---------------------------------------------------------------------------

void Compositor::beginScene(int bbW, int bbH) {
	_slots.resize(1);
	_slotOfKey.clear();
	_texts.clear();
	if (_idW != bbW || _idH != bbH) {
		delete[] _ids;
		_ids = new uint32[bbW * bbH];
		_idW = bbW;
		_idH = bbH;
	}
	memset(_ids, 0, bbW * bbH * sizeof(uint32));
}

void Compositor::clearIds(const Common::Rect &r) {
	if (!_ids)
		return;
	Common::Rect c(r);
	c.clip(Common::Rect(_idW, _idH));
	for (int y = c.top; y < c.bottom; y++)
		memset(_ids + y * _idW + c.left, 0, c.width() * sizeof(uint32));
}

Compositor::Sprite *Compositor::loadSprite(uint32 key, const SpriteEntry &e) {
	Common::String base = Common::String::format("gfx/spr/%08x", key);
	Graphics::Surface *img = _pack.loadImage(base);
	if (!img)
		return nullptr;
	Sprite *spr = nullptr;
	if (img->w % e.w == 0 && img->h % e.h == 0 && img->w / e.w == img->h / e.h) {
		int k = img->w / e.w;
		spr = new Sprite;
		spr->w = e.w;
		spr->h = e.h;
		spr->pal = e.palette;
		memset(spr->used, 0, sizeof(spr->used));
		Graphics::Surface dst;
		dst.create(e.w * _scale, e.h * _scale, kARGB);
		if (k == _scale)
			dst.copyFrom(*img);
		else
			resampleTo(*img, k, dst);
		spr->px.resize(dst.w * dst.h);
		for (int y = 0; y < dst.h; y++)
			memcpy(&spr->px[y * dst.w], dst.getBasePtr(0, y), dst.w * 4);
		dst.free();
	} else {
		warning("Remaster: sprite %08x is %dx%d, original %dx%d", key, img->w, img->h, e.w, e.h);
	}
	img->free();
	delete img;
	return spr;
}

uint32 Compositor::spriteSlot(const byte *pixels, int w, int h, int pitch, byte transparent) {
	if (!_ids || w <= 0 || h <= 0 || w >= 1024 || h >= 1024)
		return 0;
	uint32 key = frameKey(pixels, w, h, pitch);
	Common::HashMap<uint32, uint32>::iterator is = _slotOfKey.find(key);
	if (is != _slotOfKey.end())
		return is->_value;
	uint32 slot = 0;
	const SpriteEntry *e = _pack.sprite(key);
	if (e && e->w == w && e->h == h && _slots.size() < 4095) {
		Sprite *spr;
		Common::HashMap<uint32, Sprite *>::iterator ic = _sprCache.find(key);
		if (ic != _sprCache.end()) {
			spr = ic->_value;
		} else {
			spr = loadSprite(key, *e);
			_sprCache[key] = spr;	// failures are cached too
			if (spr) {
				for (int y = 0; y < h; y++)
					for (int x = 0; x < w; x++) {
						byte c = pixels[y * pitch + x];
						if (c != transparent)
							spr->used[c >> 5] |= 1u << (c & 31);
					}
			}
		}
		const byte *ref = spr ? _pack.spritePalette(spr->pal) : nullptr;
		if (spr && ref) {
			Slot sl;
			sl.spr = spr;
			computeModes(ref, sl.mode, sl.factor);
			bool ok = true;
			for (int i = 0; i < 256 && ok; i++)
				if ((spr->used[i >> 5] & (1u << (i & 31))) && sl.mode[i] == kLowRes)
					ok = false;	// a colour can't be mapped: keep the original frame
			if (ok) {
				_slots.push_back(sl);
				slot = _slots.size() - 1;
			}
		}
	}
	_slotOfKey[key] = slot;
	return slot;
}

// ---------------------------------------------------------------------------
// Text
// ---------------------------------------------------------------------------

int Compositor::loadFont(const Common::String &name) {
	FontAtlas f;
	if (!f.load(_pack, name))
		return -1;
	_fonts.push_back(f);
	return _fonts.size() - 1;
}

void Compositor::addText(int font, int x, int y, const Common::String &s, byte colorIndex, byte outlineIndex, int boxW) {
	if (!hasFont(font))
		return;
	Text t;
	t.font = font;
	t.x = x;
	t.y = y;
	t.s = s;
	t.color = colorIndex;
	t.outline = outlineIndex;
	t.boxW = boxW;
	_texts.push_back(t);
}

static inline uint32 blend(const Graphics::PixelFormat &fmt, uint32 dst, byte r, byte g, byte b, int a) {
	if (a <= 0)
		return dst;
	if (a >= 255)
		return fmt.RGBToColor(r, g, b);
	byte r0, g0, b0;
	fmt.colorToRGB(dst, r0, g0, b0);
	return fmt.RGBToColor((r * a + r0 * (255 - a)) / 255, (g * a + g0 * (255 - a)) / 255, (b * a + b0 * (255 - a)) / 255);
}

void Compositor::drawText(const Text &t, int originX) {
	const FontAtlas &f = _fonts[t.font];
	const int S = _scale;
	int textW = 0;
	for (uint i = 0; i < t.s.size(); i++)
		textW += f.g[(byte)t.s[i]].adv;
	int textWOut = textW * S / f.scale;
	int x0 = originX + t.x * S + (t.boxW > 0 ? (t.boxW * S - textWOut) / 2 : 0);
	int y0 = t.y * S;
	const byte *fc = &_curPal[t.color * 3];
	const byte *oc = &_curPal[t.outline * 3];
	int pen = 0;	// atlas units
	for (uint i = 0; i < t.s.size(); i++) {
		const FontAtlas::Glyph &g = f.g[(byte)t.s[i]];
		if (g.w && g.h) {
			int gx = x0 + (pen + g.bx) * S / f.scale;
			int gy = y0 + g.by * S / f.scale;
			int gw = g.w * S / f.scale, gh = g.h * S / f.scale;
			for (int yy = 0; yy < gh; yy++) {
				int oy = gy + yy;
				if (oy < 0 || oy >= _frame.h)
					continue;
				int ay = g.ay + yy * f.scale / S;
				for (int xx = 0; xx < gw; xx++) {
					int ox = gx + xx;
					if (ox < 0 || ox >= _frame.w)
						continue;
					int ax = g.ax + xx * f.scale / S;
					int cf = f.fill[ay * f.aw + ax], cs = f.stroke[ay * f.aw + ax];
					if (!cf && !cs)
						continue;
					if (_fmt.bytesPerPixel == 4) {
						uint32 *d = (uint32 *)_frame.getBasePtr(ox, oy);
						if (cs)
							*d = blend(_fmt, *d, oc[0], oc[1], oc[2], cs);
						*d = blend(_fmt, *d, fc[0], fc[1], fc[2], cf);
					} else {
						uint16 *d = (uint16 *)_frame.getBasePtr(ox, oy);
						uint32 v = *d;
						if (cs)
							v = blend(_fmt, v, oc[0], oc[1], oc[2], cs);
						*d = (uint16)blend(_fmt, v, fc[0], fc[1], fc[2], cf);
					}
				}
			}
		}
		pen += g.adv;
	}
}

void Compositor::drawTexts(int originX) {
	for (uint i = 0; i < _texts.size(); i++)
		drawText(_texts[i], originX);
}

// ---------------------------------------------------------------------------
// Composition
// ---------------------------------------------------------------------------

void Compositor::scaleIndices(const Graphics::Surface &bb, int x0, int y0, int w, int h) {
	const int S = _scale;
	_scaledW = w * S;
	_scaled.resize(_scaledW * h * S);
	for (int y = 0; y < h; y++) {
		int sy = y0 + y;
		const byte *row = (const byte *)bb.getBasePtr(0, sy);
		const byte *up = (const byte *)bb.getBasePtr(0, MAX(0, sy - 1));
		const byte *dn = (const byte *)bb.getBasePtr(0, MIN(bb.h - 1, sy + 1));
		byte *d0 = &_scaled[(y * S) * _scaledW];
		for (int x = 0; x < w; x++) {
			int sx = x0 + x;
			int xl = MAX(0, sx - 1), xr = MIN(bb.w - 1, sx + 1);
			byte E = row[sx], B = up[sx], D = row[xl], F = row[xr], H = dn[sx];
			byte *p = d0 + x * S;
			if (S == 2) {
				bool c = (B != H && D != F);
				p[0] = (c && D == B) ? D : E;
				p[1] = (c && B == F) ? F : E;
				p[_scaledW] = (c && D == H) ? D : E;
				p[_scaledW + 1] = (c && H == F) ? F : E;
			} else if (S == 3) {
				byte A = up[xl], C = up[xr], G = dn[xl], I = dn[xr];
				if (B != H && D != F) {
					p[0] = (D == B) ? D : E;
					p[1] = ((D == B && E != C) || (B == F && E != A)) ? B : E;
					p[2] = (B == F) ? F : E;
					p[_scaledW] = ((D == B && E != G) || (D == H && E != A)) ? D : E;
					p[_scaledW + 1] = E;
					p[_scaledW + 2] = ((B == F && E != I) || (H == F && E != C)) ? F : E;
					p[2 * _scaledW] = (D == H) ? D : E;
					p[2 * _scaledW + 1] = ((D == H && E != I) || (H == F && E != G)) ? H : E;
					p[2 * _scaledW + 2] = (H == F) ? F : E;
				} else {
					for (int j = 0; j < 3; j++)
						memset(p + j * _scaledW, E, 3);
				}
			} else {
				for (int j = 0; j < S; j++)
					memset(p + j * _scaledW, E, S);
			}
		}
	}
}

uint32 Compositor::hdPixel(uint32 argb, byte mode, uint16 factor) const {
	int r = (argb >> 16) & 0xff, g = (argb >> 8) & 0xff, b = argb & 0xff;
	if (mode == kFade) {
		r = (r * factor) >> 8;
		g = (g * factor) >> 8;
		b = (b * factor) >> 8;
	} else if (mode == kGray) {
		int v = MIN(255, (MAX(r, MAX(g, b)) * factor) >> 8);
		r = g = b = v;
	}
	return _fmt.RGBToColor(r, g, b);
}

const Graphics::Surface &Compositor::compose(const Graphics::Surface &bb, int scrollX256, int scrollY) {
	const int S = _scale;
	const int L = _maxExtL, R = _maxExtR;
	const int viewW = _screenW + L + R;
	if (_frame.w != viewW * S || _frame.h != _screenH * S) {
		_frame.free();
		_frame.create(viewW * S, _screenH * S, _fmt);
	}
	_frame.fillRect(Common::Rect(_frame.w, _frame.h), _fmt.RGBToColor(0, 0, 0));
	const int sx = scrollX256 >> 8;

	if (_classic) {
		// the original frame, sharp pixels, centred in 4:3
		for (int y = 0; y < _screenH && scrollY + y < bb.h; y++) {
			const byte *src = (const byte *)bb.getBasePtr(0, scrollY + y);
			for (int j = 0; j < S; j++) {
				for (int x = 0; x < _screenW && sx + x < bb.w; x++) {
					uint32 c = _palPixel[src[sx + x]];
					for (int i = 0; i < S; i++) {
						int ox = (L + x) * S + i;
						if (_fmt.bytesPerPixel == 4)
							*(uint32 *)_frame.getBasePtr(ox, y * S + j) = c;
						else
							*(uint16 *)_frame.getBasePtr(ox, y * S + j) = (uint16)c;
					}
				}
			}
		}
		return finish();
	}

	if (_modesDirty) {
		computeModes(_bgPal, _mode, _factor);
		_modesDirty = false;
		// the side areas have no palette: follow what most background colours do
		int n[4] = { 0, 0, 0, 0 };
		uint32 sum[4] = { 0, 0, 0, 0 };
		for (int i = 0; i < 256; i++) {
			n[_mode[i]]++;
			sum[_mode[i]] += _factor[i];
		}
		_wideMode = kSame;
		_wideFactor = 256;
		if (n[kFade] > n[kSame] && n[kFade] >= n[kGray]) {
			_wideMode = kFade;
			_wideFactor = sum[kFade] / n[kFade];
		} else if (n[kGray] > n[kSame]) {
			_wideMode = kGray;
			_wideFactor = sum[kGray] / n[kGray];
		}
		for (uint i = 1; i < _slots.size(); i++)
			computeModes(_pack.spritePalette(_slots[i].spr->pal), _slots[i].mode, _slots[i].factor);
	}

	// which back buffer column feeds each output column (-1: outside, use the wide picture)
	const int sub = ((scrollX256 & 255) * S) >> 8;
	int viewLeft;
	if (_wide.clampCamera)
		viewLeft = CLIP(sx - L, 0, MAX(0, bb.w - viewW));
	else
		viewLeft = sx - L;
	_lastViewLeft = viewLeft;
	_lastSx = sx;
	int colMin = bb.w, colMax = -1;
	for (int c = 0; c <= viewW; c++) {
		int col = viewLeft + c;
		if (col >= 0 && col < bb.w) {
			colMin = MIN(colMin, col);
			colMax = MAX(colMax, col);
		}
	}
	int rows = MIN(_screenH, bb.h - scrollY);
	if (colMax >= colMin && rows > 0)
		scaleIndices(bb, colMin, scrollY, colMax - colMin + 1, rows);

	const bool hasHD = _hdBg.getPixels() != nullptr;
	const bool hasWide = _wideBg.getPixels() != nullptr;
	const int hdW = hasHD ? _origBg.w : 0;

	for (int Y = 0; Y < rows * S; Y++) {
		const int y = Y / S, jy = Y % S;
		const int by = scrollY + y;
		const byte *bbRow = (const byte *)bb.getBasePtr(0, by);
		const int bgy = by - _bgY;
		const byte *ob = (hasHD && bgy >= 0 && bgy < _origBg.h) ? (const byte *)_origBg.getBasePtr(0, bgy) : nullptr;
		const uint32 *hdRow = ob ? (const uint32 *)_hdBg.getBasePtr(0, bgy * S + jy) : nullptr;
		const uint32 *idRow = (_ids && by < _idH) ? _ids + by * _idW : nullptr;
		for (int X = 0; X < _frame.w; X++) {
			const int hx = X + sub;
			const int c = hx / S, j = hx % S;
			const int col = viewLeft + c;
			uint32 out;
			if (col < 0 || col >= bb.w) {
				if (!hasWide)
					continue;	// black band
				int wx = (col - _bgX + _wide.left) * S + j;
				int wy = bgy * S + jy;
				if (wx < 0 || wx >= _wideBg.w || wy < 0 || wy >= _wideBg.h)
					continue;
				uint32 p = *(const uint32 *)_wideBg.getBasePtr(wx, wy);
				out = hdPixel(p, _wideMode, _wideFactor);
			} else {
				const byte idx = bbRow[col];
				const int bgx = col - _bgX;
				// 2. HD background / 3. upscaled frame
				if (ob && bgx >= 0 && bgx < hdW && ob[bgx] == idx && _mode[idx] != kLowRes)
					out = hdPixel(hdRow[bgx * S + j], _mode[idx], _factor[idx]);
				else
					out = _palPixel[_scaled[(y * S + jy) * _scaledW + (col - colMin) * S + j]];
				// 1. remastered sprite on top
				uint32 id = idRow ? idRow[col] : 0;
				if (id) {
					const Slot &sl = _slots[id >> 20];
					byte m = sl.mode[idx];
					if (m != kLowRes) {
						int ssx = (id >> 10) & 1023, ssy = id & 1023;
						uint32 p = sl.spr->px[(ssy * S + jy) * (sl.spr->w * S) + ssx * S + j];
						int a = p >> 24;
						if (a) {
							uint32 hp = hdPixel(p, m, sl.factor[idx]);
							if (a >= 255) {
								out = hp;
							} else {
								byte r, g, b;
								_fmt.colorToRGB(hp, r, g, b);
								out = blend(_fmt, out, r, g, b, a);
							}
						}
					}
				}
			}
			if (_fmt.bytesPerPixel == 4)
				*(uint32 *)_frame.getBasePtr(X, Y) = out;
			else
				*(uint16 *)_frame.getBasePtr(X, Y) = (uint16)out;
		}
	}
	drawTexts((sx - viewLeft) * S - sub);
	return finish();
}

void Compositor::setAspect(float pixelAspect) {
	int h = (int)(_screenH * _scale * pixelAspect + 0.5f);
	_outH = (h > 0 && h != _screenH * _scale) ? h : 0;
	if (!_outH)
		_out.free();
}

int Compositor::sideExtension(int screenW, int screenH, float pixelAspect) {
	// same number of pixels on each side, as in the pipeline tools (rstool widescreen geometry)
	float target = screenH * pixelAspect * 16.0f / 9.0f;
	float half = (target - screenW) / 2.0f - 1e-4f;
	int side = (int)half;
	if (half > side)
		side++;
	return MAX(0, side);
}

const Graphics::Surface &Compositor::finish() {
	if (!_outH)
		return _frame;
	if (_out.w != _frame.w || _out.h != _outH) {
		_out.free();
		_out.create(_frame.w, _outH, _fmt);
	}
	stretchRows(_frame, _out);
	return _out;
}

void Compositor::stretchRows(const Graphics::Surface &src, Graphics::Surface &dst) const {
	// area filter on rows: output row Y covers the source rows [Y * sh / dh, (Y + 1) * sh / dh),
	// computed exactly in units of 1/dh; every source row weighs the same in the result
	const int sh = src.h, dh = dst.h, w = MIN(src.w, dst.w);
	const bool wide = _fmt.bytesPerPixel == 4;
	Common::Array<uint32> acc(w * 4);
	for (int Y = 0; Y < dh; Y++) {
		const int64 lo = (int64)Y * sh, hi = (int64)(Y + 1) * sh;
		const int r0 = (int)(lo / dh), r1 = (int)MIN<int64>((hi + dh - 1) / dh, sh);
		if (r1 - r0 == 1) {
			memcpy(dst.getBasePtr(0, Y), src.getBasePtr(0, r0), w * _fmt.bytesPerPixel);
			continue;
		}
		memset(&acc[0], 0, w * 4 * sizeof(uint32));
		for (int r = r0; r < r1; r++) {
			const uint32 wgt = (uint32)(MIN<int64>(hi, (int64)(r + 1) * dh) - MAX<int64>(lo, (int64)r * dh));
			if (wide) {
				const byte *sp = (const byte *)src.getBasePtr(0, r);
				for (int i = 0; i < w * 4; i++)
					acc[i] += sp[i] * wgt;	// every channel of an 8888 pixel is one byte
			} else {
				const uint16 *sp = (const uint16 *)src.getBasePtr(0, r);
				for (int x = 0; x < w; x++) {
					byte cr, cg, cb;
					_fmt.colorToRGB(sp[x], cr, cg, cb);
					acc[x * 4] += cr * wgt;
					acc[x * 4 + 1] += cg * wgt;
					acc[x * 4 + 2] += cb * wgt;
				}
			}
		}
		const uint32 half = sh / 2;
		if (wide) {
			byte *dp = (byte *)dst.getBasePtr(0, Y);
			for (int i = 0; i < w * 4; i++)
				dp[i] = (byte)((acc[i] + half) / sh);
		} else {
			uint16 *dp = (uint16 *)dst.getBasePtr(0, Y);
			for (int x = 0; x < w; x++)
				dp[x] = (uint16)_fmt.RGBToColor((acc[x * 4] + half) / sh, (acc[x * 4 + 1] + half) / sh, (acc[x * 4 + 2] + half) / sh);
		}
	}
}

Common::Point Compositor::toGame(const Common::Point &p, int scrollX) const {
	(void)scrollX;
	const int S = _scale;
	int x = p.x / S;
	// the stretched rows are mapped back with the same proportion used to draw them
	int y = _outH ? (int)((int64)p.y * _screenH / _outH) : p.y / S;
	if (_classic)
		x -= _maxExtL;
	else
		x = _lastViewLeft + x - _lastSx;
	return Common::Point(CLIP(x, 0, _screenW - 1), CLIP(y, 0, _screenH - 1));
}

Common::Point Compositor::toScreen(const Common::Point &p) const {
	const int S = _scale;
	int c = _classic ? p.x + _maxExtL : p.x + _lastSx - _lastViewLeft;
	int X = c * S + S / 2, Y;
	if (_outH) {
		// rows of output that map back to game row p.y: [ceil(y * H / h), ceil((y + 1) * H / h))
		int y0 = (int)(((int64)p.y * _outH + _screenH - 1) / _screenH);
		int y1 = (int)(((int64)(p.y + 1) * _outH + _screenH - 1) / _screenH);
		Y = (y0 + y1 - 1) / 2;
	} else {
		Y = p.y * S + S / 2;
	}
	return Common::Point(X, Y);
}

} // End of namespace Remaster
