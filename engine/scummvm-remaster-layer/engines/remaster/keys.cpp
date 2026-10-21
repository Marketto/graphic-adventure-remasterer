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

#include "engines/remaster/keys.h"

namespace Remaster {

static const uint32 *crcTable() {
	static uint32 table[256];
	static bool init = false;
	if (!init) {
		for (uint32 i = 0; i < 256; i++) {
			uint32 c = i;
			for (int k = 0; k < 8; k++)
				c = (c >> 1) ^ (0xedb88320 & (0 - (c & 1)));
			table[i] = c;
		}
		init = true;
	}
	return table;
}

static inline uint32 crcByte(const uint32 *t, uint32 crc, byte b) {
	return t[(crc ^ b) & 0xff] ^ (crc >> 8);
}

uint32 frameKey(const byte *pixels, int w, int h, int pitch) {
	const uint32 *t = crcTable();
	if (pitch < 0)
		pitch = w;
	uint32 crc = 0xffffffff;
	const byte hdr[4] = { (byte)(w & 0xff), (byte)((w >> 8) & 0xff), (byte)(h & 0xff), (byte)((h >> 8) & 0xff) };
	for (int i = 0; i < 4; i++)
		crc = crcByte(t, crc, hdr[i]);
	for (int y = 0; y < h; y++) {
		const byte *row = pixels + y * pitch;
		for (int x = 0; x < w; x++)
			crc = crcByte(t, crc, row[x]);
	}
	return crc ^ 0xffffffff;
}

uint32 textKey(const Common::String &text) {
	const uint32 *t = crcTable();
	uint32 crc = 0xffffffff;
	for (uint i = 0; i < text.size(); i++) {
		byte c = (byte)text[i];
		if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\\' || c == '\v' || c == '\f')
			continue;
		crc = crcByte(t, crc, c);
	}
	return crc ^ 0xffffffff;
}

Common::String keyToString(uint32 key) {
	return Common::String::format("%08x", key);
}

} // End of namespace Remaster
