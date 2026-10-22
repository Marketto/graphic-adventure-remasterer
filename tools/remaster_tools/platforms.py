"""Target platform of the original release: how its pixels were shown on the displays of the
time (pixel aspect) and which reliable emulator or VM reproduces it for the comparison tests.

The pixel aspect is corrected ONLY when the game was conceived for a display that stretched
its pixels: that depends on release date, target platform and the devices of the time, not on
the resolution alone. Here `stretch` is the vertical stretch factor the original display
applied to one pixel (1.2 = a 320x200 picture filling a 4:3 CRT); 1.0 = square pixels.
The table gives a candidate with reasons; the art decides (round objects, faces, text drawn
in the picture) with `aspect_sheet`, and the user confirms.
"""
import math
import os

import numpy as np

from PIL import Image

# (platform, width, height) -> (stretch, display of the time, how sure)
_MODES = [
    ("dos", 320, 200, 1.2, "VGA/MCGA 13h o EGA a 200 righe su monitor CRT 4:3", "alta"),
    ("dos", 640, 200, 2.4, "CGA/EGA ad alta risoluzione su CRT 4:3", "alta"),
    ("dos", 640, 350, 1.37, "EGA 640x350 su CRT 4:3", "alta"),
    ("dos", 640, 400, 1.2, "SVGA 640x400 su CRT 4:3 (ma spesso arte digitalizzata o renderizzata a pixel quadrati: verifica)", "media"),
    ("dos", 320, 240, 1.0, "Mode X 320x240: pixel quadrati su 4:3", "alta"),
    ("dos", 640, 480, 1.0, "VGA/SVGA 640x480: pixel quadrati", "alta"),
    ("windows", 640, 480, 1.0, "Windows a 640x480 o più: pixel quadrati", "alta"),
    ("windows", 800, 600, 1.0, "Windows SVGA: pixel quadrati", "alta"),
    ("mac", 512, 342, 1.0, "Mac compatti: pixel quadrati", "alta"),
    ("mac", 640, 480, 1.0, "Mac a colori: pixel quadrati", "alta"),
    ("amiga-pal", 320, 256, 1.0, "Amiga PAL lowres: pixel quasi quadrati", "media"),
    ("amiga-pal", 320, 200, 1.0, "gioco NTSC-safe su Amiga PAL: pixel quasi quadrati, bordo nero sotto", "media"),
    ("amiga-ntsc", 320, 200, 1.2, "Amiga NTSC: pixel alti come su un TV 4:3", "media"),
    ("amiga-pal", 640, 256, 0.5, "Amiga hires non interlacciato: pixel larghi la metà", "alta"),
    ("amiga-pal", 640, 512, 1.0, "Amiga hires interlacciato", "media"),
    ("atari-st", 320, 200, 1.2, "Atari ST lowres su monitor/TV 4:3", "alta"),
    ("atari-st", 640, 400, 1.0, "Atari ST monocromatico SM124: pixel quadrati", "alta"),
    ("pc-98", 640, 400, 1.2, "PC-98 640x400 su monitor 4:3", "media"),
    ("fm-towns", 640, 480, 1.0, "FM Towns 640x480: pixel quadrati", "alta"),
]

