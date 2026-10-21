"""Graphics pipeline: HD backgrounds and sprites conforming to the RAC contract."""
import hashlib
import json
import os
import shutil

import numpy as np
from PIL import Image

from . import comfy, imaging, rawframe, scalers


def backends():
    st = scalers.torch_status()
    models = {}
    for kind, env in scalers.MODEL_ENV.items():
        m = os.environ.get(env)
        models[kind] = {"env": env, "model": m, "exists": bool(m) and os.path.isfile(m)}
        try:
            models[kind]["backend"] = scalers.choose_backend(kind)[0]
        except RuntimeError as e:
            models[kind]["backend"] = None
            models[kind]["error"] = str(e)
    return {
        "spandrel": st["spandrel"],
        "torch": st["torch"],
        "spandrel_ready": st["spandrel_ready"],
        "models": models,
        "realesrgan": bool(scalers.realesrgan_binary()),
        "comfyui": comfy.available(),
        "comfyui_url": comfy.URL,
        "cpu_scalers": True,
        "ffmpeg": bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe")),
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


def remaster_background(src, scale=3, recipe=None, seed=1234, use_ai=True, model=None):
    """Original (.raw or image) -> HD image at `scale` x.

    Upscaler at 4x (spandrel model such as APISR RRDB, Real-ESRGAN ncnn, or Scale2x/3x), then
    the optional img2img (ComfyUI) followed by the colour lock to the original, then 4x -> scale
    with LANCZOS."""
    orig = _load_original(src)
    base, used = scalers.upscale_rgb_info(orig, 4, model=model, kind="bg")
    if use_ai and recipe and comfy.available():
        base = _tiled_img2img(base, recipe, seed)
        base = imaging.color_lock(base, orig, radius=recipe.get("color_lock_radius", 2.0))
        used += "+comfyui"
    hd = base.resize((orig.width * scale, orig.height * scale), Image.LANCZOS)
    return orig, hd, used


def batch_backgrounds(src_dir, out_dir, scale=3, recipe_path=None, seed=1234, use_ai=True, fmt="png",
                      model=None, resume=True):
    """Restartable: a scene already made with the same scale, upscaler model and recipe is skipped."""
    os.makedirs(out_dir, exist_ok=True)
    recipe = load_recipe(recipe_path, "background") if recipe_path else None
    model_path = scalers.model_for("bg", model)
    want_model = os.path.basename(model_path or "") or None
    # identity of the weights: full path and size (two files with the same name are different)
    model_id = None
    if model_path:
        size = os.path.getsize(model_path) if os.path.exists(model_path) else None
        model_id = f"{os.path.abspath(model_path)}:{size}"
    backend_now = scalers.choose_backend("bg", model)[0]
    ai_now = bool(use_ai and recipe and comfy.available())
    rhash = recipe_hash(recipe) if recipe else None
    report = []
    for name in sorted(os.listdir(src_dir)):
        if not name.lower().endswith((".raw", ".png", ".bmp", ".gif")) or ".hd." in name:
            continue
        scene = os.path.splitext(name)[0]
        if name.lower().endswith(".png") and os.path.exists(os.path.join(src_dir, scene + ".raw")):
            continue  # preview of a .raw
        dst = os.path.join(out_dir, scene + (".jpg" if fmt == "jpg" else ".png"))
        if resume and os.path.exists(dst) and os.path.exists(dst + ".json"):
            with open(dst + ".json") as f:
                old = json.load(f)
            if (old.get("scale") == scale and old.get("model_id") == model_id and old.get("recipe") == rhash
                    and old.get("upscaler") == backend_now and old.get("img2img") == ai_now):
                report.append({**old, "skipped": True})
                continue
        orig, hd, used = remaster_background(os.path.join(src_dir, name), scale, recipe, seed, use_ai, model)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        hd.save(dst, quality=90, subsampling=0) if fmt == "jpg" else hd.save(dst, optimize=True)
        meta = {"scene": scene, "scale": scale, "backend": used, "model": want_model, "model_id": model_id,
                "upscaler": backend_now, "img2img": ai_now, "seed": seed, "recipe": rhash}
        with open(dst + ".json", "w") as f:
            json.dump(meta, f)
        q = check_pair(orig, hd)
        report.append({**meta, **q})
    return report


def soft_alpha(mask: np.ndarray, scale: int) -> np.ndarray:
    """Upscaled alpha from an opaque mask: bilinear coverage + smoothstep (0.3..0.7),
    clamped at the frame border so cut sprites join without seams. Used when there is no
    silhouette pipeline (generative path); the common Layer takes the alpha from the PNG."""
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


# ---------------------------------------------------------------- deterministic sprite pipeline
def gaussian(a: np.ndarray, sigma: float) -> np.ndarray:
    """Separable gaussian blur of a 2-D float array (edge padding), no SciPy needed."""
    a = a.astype(np.float64)
    if sigma <= 0:
        return a
    r = max(1, int(np.ceil(3 * sigma)))
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, r, mode="edge")
    h, w = a.shape
    tmp = sum(k[i] * p[i:i + h, :] for i in range(2 * r + 1))
    return sum(k[i] * tmp[:, i:i + w] for i in range(2 * r + 1))


