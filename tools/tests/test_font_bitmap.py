"""Font bitmap HD (font from-bitmap / coverage). Font inventato generato nel test: nessun binario
nel repository, nessun dato di gioco."""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from remaster_tools import font, font_bitmap as fb  # noqa: E402

RSTOOL = os.path.join(os.path.dirname(HERE), "rstool.py")

# disegni inventati, 6x10, riga 0 = cima della cella; '#' riempimento
ART = {
    "E": ["", "", "#####", "#", "#", "####", "#", "#", "#####"],
    "D": ["", "", "####", "#...#", "#...#", "#...#", "#...#", "#...#", "####"],
    "A": ["", "", ".###", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "e": ["", "", "", "", ".###", "#...#", "#####", "#", ".####"],
    "é": ["", "...#", "..#", "", ".###", "#...#", "#####", "#", ".####"],  # é
    "è": ["", "..#", "...#", "", ".###", "#...#", "#####", "#", ".####"],  # è
    # É "accorciata" come nei font piccoli d'epoca: l'accento sta dentro l'altezza della E
    "É": ["", "", "...#", "..#", "", "#####", "#", "####", "#####"],
}


def shadow(a):
    """contorno/ombra inventato: 2 a destra, sotto e in diagonale del riempimento."""
    c = np.pad(a, 1)
    f = c == 1
    o = np.zeros_like(f)
    for dy, dx in ((0, 1), (1, 0), (1, 1), (0, -1), (-1, 0)):
        o |= np.roll(np.roll(f, dy, 0), dx, 1)
    c[o & ~f] = 2
    return c


def glyph(rows, bpp=2):
    a = np.zeros((10, 6), np.uint8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == "#":
                a[y, x] = 1
    if bpp > 1:
        a = shadow(a)
        ox = oy = -1
    else:
        ox = oy = 0
    ys, xs = np.nonzero(a)
    crop = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return {"w": crop.shape[1], "h": crop.shape[0], "ox": int(xs.min()) + ox, "oy": int(ys.min()) + oy,
            "adv": 6, "px": crop.flatten().tolist()}


def write_dump(path, chars=ART, bpp=2, mutate=None):
    gl = {}
    for ch, rows in chars.items():
        g = glyph(rows, bpp)
        gl["%02X" % ch.encode("cp437")[0]] = g
    gl["20"] = {"w": 0, "h": 0, "ox": 0, "oy": 0, "adv": 4, "px": []}
    if mutate:
        mutate(gl)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"height": 10, "bpp": bpp, "glyphs": gl}, f)
    return path


def test_crisp3x_angoli_vivi_e_centri():
    d = np.array([[1, 1, 1, 0], [1, 0, 0, 1], [1, 0, 0, 1], [1, 1, 1, 0]], np.uint8)
    big = fb.crisp3x(d)
    assert big.shape == (12, 12)
    assert np.array_equal(big[1::3, 1::3], d)          # centri = pixel originali
    assert big[0:3, 0:3].all()                          # angolo retto della D: vivo, non smussato
    assert big[3:6, 0:3].all() and big[9:12, 0:3].all()
    # gradino diagonale in alto a destra: il sottopixel tra (0,2) e (1,3) è riempito
    assert big[2, 9] == 1 or big[3, 8] == 1
    # un quadrato pieno resta un quadrato (nessun arrotondamento)
    sq = np.ones((3, 3), np.uint8)
    assert fb.crisp3x(np.pad(sq, 1))[3:12, 3:12].all()


