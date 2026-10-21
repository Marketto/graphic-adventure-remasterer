"""Dumped indexed images (.raw) and the RSPR sprite index.

.raw layout (written by the Remaster Layer dump):
  u16 w, u16 h, u8 transparent index, u8[768] RGB palette (8 bit), u8[w*h] pixels
"""
import os
import struct
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .keys import frame_key


@dataclass
class RawFrame:
    w: int
    h: int
    transparent: int
    palette: bytes  # 768 bytes
    pixels: np.ndarray  # (h, w) uint8

    @property
    def key(self):
        return frame_key(self.pixels.tobytes(), self.w, self.h)

    def rgba(self) -> Image.Image:
        pal = np.frombuffer(self.palette, dtype=np.uint8).reshape(256, 3)
        rgb = pal[self.pixels]
        a = np.where(self.pixels == self.transparent, 0, 255).astype(np.uint8)
        return Image.fromarray(np.dstack([rgb, a]), "RGBA")

    def rgb(self) -> Image.Image:
        pal = np.frombuffer(self.palette, dtype=np.uint8).reshape(256, 3)
        return Image.fromarray(pal[self.pixels], "RGB")


def read_raw(path) -> RawFrame:
    with open(path, "rb") as f:
        data = f.read()
    w, h = struct.unpack_from("<HH", data, 0)
    t = data[4]
    pal = data[5:5 + 768]
    px = np.frombuffer(data, dtype=np.uint8, count=w * h, offset=5 + 768).reshape(h, w).copy()
    return RawFrame(w, h, t, bytes(pal), px)


def write_raw(path, frame: RawFrame):
    with open(path, "wb") as f:
        f.write(struct.pack("<HH", frame.w, frame.h))
        f.write(bytes([frame.transparent]))
        f.write(frame.palette)
        f.write(frame.pixels.astype(np.uint8).tobytes())


# ---------------------------------------------------------------- RSPR index

def write_index(path, scale, entries, palettes, tag=b"RSPR"):
    """entries: list of (key_hex, palette_index, w, h); palettes: list of 768-byte palettes."""
    with open(path, "wb") as f:
        f.write(tag)
        f.write(struct.pack("<HHH", 1, scale, len(palettes)))
        for p in palettes:
            if len(p) != 768:
                raise ValueError("palette must be 768 bytes")
            f.write(p)
        f.write(struct.pack("<I", len(entries)))
        for key, pal, w, h in entries:
            f.write(struct.pack("<IHHH", int(key, 16), pal, w, h))


def read_index(path):
    with open(path, "rb") as f:
        data = f.read()
    tag = data[:4]
    if tag != b"RSPR":
        raise ValueError("not a sprite index")
    _ver, scale, npal = struct.unpack_from("<HHH", data, 4)
    off = 10
    pals = [data[off + i * 768: off + (i + 1) * 768] for i in range(npal)]
    off += npal * 768
    (n,) = struct.unpack_from("<I", data, off)
    off += 4
    entries = []
    for i in range(n):
        key, pal, w, h = struct.unpack_from("<IHHH", data, off + i * 10)
        entries.append(("%08x" % key, pal, w, h))
    return {"tag": tag.decode(), "scale": scale, "palettes": pals, "entries": entries}


def build_index_from_dump(dump_dir, hd_dir, out_path, scale, tag=b"RSPR"):
    """Index every HD frame in hd_dir whose original .raw is in dump_dir."""
    palettes, pal_ids, entries, missing = [], {}, [], []
    for name in sorted(os.listdir(dump_dir)):
        if not name.endswith(".raw"):
            continue
        key = name[:-4]
        hd = None
        for ext in (".png", ".jpg"):
            if os.path.exists(os.path.join(hd_dir, key + ext)):
                hd = key + ext
        if not hd:
            missing.append(key)
            continue
        fr = read_raw(os.path.join(dump_dir, name))
        if fr.key != key:
            raise ValueError(f"{name}: key mismatch ({fr.key})")
        pid = pal_ids.get(fr.palette)
        if pid is None:
            pid = pal_ids[fr.palette] = len(palettes)
            palettes.append(fr.palette)
        entries.append((key, pid, fr.w, fr.h))
    write_index(out_path, scale, entries, palettes, tag)
    return {"indexed": len(entries), "palettes": len(palettes), "missing": missing}