def box_blur(a: np.ndarray, r: int) -> np.ndarray:
    """Box sum (window 2r+1, zero outside) of a 2-D or HxWxC array, via a summed-area table."""
    a = a.astype(np.float64)
    pad = ((r + 1, r), (r + 1, r)) + ((0, 0),) * (a.ndim - 2)
    c = np.pad(a, pad).cumsum(0).cumsum(1)
    n = 2 * r + 1
    return c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]


def fill_outside(rgb: np.ndarray, known: np.ndarray, radii=(2, 4, 8, 16)) -> np.ndarray:
    """Give the unknown pixels the colours of the known ones nearby, spreading them outwards with
    box blurs of growing radius (2, 4, 8, 16): no dark fringes once the sprite is saved as JPEG,
    resampled or blended through a soft alpha."""
    out = rgb.astype(np.float64).copy()
    have = known.astype(bool).copy()
    for r in radii:
        if have.all():
            break
        w = box_blur(have.astype(np.float64), r)
        acc = box_blur(out * have[..., None], r)
        new = (~have) & (w > 1e-9)
        out[new] = acc[new] / w[new][:, None]
        have |= new
    if not have.all():
        out[~have] = out[have].mean(0) if have.any() else 0
    return out


def _lum(rgb):
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def _erode4(m):
    p = np.pad(m, 1, constant_values=False)
    return m & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]


def _dilate8(m):
    p = np.pad(m, 1, constant_values=False)
    out = m.copy()
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            out |= p[dy:dy + m.shape[0], dx:dx + m.shape[1]]
    return out


def outline_analysis(rgb1x: np.ndarray, mask: np.ndarray, dark_ratio=0.6, dark_max=110.0):
    """Dark outline of a 1x frame: which boundary pixels are ink, and how thick the ink is.

    A boundary pixel (opaque, touching transparency) is ink when its luminance is below
    `dark_ratio` x the median luminance of the interior and below `dark_max`. Thickness in px at
    1x = 1 + the ink-like pixels of the next inner rings that continue the ink, per ink pixel."""
    lum = _lum(rgb1x.astype(np.float64))
    inner = _erode4(mask)
    boundary = mask & ~inner
    ref = np.median(lum[inner]) if inner.any() else np.median(lum[mask])
    dark = mask & (lum < min(dark_max, dark_ratio * max(ref, 1.0)))
    ink_b = boundary & dark
    n0 = int(ink_b.sum())
    if n0 == 0:
        return ink_b, 0.0
    # inner rings continue the ink only with ink-like pixels (not merely dark clothes or hair)
    ink_like = dark & (lum <= np.median(lum[ink_b]) + 24.0)
    thick, ring_prev, cur = 1.0, ink_b, inner
    for _ in range(3):
        nxt = _erode4(cur)
        ring_dark = cur & ~nxt & ink_like & _dilate8(ring_prev)
        frac = ring_dark.sum() / n0
        if frac < 0.15:
            break
        thick += min(1.0, frac)
        ring_prev, cur = ring_dark, nxt
    return ink_b, float(thick)


