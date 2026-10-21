"""ScummVM GUI theme in the style of the game: a copy of a theme of the SAME ScummVM commit
(the .stx syntax changes between versions) with the palette, fonts and logo replaced.

The colours come from the game's own interface (menus, inventory, dialogue boxes), not from
the backgrounds: `propose_palette` reads a screenshot of the original UI and proposes the
roles; the agent checks them and the user chooses between 2-3 variants by looking.
"""
import json
import os
import re
import zipfile

from PIL import Image

# palette names of the bundled themes, grouped by role
ROLES = {
    "fondo": ["background", "thumb_color"],
    "pannello": ["dialog_background", "paleyellow", "blandyellow", "lightgray2"],
    "pannello_scuro": ["lightgray", "darkgray", "darkgray2"],
    "pulsante": ["button_idle", "darkredborder", "darkeneddarkred"],
    "pulsante_attivo": ["button_hover", "button_pressed", "griditem_highlight_color", "darkenedbrightred"],
    "bordo_chiaro": ["brightredborder"],
    "evidenza": ["highlight"],
    "ombra": ["shadowcolor"],
    "testo": ["black"],
    "testo_chiaro": ["white"],
}
THEME_EXT = (".stx", ".bmp", ".fcc", ".ttf", ".otf", ".png", ".svg", ".bdf")
COLOR = re.compile(r"(<color\s+name\s*=\s*'([^']+)'\s*rgb\s*=\s*')([^']*)(')", re.S)


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def propose_palette(ui_image, n=8):
    """Roles from a screenshot of the ORIGINAL interface: darkest -> ombra/fondo, lightest ->
    pannello, most saturated -> pulsante/evidenza. A proposal to check by eye."""
    im = Image.open(ui_image).convert("RGB")
    q = im.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    cols = [(cnt, tuple(pal[i * 3:i * 3 + 3])) for cnt, i in sorted(q.getcolors(), reverse=True)]
    rgb = [c for _n, c in cols]
    by_lum = sorted(rgb, key=_lum)
    sat = sorted(rgb, key=lambda c: (max(c) - min(c)), reverse=True)

    def mix(a, b, t):
        return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))
    btn = sat[0]
    light = by_lum[-1]
    dark = by_lum[0]
    roles = {
        "fondo": by_lum[1] if len(by_lum) > 2 else dark,
        "pannello": light,
        "pannello_scuro": mix(light, dark, 0.25),
        "pulsante": btn,
        "pulsante_attivo": mix(btn, (255, 255, 255), 0.25),
        "bordo_chiaro": mix(light, btn, 0.15),
        "evidenza": sat[1] if len(sat) > 1 else btn,
        "ombra": mix(dark, light, 0.2),
        "testo": dark,
        "testo_chiaro": light,
    }
    return {k: "#%02x%02x%02x" % v for k, v in roles.items()}