# reference to compare timings, input and look against the original
EMULATORS = {
    "dos": [("DOSBox Staging / DOSBox-X", "riferimento principale; ritracce VGA a 70 Hz, cicli fissi; Xvfb + ffmpeg x11grab + xdotool"),
            ("86Box / PCem", "PC d'epoca emulato a livello di hardware, quando i tempi dipendono dalla CPU o dalla scheda video")],
    "windows3": [("86Box / PCem con Windows 3.1", "macchina virtuale d'epoca: tempi più fedeli"),
                 ("DOSBox-X con Windows 3.1", "più semplice da automatizzare")],
    "windows": [("86Box / PCem o QEMU/VirtualBox con Windows 95/98", "macchina virtuale: tempi e driver DirectX/WinG dell'epoca"),
                ("Wine", "comodo e automatizzabile, ma i tempi dipendono dall'host: va bene per logica e testi, non per misurare la velocità")],
    "mac": [("Basilisk II / SheepShaver / Mini vMac", "richiede la ROM del Mac dell'utente")],
    "amiga-pal": [("WinUAE / FS-UAE (cycle-exact)", "richiede le ROM Kickstart dell'utente (o AROS per prove di sola logica)")],
    "amiga-ntsc": [("WinUAE / FS-UAE (cycle-exact, modo NTSC)", "richiede le ROM Kickstart dell'utente")],
    "atari-st": [("Hatari", "EmuTOS libero; TOS originale dall'utente se serve")],
    "pc-98": [("Neko Project II kai / np21w", "richiede le ROM dell'utente")],
    "fm-towns": [("MAME / Tsugaru", "richiede le ROM dell'utente")],
}
ALIASES = {"pc": "dos", "msdos": "dos", "ms-dos": "dos", "win": "windows", "win95": "windows", "win9x": "windows",
           "windows95": "windows", "win31": "windows3", "windows31": "windows3", "amiga": "amiga-pal",
           "st": "atari-st", "atari": "atari-st", "macintosh": "mac", "pc98": "pc-98"}


def norm_platform(p):
    p = (p or "").strip().lower()
    return ALIASES.get(p, p)


def pixel_aspect(platform, width, height, year=None, art=None):
    """Candidate vertical stretch for (platform, resolution, year) with the reasons.
    art: "pixel" (drawn by hand on the target display), "digitized" (scans, photos, 3D renders
    made at square pixels), or None when unknown."""
    plat = norm_platform(platform)
    reasons = []
    hit = next((m for m in _MODES if m[0] == plat and m[1] == width and m[2] == height), None)
    if hit is None and plat in ("windows3", "windows", "mac", "fm-towns"):
        hit = (plat, width, height, 1.0, "piattaforma con pixel quadrati", "alta")
    if hit is None:
        stretch = round((width / height) / (4 / 3), 3)
        reasons.append(f"modo {width}x{height} su {plat or '?'} non in tabella: se riempiva un 4:3, "
                       f"il pixel era allungato di {stretch}; verificare sui documenti dell'epoca")
        sure = "bassa"
    else:
        stretch, why, sure = hit[3], hit[4], hit[5]
        reasons.append(why)
    if year:
        if year >= 1997 and plat == "dos" and stretch != 1.0:
            reasons.append("uscita tarda: molti giochi DOS di fine decennio erano pensati per 640x480 o per "
                           "arte a pixel quadrati")
            sure = "bassa" if sure != "alta" else "media"
        if year < 1987 and plat == "dos":
            reasons.append("prima della VGA: CGA/EGA, controlla il modo grafico effettivo")
    if art == "digitized" and stretch != 1.0:
        reasons.append("arte digitalizzata o renderizzata: se fu acquisita a pixel quadrati e mostrata così, "
                       "la versione fedele è quadrata; se fu schiacciata apposta per il monitor 4:3, va "
                       "allungata. Non si deduce dal tipo di arte: decide il foglio di confronto")
        sure = "bassa"
    elif art == "pixel" and stretch != 1.0:
        reasons.append("disegnata a mano sul monitor dell'epoca: l'artista vedeva i pixel allungati")
    return {"platform": plat, "mode": [width, height], "stretch": stretch, "confidence": sure,
            "correct": stretch != 1.0, "reasons": reasons,
            "check": "confronta `aspect_sheet` su 3-4 scene con oggetti tondi, volti, ruote, orologi, lune "
                     "o testo disegnato: la versione giusta li mostra rotondi e proporzionati"}