def _upsample_field(a: np.ndarray, scale: int) -> np.ndarray:
    """Pixel-centre aligned bilinear upsampling of a 2-D field (edges clamped)."""
    h, w = a.shape
    ys = np.clip((np.arange(h * scale) + 0.5) / scale - 0.5, 0, h - 1)
    xs = np.clip((np.arange(w * scale) + 0.5) / scale - 0.5, 0, w - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, h - 1), np.minimum(x0 + 1, w - 1)
    wy, wx = (ys - y0)[:, None], (xs - x0)[None, :]
    return (a[y0][:, x0] * (1 - wy) * (1 - wx) + a[y0][:, x1] * (1 - wy) * wx +
            a[y1][:, x0] * wy * (1 - wx) + a[y1][:, x1] * wy * wx)


def silhouette(mask: np.ndarray, scale: int, sigma=0.65):
    """HD silhouette = 0.5 level of the original mask blurred with `sigma` (px at 1x; the rule
    of the reference project's engine, which rebuilt the alpha this way), computed at the HD scale, plus an antialiased alpha in
    [0, 1] (signed distance from the field gradient: about one HD pixel of ramp)."""
    big = np.kron(mask.astype(np.float64), np.ones((scale, scale)))
    field = gaussian(big, sigma * scale)
    gy, gx = np.gradient(field)
    g = np.maximum(np.hypot(gx, gy), 1e-6)
    alpha = np.clip((field - 0.5) / g + 0.5, 0, 1)
    return field >= 0.5, alpha


def _inside_distance(inside: np.ndarray, rmax: int) -> np.ndarray:
    """Distance (HD px) from each inside pixel to the edge of the silhouette (nearest outside
    pixel centre minus half a pixel), capped at rmax. Brute force over the offsets of a disc:
    exact, deterministic and cheap for the small radius of an outline."""
    h, w = inside.shape
    d = np.full((h, w), float(rmax), dtype=np.float64)
    pad = np.pad(~inside, rmax, constant_values=True)
    for dy in range(-rmax, rmax + 1):
        for dx in range(-rmax, rmax + 1):
            r = float(np.hypot(dy, dx))
            if r == 0 or r > rmax:
                continue
            out = pad[rmax + dy:rmax + dy + h, rmax + dx:rmax + dx + w]
            d = np.where(out & (r < d), r, d)
    return np.where(inside, np.maximum(d - 0.5, 0.0), 0.0)


def ink_band(rgb_hd: np.ndarray, rgb1x: np.ndarray, mask: np.ndarray, inside: np.ndarray, scale: int,
             ink_b: np.ndarray, thick: float) -> np.ndarray:
    """Repaint, where the original outline is dark, an antialiased band of ink along the smoothed
    edge: `thick` px at 1x times the scale, in the colour of the original outline."""
    if thick <= 0 or not ink_b.any():
        return rgb_hd
    T = thick * scale
    dist = _inside_distance(inside, int(np.ceil(T)) + 2)
    cover = np.clip(T - dist, 0, 1) * inside
    boundary = mask & ~_erode4(mask)
    s = 0.7
    wk = gaussian(ink_b.astype(np.float64), s)
    frac = wk / np.maximum(gaussian(boundary.astype(np.float64), s), 1e-6)
    gate = np.clip((_upsample_field(np.clip(frac, 0, 1), scale) - 0.35) / 0.3, 0, 1)
    gate = gate * gate * (3 - 2 * gate)
    col = np.dstack([gaussian(rgb1x[..., c] * ink_b, s) for c in range(3)]) / np.maximum(wk, 1e-9)[..., None]
    col_hd = np.dstack([_upsample_field(col[..., c], scale) for c in range(3)])
    k = (cover * gate)[..., None]
    return rgb_hd * (1 - k) + col_hd * k


