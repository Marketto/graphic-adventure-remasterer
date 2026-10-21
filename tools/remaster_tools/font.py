"""HD font atlases in RFNT format (see references/asset-contract.md)."""
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def build(ttf_path, out_base, size_px=36, scale=3, codepage="cp850", outline=0, extra_chars=""):
    """Render the 256 code points of `codepage` (plus nothing else) into an atlas.

    size_px is the em size at HD scale. outline > 0 also renders an outline channel (G).
    Returns metrics; writes <out_base>.dat and <out_base>.png.
    """
    font = ImageFont.truetype(ttf_path, size_px)
    ascent, descent = font.getmetrics()
    line = ascent + descent + 2 * outline
    pad = outline + 2
    glyphs = []
    for code in range(256):
        try:
            ch = bytes([code]).decode(codepage)
        except UnicodeDecodeError:
            ch = ""
        if code < 32 or not ch.isprintable():
            glyphs.append((ch, None))
            continue
        glyphs.append((ch, ch))
    # render each glyph on its own canvas
    cells = []
    for ch, drawable in glyphs:
        if drawable is None:
            cells.append(None)
            continue
        adv = int(round(font.getlength(drawable))) + 2 * outline
        bbox = font.getbbox(drawable, stroke_width=outline)
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            cells.append({"adv": adv, "img": None})
            continue
        w, h = bbox[2] - bbox[0] + 2 * pad, bbox[3] - bbox[1] + 2 * pad
        fill = Image.new("L", (w, h), 0)
        ImageDraw.Draw(fill).text((pad - bbox[0], pad - bbox[1]), drawable, font=font, fill=255)
        stroke = Image.new("L", (w, h), 0)
        if outline:
            ImageDraw.Draw(stroke).text((pad - bbox[0], pad - bbox[1]), drawable, font=font, fill=255,
                                        stroke_width=outline, stroke_fill=255)
        cells.append({"adv": adv, "img": (fill, stroke), "bx": bbox[0] - pad + outline, "by": bbox[1] - pad + outline})
    # shelf packing
    atlas_w = 1024
    x = y = row_h = 0
    places = []
    for c in cells:
        if not c or not c.get("img"):
            places.append(None)
            continue
        w, h = c["img"][0].size
        if x + w > atlas_w:
            x, y, row_h = 0, y + row_h + 1, 0
        places.append((x, y))
        x += w + 1
        row_h = max(row_h, h)
    atlas_h = max(1, y + row_h + 1)
    atlas = np.zeros((atlas_h, atlas_w, 3), dtype=np.uint8)
    recs = []
    for c, p in zip(cells, places):
        if c is None:
            recs.append((0, 0, 0, 0, 0, 0, 0))
            continue
        if p is None:
            recs.append((0, 0, 0, 0, 0, 0, c["adv"]))
            continue
        fill, stroke = c["img"]
        w, h = fill.size
        atlas[p[1]:p[1] + h, p[0]:p[0] + w, 0] = np.asarray(fill)
        atlas[p[1]:p[1] + h, p[0]:p[0] + w, 1] = np.asarray(stroke)
        recs.append((p[0], p[1], w, h, c["bx"], c["by"], c["adv"]))
    Image.fromarray(atlas, "RGB").save(out_base + ".png", optimize=True)
    with open(out_base + ".dat", "wb") as f:
        f.write(b"RFNT")
        f.write(struct.pack("<HHHHH", 1, scale, line, ascent + outline, outline))
        for ax, ay, w, h, bx, by, adv in recs:
            f.write(struct.pack("<HHHHhhH", ax, ay, w, h, bx, by, adv))
    missing = [i for i, (ch, d) in enumerate(glyphs) if d is not None and ch and not _has_glyph(font, ch)]
    return {"line": line, "ascent": ascent, "atlas": [atlas_w, atlas_h], "missing_codes": missing}


def _has_glyph(font, ch):
    try:
        return font.getmask(ch).getbbox() is not None or ch.isspace()
    except Exception:
        return False


def read(dat_path):
    with open(dat_path, "rb") as f:
        data = f.read()
    tag = data[:4]
    if tag != b"RFNT":
        raise ValueError("not a font atlas")
    ver, scale, line, asc, outline = struct.unpack_from("<HHHHH", data, 4)
    glyphs = [struct.unpack_from("<HHHHhhH", data, 14 + i * 14) for i in range(256)]
    return {"scale": scale, "line": line, "ascent": asc, "outline": outline,
            "adv": [g[6] for g in glyphs], "glyphs": glyphs}


def text_width(font_info, text_bytes: bytes, scale_to_original=True):
    w = sum(font_info["adv"][b] for b in text_bytes)
    return w / font_info["scale"] if scale_to_original else w