def contrast(a, b):
    """WCAG contrast ratio of two #rrggbb colours."""
    def rel(c):
        v = [x / 255 for x in _hex(c)]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    la, lb = sorted((rel(a), rel(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


TAG_ATTRS = r"((?:\s+[\w]+\s*=\s*'[^']*')*)"  # attributes, quoted values may contain '>'


def set_font(stx, fname, skip_ids=("console",)):
    """Use `fname` for the Latin languages in every text style (not the monospaced console):
    replaces the scalable file of the <language id = '*'> fallback, or adds scalable_file to a
    <font> without one. Quoted attribute values may contain '>' (resolution = 'y>=H')."""
    count = 0

    def one(m):
        nonlocal count
        attrs, close, body = m.group(1), m.group(2), m.group(3) or ""
        ident = re.search(r"\bid\s*=\s*'([^']*)'", attrs)
        if ident and ident.group(1) in skip_ids:
            return m.group(0)
        new_body, k = re.subn(r"(<language\s+id\s*=\s*'\*'\s+scalable_file\s*=\s*')[^']*(')",
                              lambda mm: f"{mm.group(1)}{fname}{mm.group(2)}", body)
        if k == 0 and "scalable_file" not in attrs:
            attrs += f" scalable_file = '{fname}'"
            k = 1
        count += 1 if k else 0
        return f"<font{attrs}{close}{new_body}" + ("</font>" if close.strip() == ">" else "")
    stx = re.sub(r"<font" + TAG_ATTRS + r"\s*(/>|>)((?<=>)(?<!/>).*?(?=</font>))?(?:</font>)?", one, stx, flags=re.S)
    return stx, count


def build(base_theme_dir, roles, out_zip, name, font_ttf=None, logo=None, colors=None):
    """base_theme_dir: e.g. <scummvm>/gui/themes/scummremastered (same commit as the fork).
    roles: {role: "#rrggbb"} (see ROLES); colors: {stx colour name: "#rrggbb"} for fine tuning.
    font_ttf: TTF/OTF of the game's style (licence that allows redistribution!) used as
    scalable font for every text style; logo: PNG replacing the theme logo."""
    themerc = os.path.join(base_theme_dir, "THEMERC")
    if not os.path.exists(themerc):
        raise ValueError(f"{base_theme_dir}: manca THEMERC (serve una cartella di tema di ScummVM)")
    with open(themerc, encoding="utf-8") as f:
        rc = f.read().splitlines()
    m = re.match(r"\[(SCUMMVM_STX[\d.]+):([^:]*):(.*)\]", rc[0])
    if not m:
        raise ValueError("THEMERC: intestazione non riconosciuta")
    using = [l[len("%using "):].strip() for l in rc[1:] if l.startswith("%using ")]
    wanted = {}
    for role, hexcol in (roles or {}).items():
        for cname in ROLES.get(role, []):
            wanted[cname] = hexcol
    wanted.update(colors or {})
    replaced, files = set(), {}
    dirs = [base_theme_dir] + [os.path.normpath(os.path.join(base_theme_dir, u)) for u in using]
    for d in dirs:
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if os.path.isfile(p) and fn.lower().endswith(THEME_EXT) and fn not in files:
                files[fn] = p
    os.makedirs(os.path.dirname(os.path.abspath(out_zip)), exist_ok=True)
    report = {"theme": name, "stx_version": m.group(1), "colors_replaced": [], "fonts": 0}
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("THEMERC", f"[{m.group(1)}:{name}:{m.group(3)}]\n")
        for fn, p in files.items():
            if fn == "THEMERC":
                continue
            if fn.endswith(".stx"):
                with open(p, encoding="utf-8") as f:
                    stx = f.read()

                def sub(mm):
                    cname = mm.group(2)
                    if cname in wanted:
                        replaced.add(cname)
                        r, g, b = _hex(wanted[cname])
                        return f"{mm.group(1)}{r}, {g}, {b}{mm.group(4)}"
                    return mm.group(0)
                stx = COLOR.sub(sub, stx)
                if font_ttf:
                    stx, k = set_font(stx, os.path.basename(font_ttf))
                    report["fonts"] += k
                if logo:
                    # the bitmap must win over the bundled SVG logo
                    stx = re.sub(r"(<bitmap\s+filename\s*=\s*'logo[^']*\.bmp')\s+scalable_file\s*=\s*'[^']*'", r"\1", stx)
                z.writestr(fn, stx)
            elif logo and fn.startswith("logo") and fn.endswith(".svg"):
                continue
            elif logo and fn.startswith("logo") and fn.endswith(".bmp"):
                with Image.open(p) as orig:
                    size = orig.size
                im = Image.open(logo).convert("RGB")
                im.thumbnail(size, Image.LANCZOS)
                canvas = Image.new("RGB", size, (255, 0, 255))  # magenta = transparent in themes
                canvas.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
                tmp = out_zip + ".logo.bmp"
                canvas.save(tmp)
                z.write(tmp, fn)
                os.remove(tmp)
            else:
                z.write(p, fn)
        if font_ttf:
            z.write(font_ttf, os.path.basename(font_ttf))
    report["colors_replaced"] = sorted(replaced)
    report["colors_missing"] = sorted(set(wanted) - replaced)
    warnings = []
    for bg_role, key, what in (("pannello", "contrast_text_panel", "pannello (liste, dialoghi)"),
                               ("fondo", "contrast_text_background", "fondo (etichette scritte sul fondo)")):
        if roles and roles.get("testo") and roles.get(bg_role):
            report[key] = contrast(roles["testo"], roles[bg_role])
            if report[key] < 4.5:
                warnings.append(f"contrasto testo/{what} {report[key]} < 4.5: si legge male; schiarisci il "
                                "fondo o scurisci il testo (il testo dei temi è uno solo per fondo e pannelli)")
    if warnings:
        report["warnings"] = warnings
    report["zip"] = out_zip
    return report


def save_roles(roles, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(roles, f, indent=2)
    return path
