"""16:9 planning: geometry, scene classification, side extensions, decisions."""
import datetime as _dt
import json
import math
import os
import re
import shutil

import numpy as np
from PIL import Image, ImageFilter

from . import bands, comfy, imaging, rawframe

UI_HINTS = re.compile(r"(menu|map|mappa|inv|intro|title|titolo|credits|crediti|logo|slide|option)", re.I)


def geometry(screen_w, screen_h, par=1.0, aspect=(16, 9)):
    """Viewport width in original pixels and the (symmetric) extension per side.

    par is the vertical stretch the remaster gives each pixel: 1.0 = square pixels (default:
    640x400 -> 36 px per side); another value ONLY if the game was conceived for a display
    that stretched its pixels (release date, target platform, devices of the time: see
    platforms.pixel_aspect), e.g. 1.2 for a 320x200 picture made for a 4:3 CRT.
    """
    target = screen_h * par * aspect[0] / aspect[1]
    side = max(0, int(math.ceil((target - screen_w) / 2 - 1e-9)))
    return {"screen": [screen_w, screen_h], "par": par, "viewport_w": screen_w + 2 * side,
            "extend_total": 2 * side, "left": side, "right": side}


def _load(path):
    if path.endswith(".raw"):
        return rawframe.read_raw(path).rgb()
    return Image.open(path).convert("RGB")


