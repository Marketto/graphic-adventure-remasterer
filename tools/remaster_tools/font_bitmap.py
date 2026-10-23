"""HD dei font bitmap originali: glifi indicizzati -> atlante RFNT a 3x con angoli vivi.

Strada preferita per i testi in gioco (fedele al disegno); il TTF (`font.build`) resta per
sottotitoli/filmati o quando il font originale è inservibile. Vedi skills/hd-graphics §4.

Ingresso (generico, scritto dal Layer o da un adattatore del repository privato):
- un file JSON `{"height": H, "bpp": 1|2, "glyphs": {"41": {"w","h","ox","oy","adv","px": [...]}}}`
  (chiave = codice del glifo in esadecimale, `px` = w*h valori per riga);
- oppure una cartella di PNG indicizzati `<hex>.png` (valori dei pixel = indici) con un
  `font.json` facoltativo per `height`, `bpp` e per glifo `ox`, `oy`, `adv`.
Valori dei pixel: 0 vuoto, 1 riempimento, 2 contorno/ombra, 3 secondo colore (trattato come
riempimento). Coordinate: (ox, oy) = angolo in alto a sinistra rispetto alla penna; adv in px.
"""
import json
import os
import struct
import unicodedata

import numpy as np
from PIL import Image

from . import text as _text

ACUTE, GRAVE = "́", "̀"
OPPOSITE = {ACUTE: GRAVE, GRAVE: ACUTE}
PAD = 12  # margine della tela di lavoro (accenti sopra la riga, contorni)


# ---------------------------------------------------------------- caricamento
def _glyph(w, h, ox, oy, adv, px):
    return {"w": int(w), "h": int(h), "ox": int(ox), "oy": int(oy), "adv": int(adv),
            "px": [int(v) for v in px]}


def _indices(img):
    """PNG -> matrice di indici 0..3 (palette o grigi; i grigi chiari = riempimento)."""
    a = np.asarray(img if img.mode in ("P", "L") else img.convert("L")).astype(np.int32)
    if a.max() > 3:
        a = np.where(a == 0, 0, np.where(a >= 128, 1, 2))
    return a.astype(np.uint8)


def load(path):
    """Legge un dump di font bitmap (JSON o cartella di PNG)."""
    if os.path.isdir(path):
        meta_p = os.path.join(path, "font.json")
        meta = json.load(open(meta_p, encoding="utf-8")) if os.path.exists(meta_p) else {}
        gm = {int(k, 16): v for k, v in meta.get("glyphs", {}).items()}
        glyphs = {}
        for f in sorted(os.listdir(path)):
            stem, ext = os.path.splitext(f)
            if ext.lower() != ".png":
                continue
            try:
                code = int(stem, 16)
            except ValueError:
                continue
            a = _indices(Image.open(os.path.join(path, f)))
            m = gm.get(code, {})
            glyphs[code] = _glyph(a.shape[1], a.shape[0], m.get("ox", 0), m.get("oy", 0),
                                  m.get("adv", a.shape[1] + m.get("ox", 0)), a.flatten())
        height = meta.get("height") or max((g["h"] + g["oy"] for g in glyphs.values()), default=1)
        bpp = meta.get("bpp") or (2 if any(2 in g["px"] for g in glyphs.values()) else 1)
        return {"height": int(height), "bpp": int(bpp), "glyphs": glyphs}
    d = json.load(open(path, encoding="utf-8"))
    glyphs = {}
    for k, g in d["glyphs"].items():
        code = int(k, 16) if isinstance(k, str) else int(k)
        glyphs[code] = _glyph(g["w"], g["h"], g.get("ox", 0), g.get("oy", 0),
                              g.get("adv", g["w"] + g.get("ox", 0)), g["px"])
    return {"height": int(d["height"]), "bpp": int(d.get("bpp", 2)), "glyphs": glyphs}


# ---------------------------------------------------------------- tela di lavoro
def place(g, size=48):
    c = np.zeros((size, size), np.uint8)
    if g["w"] and g["h"]:
        a = np.array(g["px"], np.uint8).reshape(g["h"], g["w"])
        c[PAD + g["oy"]:PAD + g["oy"] + g["h"], PAD + g["ox"]:PAD + g["ox"] + g["w"]] = a
    return c