def remaster_sprite(fr: rawframe.RawFrame, scale=3, recipe=None, seed=1234, use_ai=False, model=None,
                    ink=True, sigma=0.65, margin=3):
    """Deterministic HD sprite (same input -> same output), pipeline of the reference project:
      1. crop to the useful box; colours outside the shape spread from its edge, so the
         transparent key colour never reaches the upscaler;
      2. upscaler at 4x reduced with BOX (spandrel model such as APISR GRL, or Real-ESRGAN ncnn),
         or Scale2x/3x on the palette indices when no model is configured;
      3. silhouette = 0.5 level of the original mask blurred with sigma (px at 1x), antialiased;
      4. where the original outline is dark, an antialiased band of ink as thick as that outline;
      5. colours outside the silhouette filled from its edge (box blurs, radii 2-16): no fringes.
    Returns (RGBA image of (w*scale, h*scale), backend description)."""
    mask = fr.pixels != fr.transparent
    pal = np.frombuffer(fr.palette, dtype=np.uint8).reshape(256, 3)
    W, H = fr.w * scale, fr.h * scale
    if not mask.any():
        return Image.new("RGBA", (W, H), (0, 0, 0, 0)), "empty"
    ys, xs = np.where(mask)
    y0, y1 = max(0, ys.min() - margin), min(fr.h, ys.max() + 1 + margin)
    x0, x1 = max(0, xs.min() - margin), min(fr.w, xs.max() + 1 + margin)
    m = mask[y0:y1, x0:x1]
    idx = fr.pixels[y0:y1, x0:x1]
    rgb1 = pal[idx].astype(np.float64)
    backend, _ = scalers.choose_backend("spr", model)
    if backend == "scale":
        up = scalers.scale_indexed(idx, scale) if scale in (2, 3, 4, 6) else \
            np.kron(idx, np.ones((scale, scale), dtype=np.uint8))
        rgb_hd = pal[up].astype(np.float64)
        used = "scale"
    else:
        src = Image.fromarray((fill_outside(rgb1, m) + 0.5).astype(np.uint8), "RGB")
        big, used = scalers.upscale_rgb_info(src, scale, model=model, kind="spr")
        rgb_hd = np.asarray(big, dtype=np.float64)
    if use_ai and recipe and comfy.available() and fr.w * fr.h >= 64:
        img = Image.fromarray((np.clip(rgb_hd, 0, 255) + 0.5).astype(np.uint8), "RGB")
        img = comfy.img2img(img, recipe, seed).resize(img.size, Image.LANCZOS)
        img = imaging.color_lock(img, Image.fromarray(rgb1.astype(np.uint8)), radius=1.0)
        rgb_hd = np.asarray(img, dtype=np.float64)
        used += "+comfyui"
    inside, alpha = silhouette(m, scale, sigma)
    if ink:
        ink_b, thick = outline_analysis(rgb1, m)
        rgb_hd = ink_band(rgb_hd, rgb1, m, inside, scale, ink_b, thick)
    # place the useful box in the full frame, then fill everything outside the silhouette
    sy, sx = slice(y0 * scale, y1 * scale), slice(x0 * scale, x1 * scale)
    rgb_full = np.zeros((H, W, 3), dtype=np.float64)
    known = np.zeros((H, W), dtype=bool)
    a_full = np.zeros((H, W), dtype=np.float64)
    rgb_full[sy, sx], known[sy, sx], a_full[sy, sx] = rgb_hd, inside, alpha
    rgb_full = fill_outside(rgb_full, known)
    out = np.dstack([np.clip(rgb_full + 0.5, 0, 255), a_full * 255 + 0.5]).astype(np.uint8)
    return Image.fromarray(out, "RGBA"), used


def batch_sprites(dump_dir, out_dir, scale=3, recipe_path=None, seed=1234, use_ai=False, tag=b"RSPR",
                  model=None, ink=True, fmt="png"):
    """Deterministic by default: per-frame generative img2img breaks the coherence of animations
    (thousands of frames can not stay coherent); enable it only for a few static frames, after review.
    PNG keeps the alpha, which the common Layer uses. JPEG (q90, 4:4:4) has no alpha: only for an
    engine hook that rebuilds it from the original mask (the common Layer does not)."""
    os.makedirs(out_dir, exist_ok=True)
    recipe = load_recipe(recipe_path, "sprite") if recipe_path else None
    done, used = 0, {}
    for name in sorted(os.listdir(dump_dir)):
        if not name.endswith(".raw"):
            continue
        fr = rawframe.read_raw(os.path.join(dump_dir, name))
        img, u = remaster_sprite(fr, scale, recipe, seed, use_ai, model=model, ink=ink)
        used[u] = used.get(u, 0) + 1
        if fmt == "jpg":
            img.convert("RGB").save(os.path.join(out_dir, fr.key + ".jpg"), quality=90, subsampling=0)
        else:
            img.save(os.path.join(out_dir, fr.key + ".png"), optimize=True)
        done += 1
    idx = rawframe.build_index_from_dump(dump_dir, out_dir, os.path.join(out_dir, "index.dat"), scale, tag)
    return {"sprites": done, "backends": used, **idx}


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
