"""Graphics pipeline: HD backgrounds and sprites conforming to the RAC contract."""
import hashlib
import json
import os

import numpy as np
from PIL import Image

from . import comfy, imaging, rawframe, scalers


def backends():
    return {
        "comfyui": comfy.available(),
        "comfyui_url": comfy.URL,
        "realesrgan": bool(scalers.realesrgan_binary()),
        "cpu_scalers": True,
    }


def load_recipe(path, category):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        recipes = json.load(f)
    r = recipes.get(category) or recipes.get("default")
    if r is None:
        raise KeyError(f"ricetta '{category}' assente in {path}")
    return r


def recipe_hash(recipe, extra=""):
    blob = json.dumps(recipe, sort_keys=True) + extra
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def _load_original(path):
    if path.endswith(".raw"):
        return rawframe.read_raw(path).rgb()
    return Image.open(path).convert("RGB")


def _tiled_img2img(img, recipe, seed, tile=1024, overlap=128):
    W, H = img.size
    if W <= tile + overlap and H <= tile + overlap:
        return comfy.img2img(img, recipe, seed).resize((W, H), Image.LANCZOS)
    acc = np.zeros((H, W, 3))
    wsum = np.zeros((H, W, 1))
    step = tile - overlap
    for y in range(0, max(1, H - overlap), step):
        for x in range(0, max(1, W - overlap), step):
            box = (x, y, min(W, x + tile), min(H, y + tile))
            part = img.crop(box)
            out = comfy.img2img(part, recipe, seed).resize(part.size, Image.LANCZOS)
            pw, ph = part.size
            # feathered weights so tiles blend without seams
            wx = np.minimum(np.arange(pw) + 1, np.arange(pw)[::-1] + 1).clip(max=overlap) / overlap
            wy = np.minimum(np.arange(ph) + 1, np.arange(ph)[::-1] + 1).clip(max=overlap) / overlap
            wgt = (wy[:, None] * wx[None, :])[..., None]
            acc[box[1]:box[3], box[0]:box[2]] += imaging.to_f(out) * wgt
            wsum[box[1]:box[3], box[0]:box[2]] += wgt
    out = acc / np.maximum(wsum, 1e-6)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGB")


def remaster_background(src, scale=3, recipe=None, seed=1234, use_ai=True):
    """Original (.raw or image) -> HD image at `scale` x, colour-locked to the original."""
    orig = _load_original(src)
    base = scalers.upscale_rgb(orig, 4)
    used = "scale"
    if use_ai and recipe and comfy.available():
        base = _tiled_img2img(base, recipe, seed)
        used = "comfyui"
    hd = imaging.color_lock(base, orig, radius=recipe.get("color_lock_radius", 2.0) if recipe else 2.0)
    hd = hd.resize((orig.width * scale, orig.height * scale), Image.LANCZOS)
    return orig, hd, used