def reference_emulators(platform):
    plat = norm_platform(platform)
    rows = EMULATORS.get(plat)
    if not rows:
        return {"platform": plat, "emulators": [],
                "note": "piattaforma non in tabella: cerca l'emulatore più accurato e mantenuto (MAME copre molte "
                        "macchine), con le ROM/BIOS fornite dall'utente"}
    return {"platform": plat, "emulators": [{"name": n, "note": t} for n, t in rows],
            "rules": ["stessa versione del gioco che si rimasterizza (lingua, floppy/CD)",
                      "prima scelta: l'emulatore più fedele ai tempi della macchina; una VM o un livello di "
                      "compatibilità (Wine) solo per ciò che non dipende dai tempi",
                      "registrazione sotto Xvfb con ffmpeg x11grab a 60 fps; input con xdotool; poi "
                      "`rstool.py engine timing <video>`",
                      "ROM, BIOS e sistemi operativi d'epoca li fornisce l'utente: non si scaricano"]}


def aspect_sheet(images, out_path, stretches=(1.0, 1.2), height=360):
    """Same scenes at each candidate stretch, side by side, to choose by eye."""
    rows = []
    for p in images:
        im = Image.open(p).convert("RGB")
        cells = []
        for s in stretches:
            h = height
            w = int(round(im.width * height / (im.height * s)))
            cells.append(im.resize((w, h), Image.LANCZOS))
        rows.append(cells)
    W = max(sum(c.width for c in r) + 16 * (len(r) - 1) for r in rows)
    H = sum(height + 28 for _ in rows)
    from PIL import ImageDraw
    sheet = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    y = 0
    for r, p in zip(rows, images):
        x = 0
        for c, s in zip(r, stretches):
            d.text((x + 4, y + 6), f"{os.path.basename(p)} — allungamento {s}", fill=(230, 230, 230))
            sheet.paste(c, (x, y + 24))
            x += c.width + 16
        y += height + 28
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path)
    return {"sheet": out_path, "stretches": list(stretches), "scenes": len(images)}