def edge_features(img: Image.Image, strip: int):
    f = imaging.to_f(img)
    lum = f @ np.array([0.299, 0.587, 0.114])
    h, w = lum.shape
    strip = max(4, min(strip, w // 4))
    gy, gx = np.gradient(lum)
    feats = {}
    for side, sl in (("left", slice(0, strip)), ("right", slice(w - strip, w))):
        L, GX, GY, F = lum[:, sl], gx[:, sl], gy[:, sl], f[:, sl]
        top = slice(0, h // 3)
        # sky: smooth, bright-ish top band with blue dominance or very low texture
        sky_smooth = float((np.hypot(GX[top], GY[top]) < 0.02).mean())
        blue = float((F[top][..., 2] > F[top][..., 0] + 0.03).mean())
        # long vertical edges (walls, door frames): columns with strong |gx| along many rows
        col_vert = (np.abs(GX) > 0.08).mean(axis=0)
        vertical = float(col_vert.max())
        # horizontal structures running out of the frame (horizon, road, rooftops)
        row_horiz = (np.abs(GY) > 0.08).mean(axis=1)
        horizontal = float((row_horiz > 0.6).mean())
        texture = float(np.hypot(GX, GY).mean())
        feats[side] = {"sky": round(sky_smooth * (0.5 + 0.5 * blue), 3), "vertical": round(vertical, 3),
                       "horizontal": round(horizontal, 3), "texture": round(texture, 4)}
    return feats


def classify_scene(img, screen_w, screen_h, geo, name=""):
    w, h = img.size
    if UI_HINTS.search(name):
        return "ui-fixed", 0.5, "nome da schermata di interfaccia"
    if w >= geo["viewport_w"]:
        return "scroll-wide", 0.95, f"fondale largo {w}px ≥ viewport {geo['viewport_w']}px"
    if w > screen_w:
        return "scroll-narrow", 0.8, f"fondale {w}px tra schermo {screen_w} e viewport {geo['viewport_w']}"
    feats = edge_features(img, max(8, geo["left"]))
    open_score = 0.0
    for s in ("left", "right"):
        e = feats[s]
        open_score += 1.2 * e["sky"] + 0.8 * e["horizontal"] - 1.5 * max(0.0, e["vertical"] - 0.35)
    open_score /= 2
    if open_score > 0.45:
        return "open-static", min(0.9, 0.5 + open_score / 2), f"bordi aperti (cielo/orizzonte), punteggio {open_score:.2f}"
    if open_score < 0.15:
        return "closed-static", min(0.9, 0.6 + (0.15 - open_score)), f"bordi chiusi (pareti/verticali), punteggio {open_score:.2f}"
    return "closed-static", 0.4, f"incerto (punteggio {open_score:.2f}): verificare a vista"


def classify(src_dir, screen_w, screen_h, par=1.0, out_path=None):
    geo = geometry(screen_w, screen_h, par)
    scenes = []
    for name in sorted(os.listdir(src_dir)):
        p = os.path.join(src_dir, name)
        if not os.path.isfile(p) or not name.lower().endswith((".raw", ".png", ".bmp", ".gif", ".jpg")):
            continue
        scene = os.path.splitext(name)[0]
        if name.lower().endswith(".png") and os.path.exists(os.path.join(src_dir, scene + ".raw")):
            continue
        img = _load(p)
        cls, conf, why = classify_scene(img, screen_w, screen_h, geo, scene)
        scenes.append({"scene": scene, "source": p, "size": list(img.size), "class": cls,
                       "confidence": round(conf, 2), "why": why, "verified": False})
    plan = {"geometry": geo, "scenes": scenes,
            "counts": {c: sum(1 for s in scenes if s["class"] == c) for c in
                       ("scroll-wide", "scroll-narrow", "closed-static", "open-static", "ui-fixed")}}
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
    return plan


def border_variant(img: Image.Image, left: int, right: int, darken=0.45):
    """Pillarbox in keeping with the picture: blurred, darkened stretch of the edges."""
    w, h = img.size
    out = Image.new("RGB", (w + left + right, h))
    if left:
        l = img.crop((0, 0, max(1, w // 6), h)).resize((left, h)).filter(ImageFilter.GaussianBlur(max(2, left // 6)))
        out.paste(Image.eval(l, lambda v: int(v * darken)), (0, 0))
    if right:
        r = img.crop((w - max(1, w // 6), 0, w, h)).resize((right, h)).filter(ImageFilter.GaussianBlur(max(2, right // 6)))
        out.paste(Image.eval(r, lambda v: int(v * darken)), (left + w, 0))
    out.paste(img, (left, 0))
    return out


def load_lama(path):
    """LaMa inpainting model (TorchScript big-lama.pt, e.g. from simple-lama-inpainting releases)."""
    import torch  # optional dependency
    model = torch.jit.load(path, map_location="cpu").eval()

    def fill(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        ph, pw = (8 - h % 8) % 8, (8 - w % 8) % 8
        im = np.pad(img, ((0, ph), (0, pw), (0, 0)), mode="reflect")
        m = np.pad(mask, ((0, ph), (0, pw)), mode="constant", constant_values=1)
        t = torch.from_numpy(im).permute(2, 0, 1)[None].float() / 255
        tm = torch.from_numpy(m)[None, None].float()
        with torch.inference_mode():
            out = model(t, tm)[0].permute(1, 2, 0).clamp(0, 1).numpy()
        return (out[:h, :w] * 255 + 0.5).astype(np.uint8)
    return fill


def blank_borders(src: np.ndarray, limit=20):
    """Black/blank columns at the borders of the original (repainted with the bands)."""
    lum = src.astype(np.float32).mean(2)

    def count(cols):
        n = 0
        for c in cols:
            if lum[:, c].mean() < 18 and lum[:, c].std() < 12:
                n += 1
            else:
                break
        return min(n, limit)
    w = src.shape[1]
    return count(range(w)), count(range(w - 1, -1, -1))


def extend_inpaint(orig: Image.Image, hd: Image.Image, left: int, right: int, scale: int, fill,
                   upscale=None, context=24, ramp=8, refine=None):
    """16:9 bands painted at the ORIGINAL resolution by an inpainting
    model (LaMa works best at the scale the art was drawn), then upscaled with the same
    upscaler as the HD background, with `context` original pixels and a `ramp` blend into
    the HD centre. Black border columns of the original are repainted too. Sharp, not blurred.
    `upscale(img, k)` defaults to scalers.upscale_rgb (model from REMASTER_MODEL_BG).
    `fill(img, mask)` paints the bands (LaMa, a recipe, or the optional paid outpainting);
    `refine(wide, band_mask, (x0, x1))` reworks them at 1x before upscaling (image quilting).
    left/right are in original pixels; the result is (w + left + right) * scale wide."""
    from . import scalers
    up = upscale or (lambda im, k: scalers.upscale_rgb(im, k))
    src = np.asarray(orig.convert("RGB"))
    h, w = src.shape[:2]
    S = scale
    hd_a = np.asarray(hd.convert("RGB"), np.float32)
    if hd_a.shape[1] != w * S or hd_a.shape[0] != h * S:
        raise ValueError("HD background must be the original size times the scale")
    bl, br = blank_borders(src)
    W = w + left + right
    wide = np.zeros((h, W, 3), np.uint8)
    wide[:, left:left + w] = src
    mask = np.zeros((h, W), np.float32)
    mask[:, :left + bl] = 1
    mask[:, left + w - br:] = 1
    wide = np.array(fill(wide, mask), np.uint8)
    wide[:, left + bl:left + w - br] = src[:, bl:w - br]
    if refine is not None:
        wide = np.array(refine(wide, mask > 0, (left + bl, left + w - br)), np.uint8)
        wide[:, left + bl:left + w - br] = src[:, bl:w - br]
    out = np.zeros((h * S, W * S, 3), np.float32)
    out[:, left * S:(left + w) * S] = hd_a
    for is_left, n in ((True, left), (False, right)):
        if n <= 0 and not (bl if is_left else br):
            continue
        x0, x1 = (0, left + bl + context) if is_left else (left + w - br - context, W)
        x0, x1 = max(0, x0), min(W, x1)
        strip = Image.fromarray(wide[:, x0:x1])
        big = np.asarray(up(strip, S).convert("RGB").resize(((x1 - x0) * S, h * S), Image.LANCZOS), np.float32)
        cols = np.arange((x1 - x0) * S)
        r = S * ramp
        if is_left:
            wgt = np.clip(1 - (cols - (left + bl - x0) * S) / r, 0, 1)
        else:
            wgt = np.clip(1 - ((left + w - br - x0) * S - cols) / r, 0, 1)
        dst = out[:, x0 * S:x1 * S]
        out[:, x0 * S:x1 * S] = big * wgt[None, :, None] + dst * (1 - wgt[None, :, None])
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGB")


def extend(hd_img: Image.Image, left: int, right: int, recipe=None, seeds=(11, 22, 33)):
    """Outpainted variants (ComfyUI) at HD scale; the original area is pasted back untouched."""
    variants = []
    if recipe and comfy.available():
        for s in seeds:
            out = comfy.outpaint(hd_img, left, right, recipe, s)
            out = out.resize((hd_img.width + left + right, hd_img.height), Image.LANCZOS)
            out.paste(hd_img, (left, 0))
            variants.append(("ai", s, out))
    variants.append(("borders", None, border_variant(hd_img, left, right)))
    return variants


def _recipe_fill(kind, **kw):
    """Local recipe as a `fill`: LaMa-free continuation for fog/sky (rows) or shifted texture."""
    def fill(img, mask):
        m = mask > 0
        cols = np.where(~m.all(0))[0]
        box = (int(cols.min()), int(cols.max()) + 1)
        if kind == "rows":
            return bands.recipe_rows(img, m, box, **kw)
        if kind == "shift":
            return bands.recipe_shift(img, m, box, **kw)
        raise ValueError(f"ricetta sconosciuta {kind}")
    return fill


def check_variant(img, left_px, right_px):
    """Automatic checks stored next to every variant (a filter, the eye decides)."""
    return {"band_check": bands.band_check(img, left_px, right_px),
            "sharpness": bands.sharpness_index(img, left_px, right_px)}


def make_extensions(plan_path, hd_dir, out_dir, scale, recipe=None, seeds=(11, 22, 33), lama=None,
                    quilting=True, sharpen=True, paid_fill=None, recipes=None, only=None, model=None):
    """Variants per scene, with the local methods of the reference project first:
      v-lama     LaMa at 1x + upscaler                     (if `lama`)
      v-quilt    LaMa + image quilting from the original   (if `lama` and quilting)
      v-<recipe> local recipe for the scene (recipes={scene: {"kind": "rows"|"shift", ...}})
      v-fal<n>   OPTIONAL paid masked outpainting           (only with `paid_fill`, already approved)
      ai         generative outpainting with ComfyUI        (if a recipe and ComfyUI)
      borders    pillarbox in keeping with the picture
    Every inventive variant gets band_check + sharpness index; blurred bands are sharpened.
    `model` is the upscaler of the bands: the same as the HD backgrounds (default REMASTER_MODEL_BG),
    so bands and centre share the same texture."""
    from . import scalers
    fill = load_lama(lama) if isinstance(lama, str) else lama
    up = (lambda im, k: scalers.upscale_rgb(im, k, model=model, kind="bg"))
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    geo = plan["geometry"]
    os.makedirs(out_dir, exist_ok=True)
    recipes = recipes or {}
    for s in plan["scenes"]:
        if s["class"] not in ("open-static", "scroll-narrow", "closed-static"):
            continue
        if only and s["scene"] not in only:
            continue
        hd_path = None
        for ext in (".png", ".jpg"):
            if os.path.exists(os.path.join(hd_dir, s["scene"] + ext)):
                hd_path = os.path.join(hd_dir, s["scene"] + ext)
        img = Image.open(hd_path).convert("RGB") if hd_path else _load(s["source"]).resize(
            (s["size"][0] * scale, s["size"][1] * scale), Image.NEAREST)
        need = max(0, geo["viewport_w"] - s["size"][0])
        lw, rw = need // 2, need - need // 2
        left_px, right_px = lw * scale, rw * scale
        inventable = s["class"] in ("open-static", "scroll-narrow")
        use_recipe = recipe if inventable else None
        previous = [v for v in s.get("variants", []) if os.path.exists(os.path.join(out_dir, v["file"]))]
        s["variants"] = []
        orig = _load(s["source"]) if inventable else None

        def save(tag, im, kind, seed=None):
            info = None
            if sharpen and kind != "borders":
                im, amount, _idx = bands.unsharp_band(im, left_px, right_px)
                info = amount
            vname = f"{s['scene']}.{tag}.png"
            im.save(os.path.join(out_dir, vname))
            v = {"file": vname, "kind": kind, "seed": seed}
            if kind != "borders":
                v["checks"] = check_variant(im, left_px, right_px)
                v["unsharp"] = info
            s["variants"].append(v)
        if inventable and fill is not None:
            save("v-lama", extend_inpaint(orig, img, lw, rw, scale, fill, upscale=up), "inpaint")
            if quilting:
                save("v-quilt", extend_inpaint(orig, img, lw, rw, scale, fill, upscale=up,
                                               refine=lambda w_, m_, b_: bands.quilt(w_, m_, b_)), "quilt")
        if inventable and s["scene"] in recipes:
            r = dict(recipes[s["scene"]])
            kind = r.pop("kind")
            save(f"v-{kind}", extend_inpaint(orig, img, lw, rw, scale, _recipe_fill(kind, **r), upscale=up),
                 f"recipe-{kind}")
        if inventable and paid_fill is not None:
            k = 1  # every paid attempt kept under its own name: v-fal1, v-fal2
            while os.path.exists(os.path.join(out_dir, f"{s['scene']}.v-fal{k}.png")):
                k += 1
            save(f"v-fal{k}", extend_inpaint(orig, img, lw, rw, scale, paid_fill, upscale=up), "fal")
        n = 0
        for kind, seed, im in extend(img, left_px, right_px, use_recipe, seeds):
            if kind == "ai":
                n += 1
                save(f"v{n}", im, "ai", seed)
            else:
                save("borders", im, "borders")
        # variants made by earlier runs (e.g. local ones before a fal.ai run) stay in the gallery
        made = {v["file"] for v in s["variants"]}
        kept = [v for v in previous if v["file"] not in made]
        s["variants"] = [v for v in kept + s["variants"] if v["kind"] != "borders"] + \
            [v for v in s["variants"] + kept if v["kind"] == "borders"][:1]
        s["extend"] = {"left": lw, "right": rw}
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return plan


def apply_decisions(plan_path, decisions_path, variants_dir, bg_out_dir):
    """decisions: {scene: "v-lama"|"v-quilt"|"v-rows"|"v-fal1"|"v1"|"borders"|"4:3"|"redo"}"""
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    with open(decisions_path, encoding="utf-8") as f:
        decisions = json.load(f)
    os.makedirs(bg_out_dir, exist_ok=True)
    today = _dt.date.today().isoformat()
    applied, redo = [], []
    for s in plan["scenes"]:
        choice = decisions.get(s["scene"])
        if not choice:
            continue
        if choice == "redo":
            redo.append(s["scene"])
            continue
        meta = {"class": s["class"], "approved": today, "choice": choice}
        if s["class"] == "scroll-wide":
            meta.update({"left": 0, "right": 0, "camera": "clamp"})
        elif choice == "4:3":
            meta.update({"left": 0, "right": 0, "camera": "center", "pillarbox": "black"})
        else:
            v = next((v for v in s.get("variants", []) if v["file"].endswith(f".{choice}.png")), None)
            if v is None:
                raise ValueError(f"{s['scene']}: variante {choice} inesistente")
            shutil.copyfile(os.path.join(variants_dir, v["file"]), os.path.join(bg_out_dir, s["scene"] + ".wide.png"))
            meta.update({**s["extend"], "camera": "center", "kind": v["kind"], "seed": v["seed"]})
        with open(os.path.join(bg_out_dir, s["scene"] + ".wide.json"), "w") as f:
            json.dump(meta, f)
        s["decision"] = choice
        applied.append(s["scene"])
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return {"applied": applied, "redo": redo}