def batch_backgrounds(src_dir, out_dir, scale=3, recipe_path=None, seed=1234, use_ai=True, fmt="png"):
    os.makedirs(out_dir, exist_ok=True)
    recipe = load_recipe(recipe_path, "background") if recipe_path else None
    report = []
    for name in sorted(os.listdir(src_dir)):
        if not name.lower().endswith((".raw", ".png", ".bmp", ".gif")) or ".hd." in name:
            continue
        scene = os.path.splitext(name)[0]
        if name.lower().endswith(".png") and os.path.exists(os.path.join(src_dir, scene + ".raw")):
            continue  # preview of a .raw
        orig, hd, used = remaster_background(os.path.join(src_dir, name), scale, recipe, seed, use_ai)
        dst = os.path.join(out_dir, scene + (".jpg" if fmt == "jpg" else ".png"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        hd.save(dst, quality=90, subsampling=0) if fmt == "jpg" else hd.save(dst, optimize=True)
        meta = {"scene": scene, "scale": scale, "backend": used, "seed": seed,
                "recipe": recipe_hash(recipe) if recipe else None}
        with open(dst + ".json", "w") as f:
            json.dump(meta, f)
        q = check_pair(orig, hd)
        report.append({**meta, **q})
    return report


def soft_alpha(mask: np.ndarray, scale: int) -> np.ndarray:
    """Upscaled alpha from an opaque mask: bilinear coverage + smoothstep (0.3..0.7),
    clamped at the frame border so cut sprites join without seams."""
    h, w = mask.shape
    m = mask.astype(np.float64)
    ys = (np.arange(h * scale) + 0.5) / scale - 0.5
    xs = (np.arange(w * scale) + 0.5) / scale - 0.5
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    wy, wx = ys - y0, xs - x0
    y0c, y1c = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
    x0c, x1c = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
    top = m[y0c][:, x0c] * (1 - wx) + m[y0c][:, x1c] * wx
    bot = m[y1c][:, x0c] * (1 - wx) + m[y1c][:, x1c] * wx
    v = top * (1 - wy)[:, None] + bot * wy[:, None]
    t = np.clip((v - 0.3) / 0.4, 0, 1)
    return (t * t * (3 - 2 * t) * 255 + 0.5).astype(np.uint8)


def remaster_sprite(fr: rawframe.RawFrame, scale=3, recipe=None, seed=1234, use_ai=True):
    idx_up = scalers.scale_indexed(fr.pixels, scale) if scale in (2, 3, 4, 6) else \
        np.kron(fr.pixels, np.ones((scale, scale), dtype=np.uint8))
    pal = np.frombuffer(fr.palette, dtype=np.uint8).reshape(256, 3)
    rgb = Image.fromarray(pal[idx_up], "RGB")
    used = "scale"
    if use_ai and recipe and comfy.available() and fr.w * fr.h >= 64:
        rgb = comfy.img2img(rgb, recipe, seed).resize(rgb.size, Image.LANCZOS)
        rgb = imaging.color_lock(rgb, fr.rgb(), radius=1.0)
        used = "comfyui"
    alpha = soft_alpha(fr.pixels != fr.transparent, scale)
    out = np.dstack([np.asarray(rgb), alpha])
    return Image.fromarray(out, "RGBA"), used


def batch_sprites(dump_dir, out_dir, scale=3, recipe_path=None, seed=1234, use_ai=False, tag=b"RSPR"):
    """Deterministic by default: per-frame generative img2img breaks the coherence of animations
    (thousands of frames can not stay coherent); enable it only for a few static frames, after review."""
    os.makedirs(out_dir, exist_ok=True)
    recipe = load_recipe(recipe_path, "sprite") if recipe_path else None
    done = 0
    for name in sorted(os.listdir(dump_dir)):
        if not name.endswith(".raw"):
            continue
        fr = rawframe.read_raw(os.path.join(dump_dir, name))
        img, _used = remaster_sprite(fr, scale, recipe, seed, use_ai)
        img.save(os.path.join(out_dir, fr.key + ".png"), optimize=True)
        done += 1
    idx = rawframe.build_index_from_dump(dump_dir, out_dir, os.path.join(out_dir, "index.dat"), scale, tag)
    return {"sprites": done, **idx}


def check_pair(orig: Image.Image, hd: Image.Image):
    small = hd.convert("RGB").resize(orig.size, Image.BOX)
    return {"ssim": round(imaging.ssim(orig, small), 4), "delta_e": round(imaging.mean_delta_e(orig, small), 2)}


def check_dirs(orig_dir, hd_dir, min_ssim=0.85, max_de=6.0):
    rows = []
    for name in sorted(os.listdir(orig_dir)):
        if not name.lower().endswith((".raw", ".png")):
            continue
        scene = os.path.splitext(name)[0]
        for ext in (".png", ".jpg"):
            hp = os.path.join(hd_dir, scene + ext)
            if os.path.exists(hp):
                q = check_pair(_load_original(os.path.join(orig_dir, name)), Image.open(hp))
                q["scene"] = scene
                q["ok"] = q["ssim"] >= min_ssim and q["delta_e"] <= max_de
                rows.append(q)
                break
    return rows
