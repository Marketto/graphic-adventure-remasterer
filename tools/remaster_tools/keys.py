"""Asset keys of the Remaster Asset Contract (references/asset-contract.md).

Both keys are zlib CRC32 values, written as 8 lowercase hex digits, and match the
C++ implementation in engine/scummvm-remaster-layer.
"""
import struct
import zlib

# bytes skipped by textKey: space, tab, LF, CR, backslash, VT, FF
_TEXT_SKIP = frozenset(b" \t\n\r\\\x0b\x0c")


def frame_key(pixels: bytes, w: int, h: int) -> str:
    """Key of an indexed sprite frame: CRC32 of LE16 w, LE16 h, then w*h pixels."""
    if len(pixels) < w * h:
        raise ValueError("pixel buffer smaller than w*h")
    crc = zlib.crc32(struct.pack("<HH", w & 0xFFFF, h & 0xFFFF))
    crc = zlib.crc32(bytes(pixels[: w * h]), crc)
    return "%08x" % (crc & 0xFFFFFFFF)


def text_key(text, encoding: str = "cp850") -> str:
    """Key of a game string: CRC32 of its bytes (game code page) without whitespace/backslashes."""
    data = text.encode(encoding, errors="replace") if isinstance(text, str) else bytes(text)
    filtered = bytes(b for b in data if b not in _TEXT_SKIP)
    return "%08x" % (zlib.crc32(filtered) & 0xFFFFFFFF)
