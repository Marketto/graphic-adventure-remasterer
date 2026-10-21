"""16:9 bands with the local techniques proven on the reference project (free, CPU only):
image quilting guided by LaMa, per-scene recipes, checks (band_check, sharpness index) and an
unsharp mask tuned on the band. All functions work on numpy RGB uint8 arrays.

Order of use (see skill widescreen): LaMa at 1x -> quilting -> upscale with the background
upscaler -> checks -> the eye decides on numbered sheets. Recipes for the scenes left over.
"""
import numpy as np
from PIL import Image, ImageFilter


def _lum(a):
    return a[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)


# ------------------------------------------------------------------ image quilting
def _min_cut(err, axis):
    """Minimum error boundary through an overlap strip (Efros & Freeman). err: (h, w).
    axis=1: vertical path (one column per row); axis=0: horizontal path. Returns the path."""
    e = err if axis == 1 else err.T
    h, w = e.shape
    cost = e.copy()
    back = np.zeros((h, w), np.int8)
    for y in range(1, h):
        prev = cost[y - 1]
        left = np.r_[np.inf, prev[:-1]]
        right = np.r_[prev[1:], np.inf]
        stack = np.vstack([left, prev, right])
        k = stack.argmin(0)
        cost[y] += stack[k, np.arange(w)]
        back[y] = k - 1
    path = np.zeros(h, int)
    path[-1] = int(cost[-1].argmin())
    for y in range(h - 1, 0, -1):
        path[y - 1] = min(w - 1, max(0, path[y] + back[y, path[y]]))
    return path


