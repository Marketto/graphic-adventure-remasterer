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


def outline_stats(fr: rawframe.RawFrame):
    """For sprites: how dark the silhouette border is (dark outlines vs coloured edges)."""
    m = fr.pixels != fr.transparent
    if m.sum() == 0:
        return None
    p = np.pad(m, 1)
    border = m & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    pal = np.frombuffer(fr.palette, dtype=np.uint8).reshape(256, 3).astype(float)
    lum = (pal @ np.array([0.299, 0.587, 0.114]))[fr.pixels]
    return {"border_luma": round(float(lum[border].mean()), 1), "inner_luma": round(float(lum[m & ~border].mean() if (m & ~border).any() else 0), 1)}


def analyze(dump_dir, out_dir):
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
        f = imaging.to_f(img)
        lum = f @ np.array([0.299, 0.587, 0.114])
        hsv = np.asarray(img.convert("HSV"), dtype=float) / 255
        gy, gx = np.gradient(lum)
        entry = {
            "scene": scene, "size": img.size,
            "colors_used": int(len(np.unique(fr.pixels))) if fr else None,
            "dither": round(dither_ratio(fr.pixels), 4) if fr else None,
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
        for name in sorted(os.listdir(spr_dir)):
            if name.endswith(".raw"):
                fr = rawframe.read_raw(os.path.join(spr_dir, name))
                report["sprites"]["count"] += 1
                o = outline_stats(fr)
                if o:
                    outs.append(o)
                if len(sprites) < 48 and fr.w * fr.h > 400:
                    sprites.append(fr.rgba())
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
