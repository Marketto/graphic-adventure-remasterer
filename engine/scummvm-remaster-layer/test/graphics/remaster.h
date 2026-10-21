#include <cxxtest/TestSuite.h>

#include "engines/remaster/compositor.h"
#include "engines/remaster/keys.h"

// Remaster Layer: keys must match the pipeline tools (Python zlib.crc32),
// the compositor must reproduce the original frame and map the mouse back.
class RemasterTestSuite : public CxxTest::TestSuite {
	static const Graphics::PixelFormat argb() { return Graphics::PixelFormat(4, 8, 8, 8, 8, 16, 8, 0, 24); }

	static uint32 px(const Graphics::Surface &s, int x, int y) { return *(const uint32 *)s.getBasePtr(x, y); }

	void makePalette(byte *pal) {
		for (int i = 0; i < 256; i++) {
			pal[i * 3] = (byte)i;
			pal[i * 3 + 1] = (byte)(255 - i);
			pal[i * 3 + 2] = (byte)(i / 2);
		}
	}

public:
	void test_keys() {
		byte frame[13 * 5];
		for (int i = 0; i < 13 * 5; i++)
			frame[i] = (byte)((i * 7) % 256);
		TS_ASSERT_EQUALS(Remaster::keyToString(Remaster::frameKey(frame, 13, 5)), Common::String("530a0dc6"));
		TS_ASSERT_EQUALS(Remaster::keyToString(Remaster::textKey("Ciao,\\mondo! E' tardi\n")), Common::String("dd24cc89"));
	}

	void test_compose_and_classic() {
		Remaster::AssetPack pack;	// not opened: no HD assets, upscaling only
		Remaster::Compositor comp(pack, 3, 4, 2, argb());
		byte pal[768];
		makePalette(pal);
		comp.setPalette(pal, 0, 256);
		Graphics::Surface bb;
		bb.create(4, 2, Graphics::PixelFormat::createFormatCLUT8());
		byte *p = (byte *)bb.getPixels();
		for (int i = 0; i < 8; i++)
			p[i] = (byte)(10 + i);
		comp.beginScene(4, 2);
		const Graphics::Surface &out = comp.compose(bb, 0, 0);
		TS_ASSERT_EQUALS(out.w, 12);
		TS_ASSERT_EQUALS(out.h, 6);
		Graphics::PixelFormat f = argb();
		// a uniform 3x3 block where the neighbours don't form a diagonal edge
		TS_ASSERT_EQUALS(px(out, 4, 1), f.RGBToColor(11, 244, 5));
		comp.setClassic(true);
		const Graphics::Surface &cl = comp.compose(bb, 0, 0);
		for (int y = 0; y < 6; y++)
			for (int x = 0; x < 12; x++) {
				byte i = p[(y / 3) * 4 + x / 3];
				TS_ASSERT_EQUALS(px(cl, x, y), f.RGBToColor(pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]));
			}
		bb.free();
	}

	void test_widescreen_bands_and_mouse() {
		Remaster::AssetPack pack;
		Remaster::Compositor comp(pack, 3, 4, 2, argb());
		comp.setMaxExtension(1, 1);
		byte pal[768];
		makePalette(pal);
		comp.setPalette(pal, 0, 256);
		Graphics::Surface bb;
		bb.create(4, 2, Graphics::PixelFormat::createFormatCLUT8());
		memset(bb.getPixels(), 200, 8);
		comp.beginScene(4, 2);
		const Graphics::Surface &out = comp.compose(bb, 0, 0);
		TS_ASSERT_EQUALS(out.w, 18);
		Graphics::PixelFormat f = argb();
		TS_ASSERT_EQUALS(px(out, 0, 0), f.RGBToColor(0, 0, 0));		// side band (no wide picture)
		TS_ASSERT_EQUALS(px(out, 17, 5), f.RGBToColor(0, 0, 0));
		TS_ASSERT_EQUALS(px(out, 3, 0), f.RGBToColor(200, 55, 100));	// first game column
		// output pixel 10 is game column (10 / 3) - 1 = 2
		Common::Point g = comp.toGame(Common::Point(10, 4), 0);
		TS_ASSERT_EQUALS(g.x, 2);
		TS_ASSERT_EQUALS(g.y, 1);
		// clicks in the bands are clamped to the game area
		TS_ASSERT_EQUALS(comp.toGame(Common::Point(0, 0), 0).x, 0);
		TS_ASSERT_EQUALS(comp.toGame(Common::Point(17, 0), 0).x, 3);
		bb.free();
	}

	void test_smooth_scroll_subpixel() {
		Remaster::AssetPack pack;
		Remaster::Compositor comp(pack, 3, 2, 1, argb());
		byte pal[768];
		makePalette(pal);
		comp.setPalette(pal, 0, 256);
		Graphics::Surface bb;
		bb.create(4, 1, Graphics::PixelFormat::createFormatCLUT8());
		byte *p = (byte *)bb.getPixels();
		p[0] = 1; p[1] = 2; p[2] = 3; p[3] = 4;
		comp.beginScene(4, 1);
		Graphics::PixelFormat f = argb();
		// scroll 1 + 1/3 pixel: the output starts one HD pixel into game column 1
		const Graphics::Surface &out = comp.compose(bb, 256 + 86, 0);
		TS_ASSERT_EQUALS(px(out, 0, 0), f.RGBToColor(2, 253, 1));
		TS_ASSERT_EQUALS(px(out, 2, 0), f.RGBToColor(3, 252, 1));
		bb.free();
	}
};