def test_from_bitmap_verifica_e_maiuscole(tmp_path):
    src = write_dump(str(tmp_path / "f.json"))
    out = str(tmp_path / "fonts")
    r = fb.from_bitmap(src, out, "ui", compose_accents=True, chars="ÈÀEe")
    assert r["verify_mismatch"] == []
    assert r["missing"] == []
    cm = fb.read_charmap(os.path.join(out, "charmap.tsv"))
    assert cm["À"] == 0xB7 and cm["È"] == 0xD4      # posizioni CP850 libere
    assert "╖" not in cm                                  # il vecchio carattere di B7 è tolto
    F = fb.load(src)["glyphs"]
    info = font.read(os.path.join(out, "ui.dat"))
    atlas = np.asarray(Image.open(os.path.join(out, "ui.png")).convert("RGB"))
    E, _, eoy = fb.lowres(atlas, info["glyphs"][0x45], 3, 2)
    abs_e = set(eoy + np.nonzero((E == 1).any(1))[0])
    for code in (0x90, 0xD4):                                  # É rifatta, È costruita
        idx, ox, oy = fb.lowres(atlas, info["glyphs"][code], 3, 2)
        abs_x = set(oy + np.nonzero((idx == 1).any(1))[0])
        assert abs_e <= abs_x                                  # corpo della E a piena altezza
        assert min(abs_x) < min(abs_e) - 1                     # accento sopra la maiuscola
        assert oy + 1 < 0                                      # ...e sopra la riga
    assert "90" in r["outside_line"] and "D4" in r["outside_line"]
    # direzione dell'accento: É acuto (punta in alto a destra), È grave (in alto a sinistra)
    acute = fb.lowres(atlas, info["glyphs"][0x90], 3, 2)[0] == 1
    grave = fb.lowres(atlas, info["glyphs"][0xD4], 3, 2)[0] == 1
    top = lambda m: np.nonzero(m[np.nonzero(m.any(1))[0].min()])[0].mean()
    assert top(acute) > top(grave)
    assert F[0x45]["w"] > 0


def test_altra_edizione_prima_della_costruzione(tmp_path):
    base = {k: v for k, v in ART.items() if k != "è"}
    src = write_dump(str(tmp_path / "cd.json"), base)
    ext = write_dump(str(tmp_path / "other.json"))
    r = fb.from_bitmap(src, str(tmp_path / "o"), "f", extra_edition=ext)
    assert r["added"]["8A"] == "edizione"
    # stessa lettera con peso diverso: base locale + accento dell'altra edizione
    heavy = dict(ART)
    heavy["e"] = ["", "", "", "", "####", "#...#", "#####", "#", "#####"]
    heavy["è"] = ["", "..#", "...#", "", "####", "#...#", "#####", "#", "#####"]
    ext2 = write_dump(str(tmp_path / "heavy.json"), heavy)
    r2 = fb.from_bitmap(src, str(tmp_path / "o2"), "f", extra_edition=ext2)
    assert "base locale" in r2["added"]["8A"] and r2["verify_mismatch"] == []


def test_cartella_png_e_1bpp(tmp_path):
    d = tmp_path / "glyphs"
    d.mkdir()
    for ch in "ED":
        g = glyph(ART[ch], 1)
        a = np.array(g["px"], np.uint8).reshape(g["h"], g["w"])
        Image.fromarray(a, "L").save(str(d / ("%02X.png" % ord(ch))))
    (d / "font.json").write_text(json.dumps({"height": 10, "bpp": 1,
                                             "glyphs": {"45": {"oy": 2}, "44": {"oy": 2}}}))
    r = fb.from_bitmap(str(d), str(tmp_path / "o"), "small")
    assert r["verify_mismatch"] == [] and r["glyphs"] == 2
    info = font.read(str(tmp_path / "o" / "small.dat"))
    assert info["scale"] == 3 and info["outline"] == 0 and info["line"] == 30


def test_coverage_cli(tmp_path):
    src = write_dump(str(tmp_path / "f.json"))
    out = str(tmp_path / "fonts")
    texts = tmp_path / "it.tsv"
    texts.write_text("k1\tEè DÈ\nk2\tDeß\n", encoding="utf-8")   # ß non c'è
    p = subprocess.run([sys.executable, RSTOOL, "font", "from-bitmap", src, "--name", "dlg",
                        "--out", out, "--compose-accents", "--texts", str(texts)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["missing"] == ["ß"]
    p = subprocess.run([sys.executable, RSTOOL, "font", "coverage", out, "--texts", str(texts)],
                       capture_output=True, text=True)
    assert p.returncode == 1
    assert json.loads(p.stdout)["missing"]["dlg"] == "ß"
    texts.write_text("k1\tEè DÈ\n", encoding="utf-8")
    p = subprocess.run([sys.executable, RSTOOL, "font", "coverage", out, "--texts", str(texts)],
                       capture_output=True, text=True)
    assert p.returncode == 0 and json.loads(p.stdout)["ok"]


def test_override_per_font(tmp_path):
    out = str(tmp_path / "fonts")
    os.makedirs(out)
    fb.write_charmap(os.path.join(out, "charmap.tsv"), {"E": 0x45, "È": 0xD4}, "test")
    with open(os.path.join(out, "small.charmap.tsv"), "w", encoding="utf-8") as f:
        f.write("U+00C8\t8A\n")
    m = fb.font_charmap(out, "small")
    assert m["È"] == 0x8A and fb.font_charmap(out, "other")["È"] == 0xD4
