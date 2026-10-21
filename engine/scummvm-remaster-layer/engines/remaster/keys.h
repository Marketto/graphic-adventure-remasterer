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

#ifndef ENGINES_REMASTER_KEYS_H
#define ENGINES_REMASTER_KEYS_H

#include "common/scummsys.h"
#include "common/str.h"

namespace Remaster {

/**
 * Keys of the Remaster Asset Contract (RAC v1). Both are zlib CRC32 values,
 * printed as 8 lowercase hex digits.
 */

/** CRC32 of LE16 w, LE16 h and the w*h indexed pixels of a sprite frame. */
uint32 frameKey(const byte *pixels, int w, int h, int pitch = -1);

/** CRC32 of a game string without whitespace (space, \t \n \r \v \f) and backslashes. */
uint32 textKey(const Common::String &text);

Common::String keyToString(uint32 key);

} // End of namespace Remaster

#endif
