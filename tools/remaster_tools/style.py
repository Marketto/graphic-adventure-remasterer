"""Measurable traits of the original art, to back the style bible with numbers."""
import json
import os

import numpy as np
from PIL import Image

from . import imaging, rawframe


def _load(path):
    if path.endswith(".raw"):
        fr = rawframe.read_raw(path)
        return fr.rgb(), fr
    return Image.open(path).convert("RGB"), None


def dominant_colors(img, n=12):
    q = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    counts = sorted(q.getcolors(), reverse=True)
    pal = q.getpalette()
    total = sum(c for c, _ in counts)
    return [{"hex": "#%02x%02x%02x" % tuple(pal[i * 3:i * 3 + 3]), "share": round(c / total, 4)} for c, i in counts]


def dither_ratio(idx: np.ndarray):
    """Share of pixels in a 2x2 checkerboard of two alternating colours."""
    a, b = idx[:-1, :-1], idx[:-1, 1:]
    c, d = idx[1:, :-1], idx[1:, 1:]
    checker = (a == d) & (b == c) & (a != b)
    return float(checker.mean()) if checker.size else 0.0


def _indexed(img):
    """Indices of an RGB picture (for dither and colour counts of PNG dumps)."""
    a = np.asarray(img.convert("RGB")).astype(np.int64)
    return a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]


def outline_stats(fr):
    """For sprites: how dark the silhouette border is (dark outlines vs coloured edges).
    `fr`: a RawFrame or an RGBA picture (PNG dump: transparent where alpha is 0)."""
    if isinstance(fr, Image.Image):
        a = np.asarray(fr.convert("RGBA")).astype(float)
        m = a[..., 3] > 0
        lum = a[..., :3] @ np.array([0.299, 0.587, 0.114])
    else:
        m = fr.pixels != fr.transparent
        pal = np.frombuffer(fr.palette, dtype=np.uint8).reshape(256, 3).astype(float)
        lum = (pal @ np.array([0.299, 0.587, 0.114]))[fr.pixels]
    if m.sum() == 0:
        return None
    p = np.pad(m, 1)
    border = m & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    return {"border_luma": round(float(lum[border].mean()), 1), "inner_luma": round(float(lum[m & ~border].mean() if (m & ~border).any() else 0), 1)}


def sprite_count(spr_dir):
    """Frames listed in spr/index.json (a list, or {"frames": [...]} / {key: ...}), if present:
    a PNG dump may store sheets or only a sample of the frames."""
    p = os.path.join(spr_dir, "index.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        idx = json.load(f)
    if isinstance(idx, dict):
        idx = idx.get("frames", idx)
    return len(idx)


def analyze(dump_dir, out_dir):
    """Measures of the original art from a dump: .raw frames of the Layer or PNG (RGB
    backgrounds, RGBA sprites) of an extraction without the Layer."""
    os.makedirs(out_dir, exist_ok=True)
    report = {"backgrounds": [], "sprites": {"count": 0, "outline": None}}
    bg_dir = os.path.join(dump_dir, "bg") if os.path.isdir(os.path.join(dump_dir, "bg")) else dump_dir
    spr_dir = os.path.join(dump_dir, "spr")
    thumbs, labels = [], []
    for name in sorted(os.listdir(bg_dir)):
        p = os.path.join(bg_dir, name)
        if not name.lower().endswith((".raw", ".png", ".bmp")) or not os.path.isfile(p):
            continue
        scene = os.path.splitext(name)[0]
        if name.endswith(".png") and os.path.exists(os.path.join(bg_dir, scene + ".raw")):
            continue
        img, fr = _load(p)
        idx = fr.pixels if fr else _indexed(img)
        f = imaging.to_f(img)
        lum = f @ np.array([0.299, 0.587, 0.114])
        hsv = np.asarray(img.convert("HSV"), dtype=float) / 255
        gy, gx = np.gradient(lum)
        entry = {
            "scene": scene, "size": img.size,
            "colors_used": int(len(np.unique(idx))),
            "dither": round(dither_ratio(idx), 4),
            "brightness": round(float(lum.mean()), 3), "contrast": round(float(lum.std()), 3),
            "saturation": round(float(hsv[..., 1].mean()), 3),
            # crude light direction: where the brighter half of the picture is
            "light_from": ("sinistra" if lum[:, : lum.shape[1] // 2].mean() > lum[:, lum.shape[1] // 2:].mean() else "destra")
            + ("/alto" if lum[: lum.shape[0] // 2].mean() > lum[lum.shape[0] // 2:].mean() else "/basso"),
            "edge_density": round(float((np.hypot(gx, gy) > 0.08).mean()), 4),
            "palette": dominant_colors(img),
        }
        report["backgrounds"].append(entry)
        thumbs.append(img)
        labels.append(scene)
    if thumbs:
        imaging.contact_sheet(thumbs, labels=labels).save(os.path.join(out_dir, "backgrounds.png"))
    if os.path.isdir(spr_dir):
        outs, sprites = [], []
        files = [n for n in sorted(os.listdir(spr_dir)) if n.lower().endswith((".raw", ".png"))]
        raws = {os.path.splitext(n)[0] for n in files if n.endswith(".raw")}
        for name in files:
            stem = os.path.splitext(name)[0]
            if name.lower().endswith(".png") and stem in raws:
                continue
            if name.endswith(".raw"):
                fr = rawframe.read_raw(os.path.join(spr_dir, name))
                o, im = outline_stats(fr), fr.rgba()
            else:
                im = Image.open(os.path.join(spr_dir, name)).convert("RGBA")
                o = outline_stats(im)
            report["sprites"]["count"] += 1
            if o:
                outs.append(o)
            if len(sprites) < 48 and im.size[0] * im.size[1] > 400:
                sprites.append(im)
        n_index = sprite_count(spr_dir)
        if n_index is not None:
            report["sprites"]["count"] = n_index
        if outs:
            report["sprites"]["outline"] = {
                "border_luma": round(float(np.mean([o["border_luma"] for o in outs])), 1),
                "inner_luma": round(float(np.mean([o["inner_luma"] for o in outs])), 1)}
        if sprites:
            imaging.contact_sheet(sprites, cols=8, thumb=160).save(os.path.join(out_dir, "sprites.png"))
    if report["backgrounds"]:
        report["global"] = {
            "brightness": round(float(np.mean([b["brightness"] for b in report["backgrounds"]])), 3),
            "contrast": round(float(np.mean([b["contrast"] for b in report["backgrounds"]])), 3),
            "saturation": round(float(np.mean([b["saturation"] for b in report["backgrounds"]])), 3),
            "dither": round(float(np.mean([b["dither"] or 0 for b in report["backgrounds"]])), 4),
        }
    with open(os.path.join(out_dir, "style-metrics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report