def _compose(images, grid):
    cols, rows = grid
    ims = [Image.open(p).convert("RGB") for p in images]
    if len(ims) != cols * rows:
        raise ValueError(f"--compose {cols}x{rows} vuole {cols * rows} immagini, ricevute {len(ims)}")
    w, h = max(i.width for i in ims), max(i.height for i in ims)
    out = Image.new("RGB", (w * cols, h * rows))
    for k, im in enumerate(ims):
        out.paste(im, ((k % cols) * w, (k // cols) * h))
    return out


def _largest_component(mask):
    try:
        from scipy import ndimage
        lab, n = ndimage.label(mask)
        if not n:
            return mask & False
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        return lab == (int(np.argmax(sizes)) + 1)
    except ImportError:  # small pictures: plain flood fill
        import collections
        seen = np.zeros_like(mask, dtype=bool)
        best = None
        for y, x in zip(*np.nonzero(mask)):
            if seen[y, x]:
                continue
            comp, q = [], collections.deque([(y, x)])
            seen[y, x] = True
            while q:
                cy, cx = q.popleft()
                comp.append((cy, cx))
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if best is None or len(comp) > len(best):
                best = comp
        out = np.zeros_like(mask, dtype=bool)
        if best:
            ys, xs = zip(*best)
            out[list(ys), list(xs)] = True
        return out


def aspect_measure(images, compose=None, box=None, color=None, tolerance=40, candidates=(1.0, 1.2), out_path=None):
    """Width/height of a shape that is ROUND in reality (a disc seen from above, a wheel, a
    moon, a round table), measured on the original pixels. A circle drawn for a display that
    stretched pixels by s measures w/h ≈ s. Decisive when the aspect sheet does not help
    (perspective views, documents).

    images: one picture, or several to compose (`compose`=(cols, rows), in reading order) when
    the shape is split between rooms. box: (x, y, w, h) around the shape. color: "#rrggbb" of the
    shape (pixels within `tolerance`); without it the shape is what differs from the colour of the
    box border. The largest connected region is measured: bounding box, second moments (ellipse
    fit) and how much it looks like an ellipse (filled area / ellipse area)."""
    img = _compose(images, compose) if compose else Image.open(images[0]).convert("RGB")
    a = np.asarray(img).astype(int)
    x0, y0 = 0, 0
    if box:
        x0, y0, bw, bh = box
        a = a[y0:y0 + bh, x0:x0 + bw]
    if color:
        c = np.array([int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)])
        mask = np.abs(a - c).sum(axis=2) <= tolerance
    else:
        border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
        vals, cnt = np.unique(border, axis=0, return_counts=True)
        bgc = vals[int(np.argmax(cnt))]
        mask = np.abs(a - bgc).sum(axis=2) > tolerance
    comp = _largest_component(mask)
    ys, xs = np.nonzero(comp)
    if len(xs) < 20:
        return {"error": "nessuna forma abbastanza grande: indica --box o --color"}
    bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    sx, sy = float(xs.std()), float(ys.std())
    ratio_bbox, ratio_mom = bw / bh, sx / sy if sy else 0.0
    fill = len(xs) / (math.pi / 4 * bw * bh)
    ratio = round((ratio_bbox + ratio_mom) / 2, 3)
    best = min(candidates, key=lambda s: abs(s - ratio))
    res = {"shape_px": [bw, bh], "origin": [int(xs.min()) + x0, int(ys.min()) + y0],
           "ratio_bbox": round(ratio_bbox, 3), "ratio_moments": round(ratio_mom, 3), "ratio": ratio,
           "ellipse_fill": round(fill, 3), "closest": best,
           "candidates": {str(s): round(abs(s - ratio), 3) for s in candidates},
           "note": ("forma piena ed ellittica: misura attendibile" if 0.9 <= fill <= 1.1 else
                    "la forma non è un'ellisse piena (anello, contorno o pezzi): controlla il ritaglio, "
                    "usa --box o --color, o misura un riquadro a mano")}
    if out_path:
        from PIL import ImageDraw
        vis = img.copy()
        d = ImageDraw.Draw(vis)
        d.rectangle([res["origin"][0], res["origin"][1], res["origin"][0] + bw - 1, res["origin"][1] + bh - 1],
                    outline=(255, 0, 255))
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        vis.save(out_path)
        res["image"] = out_path
    return res


# ---------------------------------------------------------------------------------------------
# Automatic pixel aspect: table candidate + shapes measured on the dump + manual measures.
# Rule of the suite: decide alone when the evidence is clear; ask the user only when in doubt.

_IMG_EXT = (".png", ".bmp", ".gif", ".tga", ".jpg", ".jpeg", ".webp")
CONF_RANK = {"bassa": 0, "media": 1, "alta": 2}


def _image_paths(evidence, limit=2000):
    paths = []
    for e in evidence or []:
        if os.path.isdir(e):
            for root, _dirs, files in sorted(os.walk(e)):
                paths += [os.path.join(root, f) for f in sorted(files) if f.lower().endswith(_IMG_EXT)]
        elif os.path.isfile(e) and e.lower().endswith(_IMG_EXT):
            paths.append(e)
    return paths[:limit]


def _rgb_array(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
        rgba = np.asarray(im.convert("RGBA"))
        return rgba[..., :3].astype(np.int32), rgba[..., 3] > 0
    return np.asarray(im.convert("RGB")).astype(np.int32), None


def _segmentations(rgb, opaque):
    """Label maps of the picture: exact colours, and colours after a 3x3 median and a 12-colour
    quantization (removes dithering and noise). Transparent pixels get their own label."""
    from scipy import ndimage
    flat = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    maps = [flat]
    sm = np.stack([ndimage.median_filter(rgb[..., k], size=3) for k in range(3)], axis=2).astype(np.uint8)
    q = np.asarray(Image.fromarray(sm, "RGB").quantize(12, method=Image.Quantize.MEDIANCUT)).astype(np.int64)
    maps.append(q)
    if opaque is not None:
        maps = [np.where(opaque, m, -1) for m in maps]
        maps.append(opaque.astype(np.int64))  # the silhouette of a sprite
    return maps


def _ellipse_fit_closed(filled):
    """IoU between a filled region and the axis-aligned ellipse with its second moments, the
    w/h ratio of that ellipse, and the tilt (None when tilted)."""
    yy, xx = np.nonzero(filled)
    cy, cx = yy.mean(), xx.mean()
    vy, vx = yy.var() + 1 / 12, xx.var() + 1 / 12
    cxy = ((yy - cy) * (xx - cx)).mean()
    if abs(cxy) > 0.08 * math.sqrt(vx * vy):
        return None
    ax, ay = 2 * math.sqrt(vx), 2 * math.sqrt(vy)
    gy, gx = np.mgrid[0:filled.shape[0], 0:filled.shape[1]]
    ell = ((gx - cx) / ax) ** 2 + ((gy - cy) / ay) ** 2 <= 1
    iou = (ell & filled).sum() / max(1, (ell | filled).sum())
    return iou, ax / ay


def _conic_fit(x, y):
    """Least squares axis-aligned ellipse A x² + C y² + D x + E y = 1 → (cx, cy, a, b) or None."""
    M = np.stack([x * x, y * y, x, y], axis=1)
    try:
        p, *_ = np.linalg.lstsq(M, np.ones_like(x), rcond=None)
    except np.linalg.LinAlgError:
        return None
    A, C, D, E = p
    if A <= 0 or C <= 0:
        return None
    cx, cy = -D / (2 * A), -E / (2 * C)
    F = 1 + D * D / (4 * A) + E * E / (4 * C)
    if F <= 0:
        return None
    return cx, cy, math.sqrt(F / A), math.sqrt(F / C)


def _arc_fit(xs, ys, W, H, rng, iters=150):
    """RANSAC: the longest elliptic arc (axis aligned) in a boundary. Returns (ratio, inliers,
    span in degrees, a, b) or None."""
    n = len(xs)
    if n < 40:
        return None
    best = None
    lim = 1.6 * max(W, H)
    for _ in range(iters):
        idx = rng.choice(n, 5, replace=False)
        f = _conic_fit(xs[idx], ys[idx])
        if not f:
            continue
        cx, cy, a, b = f
        if not (6 <= a <= lim and 6 <= b <= lim and 0.3 <= a / b <= 4):
            continue
        r = np.sqrt(((xs - cx) / a) ** 2 + ((ys - cy) / b) ** 2)
        inl = np.abs(r - 1) * min(a, b) < 0.9
        k = int(inl.sum())
        if best is None or k > best[0]:
            best = (k, inl)
    if best is None or best[0] < 40:
        return None
    inl = best[1]
    f = _conic_fit(xs[inl], ys[inl])
    if not f:
        return None
    cx, cy, a, b = f
    if not (6 <= a <= lim and 6 <= b <= lim):
        return None
    r = np.sqrt(((xs - cx) / a) ** 2 + ((ys - cy) / b) ** 2)
    inl = np.abs(r - 1) * min(a, b) < 0.9
    if inl.sum() < 40:
        return None
    ang = np.degrees(np.arctan2((ys[inl] - cy) / b, (xs[inl] - cx) / a)) % 360
    bins = np.zeros(36, bool)
    bins[(ang // 10).astype(int) % 36] = True
    span = int(bins.sum()) * 10
    if span < 80:
        return None
    return a / b, int(inl.sum()), span, a, b


def find_round_shapes(evidence, min_size=10, limit=2000, seed=0):
    """Shapes that look round in the dump (objects, icons, backgrounds), measured on the original
    pixels. kind: "ellipse" (filled), "ring" (with a hole), "arc" (part of a large circle cut by the
    picture edge, e.g. a map split between rooms). ratio = width/height: a circle drawn for a
    display that stretched pixels by s measures ≈ s; a circle seen in perspective measures more."""
    from scipy import ndimage
    rng = np.random.default_rng(seed)
    found = []
    for p in _image_paths(evidence, limit):
        try:
            rgb, opaque = _rgb_array(p)
        except OSError:
            continue
        H, W = rgb.shape[:2]
        if H < min_size or W < min_size:
            continue
        mine = []
        for lv, lab_src in enumerate(_segmentations(rgb, opaque)):
            vals, cnts = np.unique(lab_src, return_counts=True)
            for v in vals[cnts >= 40]:
                if v < 0:
                    continue
                lab, n = ndimage.label(lab_src == v)
                for i, sl in enumerate(ndimage.find_objects(lab)):
                    ys, xs = sl
                    bh, bw = ys.stop - ys.start, xs.stop - xs.start
                    if bh < min_size or bw < min_size or (bw >= W - 1 and bh >= H - 1):
                        continue
                    comp = lab[sl] == (i + 1)
                    area = int(comp.sum())
                    if area < 40:
                        continue
                    border = ys.start == 0 or xs.start == 0 or ys.stop == H or xs.stop == W
                    if not border and bw <= 0.9 * W and bh <= 0.9 * H:
                        filled = ndimage.binary_fill_holes(comp)
                        fit = _ellipse_fit_closed(filled)
                        if fit and fit[0] >= 0.9:
                            ratio = round((fit[1] + bw / bh) / 2, 3)
                            mine.append({"file": p, "kind": "ring" if area < 0.8 * filled.sum() else "ellipse",
                                         "box": [int(xs.start), int(ys.start), int(bw), int(bh)], "ratio": ratio,
                                         "quality": round(float(fit[0]), 3), "size": int(min(bw, bh))})
                            continue
                    if area >= 200 and max(bw, bh) >= 30:
                        edge = comp & ~ndimage.binary_erosion(comp)
                        ey, ex = np.nonzero(edge)
                        ex, ey = ex + xs.start, ey + ys.start
                        keep = (ex > 0) & (ey > 0) & (ex < W - 1) & (ey < H - 1)
                        ex, ey = ex[keep].astype(float), ey[keep].astype(float)
                        arc = _arc_fit(ex, ey, W, H, rng)
                        if arc:
                            ratio, k, span, a, b = arc
                            mine.append({"file": p, "kind": "arc", "box": [int(xs.start), int(ys.start), int(bw), int(bh)],
                                         "ratio": round(float(ratio), 3), "quality": round(min(1.0, span / 180), 3),
                                         "size": int(min(a, b)), "arc_deg": span, "axes": [round(2 * a), round(2 * b)]})
        # the same shape found at several segmentation levels counts once
        mine.sort(key=lambda s: -s["quality"])
        for s in mine:
            if not any(abs(s["box"][0] - t["box"][0]) <= 2 and abs(s["box"][1] - t["box"][1]) <= 2
                       and abs(s["box"][2] - t["box"][2]) <= 3 and abs(s["box"][3] - t["box"][3]) <= 3
                       for t in found if t["file"] == p):
                found.append(s)
    # animation frames and repeated objects: identical shapes count once
    seen, uniq = set(), []
    for s in found:
        k = (s["kind"], s["box"][2], s["box"][3])
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq


def estimate_from_shapes(shapes, candidates, tol=0.045):
    """Which candidate the measured shapes support. Wider than every candidate = probably seen in
    perspective (a round thing on the floor); taller than every candidate = not round. Weighted
    by quality and size (small shapes are quantized)."""
    cands = sorted(set(round(float(c), 3) for c in candidates))
    lo, hi = min(cands) / (1 + 2 * tol), max(cands) * (1 + 2 * tol)
    support = {c: 0.0 for c in cands}
    count = {c: 0 for c in cands}
    persp = narrow = 0
    vals, wts = [], []
    for s in shapes:
        r = s["ratio"]
        w = s.get("quality", 1.0) * min(1.0, s.get("size", 20) / 20)
        if r > hi:
            persp += 1
            continue
        if r < lo:
            narrow += 1
            continue
        vals.append(math.log(r))
        wts.append(w)
        for c in cands:
            if abs(math.log(r / c)) <= tol:
                support[c] += w
                count[c] += 1
    mode = None
    if vals:
        v, w = np.array(vals), np.array(wts)
        grid = np.linspace(math.log(lo), math.log(hi), 200)
        dens = (w[None, :] * np.exp(-0.5 * ((grid[:, None] - v[None, :]) / 0.025) ** 2)).sum(axis=1)
        mode = round(float(math.exp(grid[int(np.argmax(dens))])), 3)
    order = sorted(cands, key=lambda c: -support[c])
    best = order[0]
    second = support[order[1]] if len(order) > 1 else 0.0
    if count[best] >= 3 and support[best] >= 2.0 and support[best] >= 2 * second and \
            (mode is None or abs(math.log(mode / best)) <= 2 * tol):
        verdict = "agree"
    elif len(vals) >= 3:
        verdict = "inconclusive"
    else:
        verdict = "none"
    return {"verdict": verdict, "best": best if verdict == "agree" else None, "mode": mode,
            "shapes": len(shapes), "in_window": len(vals), "perspective_or_wide": persp, "tall": narrow,
            "support": {str(c): round(support[c], 2) for c in cands},
            "count": {str(c): count[c] for c in cands}}


def _from_measures(measures, candidates, tol=0.045):
    """Manual `aspect-measure` results (dicts or JSON files): candidates they agree with."""
    rows = []
    for m in measures or []:
        if isinstance(m, str):
            import json
            with open(m, encoding="utf-8") as f:
                m = json.load(f)
        for item in (m if isinstance(m, list) else [m]):
            r = item.get("ratio")
            if not r:
                continue
            near = [c for c in candidates if abs(math.log(r / c)) <= tol]
            rows.append({"ratio": r, "closest": min(candidates, key=lambda c: abs(c - r)),
                         "agrees": near[0] if len(near) == 1 else None,
                         "ellipse_fill": item.get("ellipse_fill")})
    agreed = {x["agrees"] for x in rows if x["agrees"] is not None}
    best = agreed.pop() if len(agreed) == 1 and all(x["agrees"] is not None for x in rows) else None
    return {"measures": rows, "best": best,
            "verdict": "agree" if best is not None else ("conflict" if rows else "none")}


def aspect_auto(platform, width, height, year=None, art=None, evidence=None, measures=None,
                sheet_out="review/aspect.png", candidates=None):
    """Decide the pixel aspect alone when it is clear, otherwise prepare the question.

    decided_by "auto": the table is sure (alta) and the measured evidence does not contradict it,
    or the measured evidence (shapes found in the dump, manual measures) clearly agrees with a
    candidate that the table does not contradict. decided_by "ask": medium/low confidence without
    concordant evidence, evidence against the table, digitized art without evidence; then the
    comparison sheet is produced to show to the user."""
    table = pixel_aspect(platform, width, height, year, art)
    ts = round(float(table["stretch"]), 3)
    cands = sorted(set([1.0, ts] + [float(c) for c in (candidates or [])]))
    shapes = find_round_shapes(evidence) if evidence else []
    auto_ev = estimate_from_shapes(shapes, cands) if evidence else {"verdict": "none", "best": None}
    man = _from_measures(measures, cands)
    reasons = [f"tabella: allungamento {ts:g} (confidenza {table['confidence']}) — " + "; ".join(table["reasons"])]

    # what the evidence says, manual measures first (they were taken on purpose)
    ev_best, ev_conflict = None, False
    if man["verdict"] == "agree":
        ev_best = man["best"]
        reasons.append(f"misure manuali: {len(man['measures'])}, concordi con {ev_best:g}")
    elif man["verdict"] == "conflict":
        ev_conflict = True
        reasons.append("misure manuali non concordi o lontane dai candidati: " +
                       ", ".join(f"{x['ratio']:g}" for x in man["measures"]))
    if auto_ev["verdict"] == "agree":
        if ev_best is not None and ev_best != auto_ev["best"]:
            ev_conflict = True
            reasons.append(f"forme trovate nel dump: favoriscono {auto_ev['best']:g}, le misure manuali {ev_best:g}")
        else:
            ev_best = auto_ev["best"]
            reasons.append(f"forme rotonde trovate nel dump: {auto_ev['count'][str(ev_best)]} vicine a {ev_best:g} "
                           f"(moda {auto_ev['mode']:g}) su {auto_ev['in_window']} utili; "
                           f"{auto_ev['perspective_or_wide']} più larghe (prospettiva)")
    elif evidence:
        reasons.append(f"forme trovate nel dump: {auto_ev.get('shapes', 0)}, {auto_ev.get('in_window', 0)} utili: "
                       + ("non bastano a decidere" if auto_ev["verdict"] == "none" else
                          f"distribuzione non netta (moda {auto_ev.get('mode')}, sostegno {auto_ev.get('support')})"))

    conf = table["confidence"]
    doubts = []
    if ev_conflict:
        doubts.append("le prove misurate non concordano tra loro")
    if ev_best is not None and ev_best != ts:
        doubts.append(f"prove ({ev_best:g}) e tabella ({ts:g}) si contraddicono")
    if ev_best is None and conf != "alta":
        doubts.append(f"confidenza {conf} della tabella senza prove misurate concordi")
    if art == "digitized" and ts != 1.0 and ev_best is None:
        doubts.append("arte digitalizzata o renderizzata senza prove misurate")

    if not doubts:
        stretch = ts
        decided_by = "auto"
        confidence = "alta" if (ev_best == ts or conf == "alta") else conf
    else:
        stretch = None
        decided_by = "ask"
        confidence = conf if ev_best is None else "media"
    res = {"stretch": stretch, "decided_by": decided_by, "confidence": confidence,
           "proposed": ev_best if ev_best is not None else ts, "candidates": cands,
           "reasons": reasons + (["dubbi: " + "; ".join(doubts)] if doubts else []),
           "evidence": {"table": {"stretch": ts, "confidence": conf, "mode": [width, height],
                                  "platform": table["platform"]},
                        "shapes": {k: v for k, v in auto_ev.items()} if evidence else None,
                        "examples": [{k: s[k] for k in ("file", "kind", "box", "ratio")}
                                     for s in sorted(shapes, key=lambda s: -s.get("size", 0))[:8]],
                        "measures": man["measures"]}}
    if decided_by == "ask":
        imgs = []
        ranked = sorted(shapes, key=lambda s: -s.get("size", 0))
        for s in ranked:
            if s["file"] not in imgs:
                imgs.append(s["file"])
            if len(imgs) == 4:
                break
        if not imgs:
            imgs = [p for p in _image_paths(evidence, 40) if Image.open(p).width >= 160][:4]
        if imgs:
            res["sheet"] = aspect_sheet(imgs, sheet_out, tuple(sorted({1.0, ts, res["proposed"]})))["sheet"]
        res["ask"] = ("proporzione dei pixel: mostra il foglio di confronto e i dubbi; "
                      "se serve, misura una forma rotonda con `widescreen aspect-measure`")
    return res


def record_aspect(data, res):
    """Write the result of `aspect_auto` in remaster.json (graphics.pixel_aspect) and, when
    automatic, a dated decision."""
    pa = {"stretch": res["stretch"], "decided_by": res["decided_by"], "confidence": res["confidence"],
          "reasons": res["reasons"], "evidence": res["evidence"]}
    if res.get("sheet"):
        pa["sheet"] = res["sheet"]
    if res["decided_by"] == "ask":
        pa["proposed"] = res["proposed"]
    data.setdefault("graphics", {})["pixel_aspect"] = pa
    if res["decided_by"] == "auto":
        import datetime as _dt
        data.setdefault("decisions", []).append({
            "date": _dt.datetime.now().replace(microsecond=0).isoformat(),
            "decision": f"proporzione dei pixel {res['stretch']:g} (automatica)",
            "why": "; ".join(res["reasons"])})
    return pa
