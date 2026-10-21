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

#ifndef ENGINES_REMASTER_ASSETPACK_H
#define ENGINES_REMASTER_ASSETPACK_H

#include "common/array.h"
#include "common/fs.h"
#include "common/hashmap.h"
#include "common/hash-str.h"
#include "common/str.h"
#include "common/stream.h"
#include "graphics/surface.h"

namespace Remaster {

/** 16:9 data of a scene (remaster/gfx/bg/<scene>.wide.json) */
struct WideInfo {
	int left = 0, right = 0;		///< pixels added on each side, at the original scale
	bool clampCamera = false;		///< scrolling scene: show more of the existing background
	bool pillarbox = false;			///< keep 4:3, black bars
	bool hasImage = false;			///< <scene>.wide.png (or its localized version) exists
};

struct SpriteEntry {
	uint16 palette;
	uint16 w, h;
};

/**
 * Read-only access to the remaster pack of the running game:
 * <game path>/remaster/.
 * See references/asset-contract.md of Remaster Studio.
 */
class AssetPack {
public:
	AssetPack();
	~AssetPack();

	/** Look for the pack in the game folder (ConfMan "path"). */
	bool open();
	bool isOpen() const { return _open; }
	int scale() const { return _scale; }
	const Common::String &gameId() const { return _gameId; }

	/** Stream of a file inside the pack, relative path with '/' */
	Common::SeekableReadStream *openFile(const Common::String &relPath) const;
	bool exists(const Common::String &relPath) const;

	/**
	 * Image without extension (tries .png then .jpg), converted to ARGB8888 (A in the high byte).
	 * Caller owns the surface. nullptr when missing or unreadable.
	 */
	Graphics::Surface *loadImage(const Common::String &relPathNoExt) const;

	/** Language of the localized backgrounds (painted texts translated), empty for none */
	void setLanguage(const Common::String &lang) { _lang = lang; }
	/**
	 * Background picture of a scene without extension: gfx/bg/<scene>.<lang>[.wide]
	 * when present, else gfx/bg/<scene>[.wide]; empty when there is none.
	 */
	Common::String backgroundPath(const Common::String &scene, bool wide = false) const;

	/** HD background of a scene; 'scale' receives the integer factor of the picture. */
	Graphics::Surface *loadBackground(const Common::String &scene, int origW, int origH, int &scale) const;
	WideInfo wideInfo(const Common::String &scene) const;
	Graphics::Surface *loadWideBackground(const Common::String &scene) const;

	/** Sprite index (RSPR) */
	bool hasSprite(uint32 key) const { return _sprites.contains(key); }
	const SpriteEntry *sprite(uint32 key) const;
	const byte *spritePalette(uint16 index) const;
	int spriteScale() const { return _spriteScale; }

	/** Corrected / translated text for a language ("it", "en"...), UTF-8 */
	bool loadTexts(const Common::String &lang);
	bool text(uint32 key, Common::String &utf8) const;

	/** Recorded voice for a text key: path relative to the pack, empty if none */
	Common::String voicePath(uint32 key, const Common::String &lang) const;

private:
	bool _open;
	int _scale;
	int _spriteScale;
	Common::String _gameId;
	Common::String _lang;
	Common::FSNode _root;
	Common::HashMap<uint32, SpriteEntry> _sprites;
	Common::Array<byte> _spritePalettes;
	Common::HashMap<uint32, Common::String> _texts;

	Common::FSNode node(const Common::String &relPath) const;
	bool hasImage(const Common::String &relPathNoExt) const;
	void loadManifest();
	void loadSpriteIndex();
};

} // End of namespace Remaster

#endif