def quilt(wide, band_mask, src_box, tile=12, overlap=4, candidates=300, dy=40, guide_weight=0.5,
          reuse_penalty=0.15, max_seam_error=900.0, seed=1):
    """Recompose the band pixels (band_mask True) of `wide` (LaMa already painted there, used as
    guide) with patches of the original picture (src_box = (x0, x1) columns of the original in
    `wide`), tile by tile from the inner edge outwards. Every band pixel then comes from a pixel
    painted by the artist; where no patch fits, LaMa's colour stays. Centre never touched."""
    rng = np.random.default_rng(seed)
    out = wide.astype(np.float32).copy()
    guide = out.copy()
    h, W = band_mask.shape
    x0, x1 = src_box
    src = out[:, x0:x1].copy()
    known = ~band_mask.copy()
    B = tile + overlap
    if x1 - x0 < B + 2 or h < B + 2:
        return wide
    uses = {}
    cols = np.where(band_mask.any(0))[0]
    if len(cols) == 0:
        return wide
    left_cols = cols[cols < x0]
    right_cols = cols[cols >= x1]
    plans = []
    if len(left_cols):  # outwards = towards x 0
        xs = list(range(left_cols.max() - tile + 1, left_cols.min() - tile, -tile))
        plans += [("L", x) for x in xs]
    if len(right_cols):
        xs = list(range(right_cols.min(), right_cols.max() + 1, tile))
        plans += [("R", x) for x in xs]
    for side, tx in plans:
        for ty in range(0, h, tile):
            # window = tile plus overlap on the known side (inner side and above)
            wy0 = max(0, ty - overlap)
            wy1 = min(h, ty + tile)
            if side == "L":
                wx0, wx1 = max(0, tx), min(W, tx + tile + overlap)
            else:
                wx0, wx1 = max(0, tx - overlap), min(W, tx + tile)
            wh, ww = wy1 - wy0, wx1 - wx0
            if wh < 2 or ww < 2:
                continue
            target = out[wy0:wy1, wx0:wx1]
            kmask = known[wy0:wy1, wx0:wx1]
            bmask = band_mask[wy0:wy1, wx0:wx1] & ~kmask
            if not bmask.any():
                continue
            gwin = guide[wy0:wy1, wx0:wx1]
            # candidate windows from the original at a similar height
            ylo, yhi = max(0, wy0 - dy), min(h - wh, wy0 + dy)
            if yhi < ylo:
                ylo, yhi = 0, h - wh
            # every column at the same height (painted scenes are organised in rows: sky, wall,
            # floor) plus random positions within ±dy
            same_y = min(max(wy0, 0), h - wh)
            all_x = np.arange(0, (x1 - x0) - ww + 1)
            cy = np.r_[np.full(len(all_x), same_y), rng.integers(ylo, yhi + 1, candidates)]
            cx = np.r_[all_x, rng.integers(0, (x1 - x0) - ww + 1, candidates)]
            patches = np.stack([src[y:y + wh, x:x + ww] for y, x in zip(cy, cx)])
            d_known = ((patches - target[None]) ** 2).sum(-1)
            d_guide = ((patches - gwin[None]) ** 2).sum(-1)
            nk = max(1, kmask.sum())
            nb = max(1, bmask.sum())
            cost = (d_known * kmask).sum((1, 2)) / nk + guide_weight * (d_guide * bmask).sum((1, 2)) / nb
            pen = np.array([uses.get((int(y), int(x)), 0) for y, x in zip(cy, cx)], np.float32)
            cost = cost * (1 + reuse_penalty * pen)
            best = int(cost.argmin())
            if kmask.any() and (d_known[best] * kmask).sum() / nk / 3 > max_seam_error:
                known[wy0:wy1, wx0:wx1] |= bmask  # nothing fits (object cut by the border): keep LaMa
                continue
            uses[(int(cy[best]), int(cx[best]))] = uses.get((int(cy[best]), int(cx[best])), 0) + 1
            p = patches[best]
            take = bmask.astype(np.float32)
            err = ((p - target) ** 2).sum(-1)
            # vertical overlap on the inner side
            ov = min(overlap, ww)
            if side == "L":
                vs = slice(ww - ov, ww)
            else:
                vs = slice(0, ov)
            if kmask[:, vs].any():
                path = _min_cut(err[:, vs], axis=1)
                for r in range(wh):
                    c = np.arange(ov)
                    inner = c > path[r] if side == "L" else c < path[r]
                    take[r, vs][inner & kmask[r, vs]] = 0
                    take[r, vs][~inner & bmask[r, vs]] = 1
            oh = min(overlap, wh)
            if ty > 0 and kmask[:oh].any():
                path = _min_cut(err[:oh], axis=0)
                for c in range(ww):
                    above = np.arange(oh) < path[c]
                    take[:oh, c][above & kmask[:oh, c]] = 0
            take *= band_mask[wy0:wy1, wx0:wx1]  # never write outside the band
            out[wy0:wy1, wx0:wx1] = p * take[..., None] + target * (1 - take[..., None])
            known[wy0:wy1, wx0:wx1] |= bmask
    res = np.where(band_mask[..., None], out, wide.astype(np.float32))
    return np.clip(res + 0.5, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ recipes for leftover scenes
def recipe_rows(wide, band_mask, src_box, fade=0.35, seed=1):
    """Row-by-row continuation of the border colour, fading outwards, with the grain of the
    original mirrored: fog, snow, sky, flat walls. No repeated blocks."""
    rng = np.random.default_rng(seed)
    out = wide.astype(np.float32).copy()
    x0, x1 = src_box
    h, W = band_mask.shape
    for side in ("L", "R"):
        cols = np.where(band_mask[:, :x0].any(0))[0] if side == "L" else np.where(band_mask[:, x1:].any(0))[0] + x1
        if not len(cols):
            continue
        n = len(cols)
        edge = out[:, x0:x0 + 6].mean(1) if side == "L" else out[:, x1 - 6:x1].mean(1)
        # grain: the original mirrored at the border, minus its local mean
        g_src = out[:, x0:x0 + n][:, ::-1] if side == "L" else out[:, x1 - n:x1][:, ::-1]
        g_mean = np.asarray(Image.fromarray(np.clip(g_src, 0, 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(4)), np.float32)
        grain = g_src - g_mean
        order = cols[::-1] if side == "L" else cols
        for k, c in enumerate(order):
            t = (k + 1) / n
            smooth = np.asarray(Image.fromarray(np.clip(edge[:, None, :], 0, 255).astype(np.uint8))
                                .filter(ImageFilter.GaussianBlur(1 + 6 * t)), np.float32)[:, 0]
            val = smooth + grain[:, k] * (1 - fade * t) + rng.normal(0, 0.5, smooth.shape)
            out[:, c] = np.where(band_mask[:, c:c + 1], val, out[:, c])
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def recipe_shift(wide, band_mask, src_box, dx=40, dy=0, slope=0.0, join=4):
    """Copy of the original texture taken `dx` px further inside (at least the band width),
    with a height correction `dy` and a `slope` (px per column) for linear elements (rails,
    ridges), and a mirrored join over `join` columns at the border."""
    out = wide.astype(np.float32).copy()
    src = wide.astype(np.float32)
    x0, x1 = src_box
    for c in np.where(band_mask.any(0))[0]:
        left = c < x0
        dist = (x0 - c) if left else (c - x1 + 1)
        n = int(band_mask[:, :x0].any(0).sum()) if left else int(band_mask[:, x1:].any(0).sum())
        d = max(dx, n)
        sc = min(x1 - 1, c + d) if left else max(x0, c - d)
        col = np.roll(src[:, sc], int(round(dy + slope * dist)), axis=0)
        if dist <= join:
            mirror = src[:, x0 + dist - 1] if left else src[:, x1 - dist]
            t = dist / (join + 1)
            col = mirror * (1 - t) + col * t
        out[:, c] = np.where(band_mask[:, c:c + 1], col, out[:, c])
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ checks
def band_check(img, left, right, edge=8):
    """Per band, against the border columns of the original area (img is the full 16:9 picture,
    left/right the band widths in its pixels). A FILTER only: it also rejects good bands that
    are just darker or lighter than the border, so the eye decides on the sheets."""
    a = np.asarray(img.convert("RGB") if isinstance(img, Image.Image) else img)
    L = _lum(a)
    h, W = L.shape
    res = {}
    for side, band, ref in (("left", L[:, :left], L[:, left:left + edge]),
                            ("right", L[:, W - right:], L[:, W - right - edge:W - right])):
        if band.size == 0:
            continue
        white = float((band > 215).mean() - (ref > 215).mean())
        rmean = float(ref.mean())
        dl = abs(float(band.mean()) - rmean) / max(rmean, 1.0)
        reasons = []
        if white > 0.12:
            reasons.append(f"pixel bianchi +{white:.0%}")
        if dl > 0.18:
            reasons.append(f"luminosità diversa del {dl:.0%}")
        if rmean < 40 and float(ref.std()) < 12 and float(band.std()) - float(ref.std()) > 10:
            reasons.append("macchie chiare su bordo scuro (firme, schizzi)")
        res[side] = {"ok": not reasons, "reasons": reasons, "white": round(white, 3), "lum_delta": round(dl, 3)}
    res["ok"] = all(v["ok"] for k, v in res.items() if isinstance(v, dict))
    return res


def _hf(L):
    blur = np.asarray(Image.fromarray(np.clip(L, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)), np.float32)
    return np.abs(L - blur)


def sharpness_index(img, left, right):
    """High-frequency energy of each band divided by that of the centre strip next to it
    (3 band widths). Below 0.6 the band looks blurred. None for dark or flat scenes."""
    a = np.asarray(img.convert("RGB") if isinstance(img, Image.Image) else img)
    L = _lum(a)
    H = _hf(L)
    h, W = L.shape
    out = {}
    for side, n in (("left", left), ("right", right)):
        if n <= 0:
            continue
        if side == "left":
            band, cen, cl = H[:, :n], H[:, n:n + 3 * n], L[:, n:n + 3 * n]
        else:
            band, cen, cl = H[:, W - n:], H[:, W - 4 * n:W - n], L[:, W - 4 * n:W - n]
        ce = float(cen.mean())
        if ce < 1.0 or float(cl.mean()) < 30:
            out[side] = None
        else:
            out[side] = round(float(band.mean()) / ce, 3)
    return out


def unsharp_band(img, left, right, target=0.8, threshold=2.0, ramp=12, amounts=(0.3, 0.6, 1.0, 1.5, 2.0, 3.0)):
    """Unsharp mask on the bands only, the smallest amount that reaches `target`: threshold of
    2 levels, overshoot clamped to the local min/max (no halos), fading over `ramp` px next to
    the centre. Returns (image, amount, index)."""
    a = np.asarray(img.convert("RGB") if isinstance(img, Image.Image) else img).astype(np.float32)
    h, W = a.shape[:2]
    pil = Image.fromarray(a.astype(np.uint8))
    blur = np.asarray(pil.filter(ImageFilter.GaussianBlur(1.5)), np.float32)
    lo = np.asarray(pil.filter(ImageFilter.MinFilter(3)), np.float32)
    hi = np.asarray(pil.filter(ImageFilter.MaxFilter(3)), np.float32)
    wgt = np.zeros(W, np.float32)
    if left:
        wgt[:left] = 1
        wgt[max(0, left - ramp):left] = np.linspace(1, 0, min(ramp, left), endpoint=False)
    if right:
        wgt[W - right:] = 1
        wgt[W - right:W - right + min(ramp, right)] = np.linspace(0, 1, min(ramp, right), endpoint=False)
    detail = a - blur
    detail[np.abs(detail) < threshold] = 0
    before = sharpness_index(pil, left, right)
    vals = [v for v in before.values() if v is not None]
    if not vals or min(vals) >= target:
        return pil, 0.0, before
    best = (pil, 0.0, before)
    for k in amounts:
        s = np.clip(a + k * detail, lo, hi)
        res = a * (1 - wgt[None, :, None]) + s * wgt[None, :, None]
        im = Image.fromarray(np.clip(res + 0.5, 0, 255).astype(np.uint8))
        idx = sharpness_index(im, left, right)
        best = (im, k, idx)
        if all(v is None or v >= target for v in idx.values()):
            break
    return best