def unplace(c, adv):
    ys, xs = np.nonzero(c)
    if not len(xs):
        return _glyph(0, 0, 0, 0, adv, [])
    a = c[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return _glyph(a.shape[1], a.shape[0], xs.min() - PAD, ys.min() - PAD, adv, a.flatten())


def fillm(c):
    return (c == 1) | (c == 3)


def empty(g):
    return g is None or not any(g["px"])


def kernel(glyphs):
    """Nocciolo del contorno: spostamenti (dx, dy) dove il contorno accompagna sempre il riempimento."""
    cs = [place(g) for g in glyphs.values() if not empty(g)]
    ks = []
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            tot = hit = 0
            for c in cs:
                f = fillm(c)
                nb = np.roll(np.roll(c, -dy, 0), -dx, 1)
                tot += f.sum()
                hit += (f & (nb != 0)).sum()
            if tot and hit / tot > 0.97:
                ks.append((dx, dy))
    return ks


def dil(m, ks):
    o = np.zeros_like(m)
    for dx, dy in ks:
        o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o


# ---------------------------------------------------------------- ingrandimento
def crisp3x(a):
    """3x a blocchi esatti; smussa solo i gradini delle diagonali vere (EPX/Scale3x ristretto
    agli spigoli): il sottopixel d'angolo prende il valore dei due vicini ortogonali uguali solo se
    il pixel diagonale tra loro è diverso. Angoli retti (convessi e concavi) restano vivi e il centro
    di ogni blocco 3x3 è il pixel originale. Mai Scale3x doppio o upscaler IA: una D diventa O."""
    p = np.pad(a, 1, mode="edge")
    h, w = a.shape
    big = np.kron(a, np.ones((3, 3), a.dtype))

    def n(dy, dx):
        return p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
    for vy, sx in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        V, Hh, A, Vo, Ho = n(vy, 0), n(0, sx), n(vy, sx), n(-vy, 0), n(0, -sx)
        m = (V == Hh) & (V != a) & (A != V) & (V != Ho) & (Hh != Vo)
        sub = big[(0 if vy < 0 else 2)::3, (0 if sx < 0 else 2)::3]
        sub[m] = V[m]
    return big


def upscale(a, scale=3):
    return crisp3x(a) if scale == 3 else np.kron(a, np.ones((scale, scale), a.dtype))


def hd_cell(g, bpp, scale=3):
    """(riempimento, sagoma) in 0/255 del glifo con 1 px originale di margine."""
    a = np.pad(np.array(g["px"], np.uint8).reshape(g["h"], g["w"]), 1)
    big = upscale(a, scale)
    fill = fillm(big)
    sil = (big != 0) if bpp > 1 else np.zeros_like(fill)
    return (fill * 255).astype(np.uint8), (sil * 255).astype(np.uint8)


# ---------------------------------------------------------------- accenti
def _cmap_codepage(codepage):
    m = {}
    for code in range(32, 256):
        try:
            ch = bytes([code]).decode(codepage)
        except UnicodeDecodeError:
            continue
        if ch.isprintable():
            m.setdefault(ch, code)
    return m


def _top(c):
    r = np.nonzero(fillm(c).any(1))[0]
    return int(r.min()) if len(r) else None


def _accent_from(F, cmap, mark):
    """Accento `mark` preso da una minuscola accentata dello stesso font: riempimento sopra il
    corpo della lettera base; restituisce (maschera, distanza dal corpo)."""
    for flip in (False, True):
        m = OPPOSITE.get(mark) if flip else mark
        if not m:
            continue
        for b in "eaouicnyEAOUI":
            acc_ch = unicodedata.normalize("NFC", b + m)
            ca, cb = cmap.get(acc_ch), cmap.get(b)
            if len(acc_ch) != 1 or ca is None or cb is None or empty(F.get(ca)) or empty(F.get(cb)):
                continue
            fa, tb = fillm(place(F[ca])), _top(place(F[cb]))
            acc = fa.copy()
            acc[tb:] = False
            if not acc.any():
                continue
            ys, xs = np.nonzero(acc)
            gap = tb - int(ys.max())
            if flip:  # grave <-> acuto: specchiato sul proprio riquadro
                new = np.zeros_like(acc)
                new[ys, xs.min() + xs.max() - xs] = True
                acc = new
            return acc, gap
    return None


def _drop_dot(c):
    """i/j: via il punto (componente di riempimento sopra uno spazio vuoto) e ciò che c'è sopra."""
    rows = np.nonzero(fillm(c).any(1))[0]
    for r0, r1 in zip(rows[:-1], rows[1:]):
        if r1 - r0 > 1:
            c = c.copy()
            c[:r1 - 1] = 0
            return c
    return c


def compose(F, cmap, ch, ks, bpp):
    """Lettera accentata `ch` = lettera base dello stesso font a piena altezza + accento della
    minuscola, sopra il corpo alla stessa distanza (sopra la riga per le maiuscole), centrato,
    contorno rifatto con il nocciolo del font. None se mancano i pezzi."""
    d = unicodedata.normalize("NFD", ch)
    if len(d) != 2:
        return None
    base, mark = d
    cb = cmap.get(base)
    if cb is None or empty(F.get(cb)):
        return None
    got = _accent_from(F, cmap, mark)
    if got is None:
        return None
    acc, gap = got
    c = place(F[cb])
    if base in "ij":
        c = _drop_dot(c)
    fb = fillm(c)
    ya, xa = np.nonzero(acc)
    xb = np.nonzero(fb)[1]
    dy = _top(c) - gap - int(ya.max())
    dx = int(round((xb.min() + xb.max()) / 2 - (xa.min() + xa.max()) / 2))
    new = np.zeros_like(acc)
    new[ya + dy, xa + dx] = True
    out = c.copy()
    if bpp > 1 and ks:
        out[dil(new, ks) & (out == 0)] = 2
    out[new] = 1
    return unplace(out, F[cb]["adv"])


def short_capital(F, cmap, ch):
    """Maiuscola accentata col corpo accorciato per far stare l'accento nella cella (si legge
    minuscola): l'accento non supera di almeno 2 righe la cima della lettera base."""
    d = unicodedata.normalize("NFD", ch)
    if not ch.isupper() or len(d) != 2 or cmap.get(ch) is None or cmap.get(d[0]) is None:
        return False
    g, b = F.get(cmap[ch]), F.get(cmap[d[0]])
    if empty(g) or empty(b):
        return False
    return _top(place(g)) >= _top(place(b)) - 1


def merge_edition(F, Fx, codepage):
    """Glifi mancanti dall'altra edizione dello stesso gioco (stesso disegno). Se la lettera base
    differisce (peso diverso), base di questa edizione + differenza accentata−base dell'altra."""
    src = {}
    for k in sorted(Fx):
        if (k in F and not empty(F[k])) or empty(Fx[k]):
            continue
        try:
            d = unicodedata.normalize("NFD", bytes([k]).decode(codepage))
            b = ord(d[0].encode(codepage)) if len(d) == 2 else None
        except (UnicodeError, ValueError):
            b = None
        if b is None or b not in F or b not in Fx or F[b]["px"] == Fx[b]["px"] and F[b]["w"] == Fx[b]["w"]:
            F[k] = Fx[k]
            src[k] = "edizione"
            continue
        fb, fa = place(Fx[b]), place(Fx[k])
        added, removed = (fa != 0) & (fb == 0), (fb != 0) & (fa == 0)
        c = place(F[b])
        c[removed] = 0
        c[added] = fa[added]
        F[k] = unplace(c, F[b]["adv"])
        src[k] = "edizione (accento su base locale)"
    return src


# ---------------------------------------------------------------- charmap
def read_charmap(path):
    m = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            u, code = line.split("\t")[:2]
            m[chr(int(u.strip()[2:], 16))] = int(code.strip(), 16)
    return m


def write_charmap(path, m, header):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# " + header + "\n# U+XXXX<TAB>codice del glifo (hex)\n")
        for ch, code in sorted(m.items(), key=lambda kv: ord(kv[0])):
            f.write("U+%04X\t%02X\n" % (ord(ch), code))


def font_charmap(fonts_dir, name):
    m = read_charmap(os.path.join(fonts_dir, "charmap.tsv"))
    m.update(read_charmap(os.path.join(fonts_dir, name + ".charmap.tsv")))
    return m


# ---------------------------------------------------------------- atlante
def write_atlas(F, height, bpp, out_base, scale=3):
    cells = {k: hd_cell(g, bpp, scale) for k, g in F.items() if k < 256 and not empty(g)}
    aw, x, y, rh, pos = 512, 0, 0, 0, {}
    for k in sorted(cells):
        h, w = cells[k][0].shape
        if x + w > aw:
            x, y, rh = 0, y + rh + 1, 0
        pos[k] = (x, y)
        x += w + 1
        rh = max(rh, h)
    atl = np.zeros((y + rh + 1, aw, 3), np.uint8)
    for k, (px, py) in pos.items():
        f, s = cells[k]
        atl[py:py + f.shape[0], px:px + f.shape[1], 0] = f
        atl[py:py + f.shape[0], px:px + f.shape[1], 1] = s
    Image.fromarray(atl, "RGB").save(out_base + ".png", optimize=True)
    with open(out_base + ".dat", "wb") as fo:
        fo.write(b"RFNT")
        fo.write(struct.pack("<HHHHH", 1, scale, height * scale, height * scale, scale if bpp > 1 else 0))
        for k in range(256):
            g = F.get(k)
            if g is None:
                fo.write(struct.pack("<HHHHhhH", 0, 0, 0, 0, 0, 0, 0))
            elif k in pos:
                h, w = cells[k][0].shape
                fo.write(struct.pack("<HHHHhhH", pos[k][0], pos[k][1], w, h,
                                     (g["ox"] - 1) * scale, (g["oy"] - 1) * scale, g["adv"] * scale))
            else:
                fo.write(struct.pack("<HHHHhhH", 0, 0, 0, 0, 0, 0, g["adv"] * scale))
    return pos


def lowres(atlas, rec, scale, bpp):
    """Glifo a 1x ridotto dall'atlante HD (centri dei blocchi), come fa il motore in modalità
    originale per i glifi che il font originale non ha: indici 0/1/2 e origine della cella
    (con 1 px di margine) rispetto alla penna."""
    ax, ay, w, h, bx, by, _ = rec
    cell = atlas[ay:ay + h, ax:ax + w]
    c = scale // 2
    fill = cell[c::scale, c::scale, 0] > 127
    sil = cell[c::scale, c::scale, 1] > 127 if bpp > 1 else fill
    idx = np.where(fill, 1, np.where(sil, 2, 0)).astype(np.uint8)
    return idx, bx // scale, by // scale


def verify(F, out_base, bpp):
    """Riportato a 1x, ogni glifo deve coincidere con il glifo costruito (3 vale come 1)."""
    from . import font as rfnt
    info = rfnt.read(out_base + ".dat")
    atlas = np.asarray(Image.open(out_base + ".png").convert("RGB"))
    bad = []
    for k, g in F.items():
        if k >= 256 or empty(g):
            continue
        idx, ox, oy = lowres(atlas, info["glyphs"][k], info["scale"], bpp)
        ref = place(g)
        ref[ref == 3] = 1
        if bpp == 1:
            ref[ref == 2] = 0
        got = np.zeros_like(ref)
        got[PAD + oy:PAD + oy + idx.shape[0], PAD + ox:PAD + ox + idx.shape[1]] = idx
        if not np.array_equal(ref, got):
            bad.append("%02X" % k)
    return bad


# ---------------------------------------------------------------- comando
def from_bitmap(src, out_dir, name, scale=3, codepage="cp437", extra_edition=None,
                compose_accents=False, chars="", reserve=(), slot_codepage="cp850"):
    """Atlante RFNT HD da un font bitmap originale; aggiorna fonts/charmap.tsv.

    chars: caratteri da garantire (es. quelli dei testi tradotti); con compose_accents quelli
    mancanti sono costruiti (base + accento dello stesso font) in codici liberi, preferendo la
    posizione di `slot_codepage`; le maiuscole accentate accorciate sono rifatte a piena altezza.
    reserve: codici che il motore usa per scopi propri (mai assegnati a glifi nuovi)."""
    os.makedirs(out_dir, exist_ok=True)
    fnt = load(src)
    F, bpp = fnt["glyphs"], fnt["bpp"]
    origin = {k: "originale" for k in F}
    if extra_edition:
        for k, v in merge_edition(F, load(extra_edition)["glyphs"], codepage).items():
            origin[k] = v
    ks = kernel({k: g for k, g in F.items() if 33 <= k < 127}) if bpp > 1 else []
    general = read_charmap(os.path.join(out_dir, "charmap.tsv")) or _cmap_codepage(codepage)
    cmap = dict(general)
    cmap.update(read_charmap(os.path.join(out_dir, name + ".charmap.tsv")))
    reserved = {int(r, 16) if isinstance(r, str) else int(r) for r in reserve}
    missing, taken = [], {}
    if compose_accents:
        for ch in [c for c in cmap if short_capital(F, cmap, c)]:
            g = compose(F, cmap, ch, ks, bpp)
            if g:
                F[cmap[ch]] = g
                origin[cmap[ch]] = "maiuscola a piena altezza + accento"
    for ch in sorted(set(chars)):
        if ch.isspace() or not ch.isprintable():
            continue
        code = cmap.get(ch)
        if code is not None and not empty(F.get(code)):
            continue
        g = compose(F, cmap, ch, ks, bpp) if compose_accents else None
        if g is None:
            missing.append(ch)
            continue
        if code is None or code in reserved:
            used = {k for k, v in F.items() if not empty(v)} | reserved | set(taken)
            try:
                pref = ch.encode(slot_codepage)[0]
            except (UnicodeError, LookupError):
                pref = None
            free = [c for c in range(0x80, 0x100) if c not in used]
            code = pref if pref is not None and pref not in used else (free[0] if free else None)
            if code is None:
                missing.append(ch)
                continue
            for other in [o for o, c in cmap.items() if c == code]:
                del cmap[other]  # il codice libero non aveva glifo: il vecchio carattere non è disegnabile
            cmap[ch] = code
            taken[code] = ch
        F[code] = g
        origin[code] = "costruito (base + accento)"
    out_base = os.path.join(out_dir, name)
    write_atlas(F, fnt["height"], bpp, out_base, scale)
    # charmap: le voci nuove vanno nella mappa generale; quelle in conflitto nell'override del font
    gen = read_charmap(os.path.join(out_dir, "charmap.tsv")) or _cmap_codepage(codepage)
    for o in [o for o, c in gen.items() if c in taken and o != taken[c]]:
        del gen[o]
    override = {ch: c for ch, c in cmap.items() if ch in gen and gen[ch] != c}
    for ch, c in cmap.items():
        gen.setdefault(ch, c)
    write_charmap(os.path.join(out_dir, "charmap.tsv"), gen, "mappa Unicode -> glifo (tutti i font)")
    if override:
        write_charmap(out_base + ".charmap.tsv", override, "override della mappa per " + name)
    over = sorted("%02X" % k for k, g in F.items() if not empty(g) and (g["oy"] < 0 or g["oy"] + g["h"] > fnt["height"]))
    return {"font": out_base + ".dat", "glyphs": sum(1 for g in F.values() if not empty(g)),
            "kernel": ks, "added": {"%02X" % k: v for k, v in sorted(origin.items()) if v != "originale"},
            "missing": missing, "verify_mismatch": verify(F, out_base, bpp),
            "outside_line": over}


def coverage(fonts_dir, texts):
    """Tutti i caratteri dei testi di tutte le lingue devono avere un glifo in ogni font."""
    from . import font as rfnt
    used = set("".join(_text.glyphs(texts).values()))
    used = {c for c in used if c.isprintable() and not c.isspace()}
    res = {}
    for f in sorted(os.listdir(fonts_dir)):
        if not f.endswith(".dat"):
            continue
        name = f[:-4]
        info = rfnt.read(os.path.join(fonts_dir, f))
        m = font_charmap(fonts_dir, name) or _cmap_codepage("cp437")
        res[name] = "".join(sorted(c for c in used if m.get(c) is None or
                                   (info["glyphs"][m[c]][2] == 0 and info["glyphs"][m[c]][6] == 0)))
    return {"chars": "".join(sorted(used)), "missing": res, "ok": not any(res.values())}
