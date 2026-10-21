"""Tests of audio groups and mix, pixel aspect, reference emulators, timing, controls, hints,
manual, GUI theme, local 16:9 techniques, optional fal.ai and patchability of the engine.
Synthetic, invented data only (no game files, no GPU, no network)."""
import json
import os
import shutil
import subprocess
import sys
import zipfile

import numpy as np
import pytest
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from remaster_tools import (assets, audio, bands, controls, falai, hints, manual, platforms,  # noqa: E402
                            project, theme, timing, widescreen)
from test_pipeline import dump, RSTOOL  # noqa: E402,F401  (fixture with invented scenes)

need_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg assente")


def tone(path, lufs, f=440, d=4):
    """Sine at about `lufs` (the lavfi sine is at 1/8 of full scale: about -18.8 LUFS)."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=f={f}:d={d}",
                    "-af", f"volume={lufs + 18.8:.1f}dB", str(path)], check=True)


# ------------------------------------------------------------------ audio
@need_ffmpeg
def test_audio_groups_then_mix(tmp_path):
    (tmp_path / "mus").mkdir()
    (tmp_path / "fx").mkdir()
    tone(tmp_path / "mus" / "tema.wav", -20)
    tone(tmp_path / "mus" / "notte.wav", -30, f=330)
    tone(tmp_path / "fx" / "forte.wav", -18, f=900, d=2)
    tone(tmp_path / "fx" / "piano.wav", -28, f=700, d=2)
    plan = str(tmp_path / "norm.json")
    m = audio.normalize_group("music", [str(tmp_path / "mus")], plan)
    s = audio.normalize_group("sfx", [str(tmp_path / "fx")], plan)
    assert m["policy"] == "file" and s["policy"] == "group"
    # group policy: one gain for every effect, so their difference is kept
    g = {e["name"]: e["norm_gain"] for e in s["files"]}
    assert g["forte.wav"] == g["piano.wav"]
    res = audio.apply_mix(plan, str(tmp_path / "out"))
    assert res["written"] == 4
    lv = {n: audio.loudness(str(tmp_path / "out" / sub / n)) for sub, n in
          (("music", "tema.ogg"), ("music", "notte.ogg"), ("sfx", "forte.ogg"), ("sfx", "piano.ogg"))}
    assert abs(lv["tema.ogg"] + 25) < 1 and abs(lv["notte.ogg"] + 25) < 1, lv
    assert lv["forte.ogg"] <= -15.0, lv           # cap of the effects (-16) respected
    assert lv["piano.ogg"] < lv["forte.ogg"] - 6, lv   # intended difference kept
    # a mix file moves a whole group
    with open(tmp_path / "mix.json", "w") as f:
        json.dump({"music": -28}, f)
    gains = audio.mix_gains(json.load(open(plan)), *audio.load_mix(str(tmp_path / "mix.json")))
    assert gains["music"]["target"] == -28 and gains["music"]["offset"] == -5


@need_ffmpeg
def test_mix_preview_variants(tmp_path):
    tone(tmp_path / "m.wav", -20, d=3)
    tone(tmp_path / "v.wav", -20, f=200, d=1)
    res = audio.mix_preview(str(tmp_path / "prova.ogg"), voice=str(tmp_path / "v.wav"), music=str(tmp_path / "m.wav"),
                            duration=4, music_offsets=(0, -3))
    assert len(res["previews"]) == 2 and all(os.path.getsize(p["file"]) > 1000 for p in res["previews"])


# ------------------------------------------------------------------ pixel aspect and emulators
def test_pixel_aspect_depends_on_platform_and_art():
    assert platforms.pixel_aspect("dos", 320, 200, 1992)["stretch"] == 1.2
    assert platforms.pixel_aspect("DOS", 640, 480, 1995)["correct"] is False
    assert platforms.pixel_aspect("dos", 640, 400, 1995, art="digitized")["stretch"] == 1.0
    assert platforms.pixel_aspect("windows", 640, 480)["stretch"] == 1.0
    assert platforms.pixel_aspect("amiga", 320, 256)["stretch"] == 1.0
    unknown = platforms.pixel_aspect("console-x", 256, 224)
    assert unknown["confidence"] == "bassa"
    assert widescreen.geometry(320, 200, 1.2)["left"] == 54 and widescreen.geometry(320, 200)["left"] == 18


def test_reference_emulators_by_platform(tmp_path):
    assert "DOSBox" in platforms.reference_emulators("ms-dos")["emulators"][0]["name"]
    win = platforms.reference_emulators("win95")["emulators"]
    assert any("Wine" in e["name"] for e in win) and "86Box" in win[0]["name"]
    assert platforms.reference_emulators("sconosciuta")["emulators"] == []
    im = tmp_path / "s.png"
    Image.new("RGB", (320, 200), (90, 120, 200)).save(im)
    res = platforms.aspect_sheet([str(im)], str(tmp_path / "sheet.png"))
    assert os.path.exists(res["sheet"])


# ------------------------------------------------------------------ timing
def synthetic_frames(n=240, every=8):
    frames = np.zeros((n, 100, 160), np.uint8)
    v = 0
    for i in range(n):
        if i % every == 0:
            v = (v + 40) % 256
        frames[i, 20:60, 30:90] = v
    return frames


def test_timing_intervals_from_frames():
    idx, iv = timing.change_intervals(synthetic_frames(), 60.0)
    s = timing.summarize(iv, 60.0)
    assert abs(s["median_ms"] - 133.3) < 0.5


@need_ffmpeg
def test_timing_from_video_and_compare(tmp_path):
    fr = synthetic_frames(180, 6)
    raw = tmp_path / "f.raw"
    raw.write_bytes(fr.tobytes())
    vid = tmp_path / "rec.mkv"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "160x100",
                    "-r", "60", "-i", str(raw), "-c:v", "ffv1", str(vid)], check=True)
    m = timing.measure(str(vid), [{"name": "intro", "start": 0, "duration": 3}])
    assert abs(m["segments"][0]["median_ms"] - 100.0) < 1, m
    faster = json.loads(json.dumps(m))
    faster["segments"][0]["duration_s"] *= 0.5
    faster["segments"][0]["median_ms"] *= 0.5
    assert timing.compare(m, m)["ok"] and not timing.compare(m, faster)["ok"]


# ------------------------------------------------------------------ controls
def test_controls_smooth_and_problems():
    good = []
    for i in range(120):
        t = i * 1000 / 60
        good += [f"{t:.1f} in mouse {100 + i * 2} 50", f"{t + 4:.1f} draw cursor {100 + i * 2} 50"]
    r = controls.analyze_cursor(controls.parse(good))
    assert not r["problems"], r
    slow = [f"{i * 1000 / 60:.1f} in mouse {100 + i * 2} 50" for i in range(120)]
    slow += [f"{i * 66.7:.1f} draw cursor {100 + i * 8} 50" for i in range(30)]
    r = controls.analyze_cursor(controls.parse(sorted(slow, key=lambda l: float(l.split()[0]))))
    assert any("Hz" in p for p in r["problems"]), r
    keys = ["0 in key F8 down", "0.5 act toggle", "500 in key F8 down repeat", "501 act toggle",
            "540 in key F8 down repeat", "600 in key F8 up",
            "1000 in key RIGHT down", "1001 act scroll", "1500 in key RIGHT up"]
    k = controls.analyze_keys(controls.parse(keys))
    assert k["presses"] == 2 and len(k["problems"]) == 1 and "F8" in k["problems"][0]


# ------------------------------------------------------------------ hints
HINT_IT = """@parte 1
obiettivo: Entrare in biblioteca
fatto: LF:atrio:porta_aperta | obj:chiave
situazione: Sei nell'atrio e la porta è chiusa.
indizio: Il custode ha qualcosa in tasca.
soluzione: Parla col custode e usa la chiave sulla porta.

obiettivo: Trovare il libro
fatto: libro_preso
situazione: Sei in biblioteca.
indizio: Guarda in alto.
soluzione: Usa la scala sullo scaffale.
"""


def test_hints_validate(tmp_path):
    (tmp_path / "it.txt").write_text(HINT_IT, encoding="utf-8")
    en = HINT_IT.replace("Entrare in biblioteca", "Get into the library")
    (tmp_path / "en.txt").write_text(en, encoding="utf-8")
    r = hints.validate([str(tmp_path / "it.txt"), str(tmp_path / "en.txt")])
    assert r["ok"], r
    assert hints.parse_condition("A | B C") == [[(False, "A"), (False, "B")], [(False, "C")]]
    bad = HINT_IT.replace("fatto: libro_preso", "fatto: libro_preso |").replace("indizio: Guarda in alto.\n", "")
    (tmp_path / "bad.txt").write_text(bad, encoding="utf-8")
    rb = hints.validate([str(tmp_path / "bad.txt")])["files"][str(tmp_path / "bad.txt")]
    assert any("«|»" in p for p in rb["problems"]) and any("indizio" in p for p in rb["problems"])
    other = HINT_IT.replace("libro_preso", "altro_flag")
    (tmp_path / "fr.txt").write_text(other, encoding="utf-8")
    assert not hints.validate([str(tmp_path / "it.txt"), str(tmp_path / "fr.txt")])["ok"]
    (tmp_path / "vocab.json").write_text(json.dumps({"flags": ["porta_aperta"], "items": ["chiave"],
                                                    "scenes": ["atrio"]}), encoding="utf-8")
    rv = hints.validate([str(tmp_path / "it.txt")], str(tmp_path / "vocab.json"))
    assert any("libro_preso" in p for p in rv["files"][str(tmp_path / "it.txt")]["problems"])
    single = HINT_IT.replace("LF:atrio:porta_aperta | obj:chiave", "obj:chiave")
    (tmp_path / "s.txt").write_text(single, encoding="utf-8")
    assert any("monotono" in w for w in hints.validate([str(tmp_path / "s.txt")])["files"][str(tmp_path / "s.txt")]["warnings"])


# ------------------------------------------------------------------ manual
def test_manual_check_and_html(tmp_path):
    md = tmp_path / "it.md"
    md.write_text("# Manuale\n\n## Avvio\n\nPremi **F8** per la versione *classica*.\n\n- uno\n- due\n\n"
                  "## Comandi\n\n| Tasto | Azione |\n|---|---|\n| H | aiuti |\n\n## Crediti\n\n> Nota.\n\n"
                  "![Mappa](img/mappa.png)\n", encoding="utf-8")
    c = manual.check(str(md), codepage="cp850")
    assert c["problems"] == ["immagine mancante: img/mappa.png"]
    (tmp_path / "img").mkdir()
    Image.new("RGB", (8, 8)).save(tmp_path / "img" / "mappa.png")
    assert manual.check(str(md))["problems"] == []
    r = manual.to_html(str(md), str(tmp_path / "out" / "it.html"), colors={"accent": "#224466"})
    page = open(r["html"], encoding="utf-8").read()
    assert "<b>F8</b>" in page and "#224466" in page and "<nav>" in page and r["sections"] == 3


# ------------------------------------------------------------------ GUI theme
def test_theme_recolor(tmp_path):
    base = tmp_path / "base"
    (base).mkdir()
    (tmp_path / "common").mkdir()
    (base / "THEMERC").write_text("[SCUMMVM_STX0.9.24:Base:Nessuno]\n%using ../common\n")
    (base / "a.stx").write_text("<palette>\n<color name = 'background'\n rgb = '1, 2, 3'\n/>\n"
                                "<color name = 'button_idle' rgb = '4, 5, 6'/>\n</palette>\n"
                                "<fonts><font id = 'text_default' file = 'x.bdf'/></fonts>\n")
    (tmp_path / "common" / "x.bdf").write_text("STARTFONT\n")
    font = tmp_path / "stile.ttf"
    font.write_bytes(b"\0\1\0\0fake")
    ui = tmp_path / "ui.png"
    a = np.zeros((40, 40, 3), np.uint8)
    a[:20] = (240, 230, 200)
    a[20:30] = (150, 30, 20)
    a[30:] = (20, 20, 25)
    Image.fromarray(a).save(ui)
    roles = theme.propose_palette(str(ui))
    assert set(roles) == set(theme.ROLES)
    r = theme.build(str(base), roles, str(tmp_path / "t.zip"), "Tema di prova", font_ttf=str(font))
    z = zipfile.ZipFile(tmp_path / "t.zip")
    assert "x.bdf" in z.namelist() and "stile.ttf" in z.namelist()
    stx = z.read("a.stx").decode()
    assert "'1, 2, 3'" not in stx and "scalable_file = 'stile.ttf'" in stx
    assert z.read("THEMERC").decode().startswith("[SCUMMVM_STX0.9.24:Tema di prova:")
    assert {"background", "button_idle"} <= set(r["colors_replaced"])
    assert theme.contrast("#000000", "#ffffff") == 21.0


# ------------------------------------------------------------------ local 16:9 techniques
def stripes(h=120, w=160):
    a = np.zeros((h, w, 3), np.uint8)
    for x in range(w):
        a[:, x] = (40 + (x // 8 % 2) * 120, 90, 160)
    a[:30] = (200, 210, 240)  # sky
    return a


def test_quilting_uses_only_painted_pixels_and_keeps_centre():
    src = stripes()
    W = src.shape[1] + 24
    wide = np.zeros((src.shape[0], W, 3), np.uint8)
    wide[:, 12:12 + src.shape[1]] = src
    mask = np.zeros(wide.shape[:2], bool)
    mask[:, :12] = True
    mask[:, -12:] = True
    # LaMa's guess: right layout (sky above, stripes below) but smooth colours
    guide = fake_lama(wide, mask.astype(np.float32))
    guide[mask] = (guide[mask].astype(int) * 0.8 + 25).astype(np.uint8)
    out = bands.quilt(guide, mask, (12, 12 + src.shape[1]))
    assert np.array_equal(out[:, 12:12 + src.shape[1]], src)
    colors = {tuple(c) for c in src.reshape(-1, 3)}
    band = out[mask].reshape(-1, 3)
    share = np.mean([tuple(c) in colors for c in band])
    assert share > 0.9, share


def test_band_checks_and_sharpening():
    rng = np.random.default_rng(3)
    base = (rng.random((90, 300, 3)) * 200 + 30).astype(np.uint8)
    img = Image.fromarray(base)
    blurred = np.asarray(img).copy()
    soft = np.asarray(img.filter(ImageFilter.GaussianBlur(3)))
    blurred[:, :30] = soft[:, :30]
    blurred[:, -30:] = soft[:, -30:]
    idx = bands.sharpness_index(blurred, 30, 30)
    assert idx["left"] < 0.6 and idx["right"] < 0.6
    sharp, amount, after = bands.unsharp_band(Image.fromarray(blurred), 30, 30)
    assert amount > 0 and after["left"] > idx["left"]
    assert np.array_equal(np.asarray(sharp)[:, 60:240], blurred[:, 60:240])  # centre untouched
    white = blurred.copy()
    white[:, :30] = 250
    assert not bands.band_check(white, 30, 30)["left"]["ok"]


def test_recipes_keep_centre():
    src = stripes()
    wide = np.zeros((src.shape[0], src.shape[1] + 20, 3), np.uint8)
    wide[:, 10:-10] = src
    mask = np.zeros(wide.shape[:2], bool)
    mask[:, :10] = mask[:, -10:] = True
    for out in (bands.recipe_rows(wide, mask, (10, 10 + src.shape[1])),
                bands.recipe_shift(wide, mask, (10, 10 + src.shape[1]), dx=16)):
        assert np.array_equal(out[:, 10:-10], src)
        assert out[5, 2].mean() > 100  # sky continued, not black


def fake_lama(img, mask):
    out = img.copy()
    cols = np.where(mask[0] == 0)[0]
    for x in np.where(mask[0] > 0)[0]:
        out[:, x] = img[:, cols[np.argmin(np.abs(cols - x))]]
    return out


def test_extensions_local_first_and_fal_only_with_budget(dump, tmp_path):
    from remaster_tools import gfx
    bgdir = str(dump / "dump" / "bg")
    gfx.batch_backgrounds(bgdir, str(tmp_path / "hd"), scale=3, use_ai=False)
    plan_path = str(tmp_path / "plan.json")
    widescreen.classify(bgdir, 320, 200, 1.0, plan_path)
    with pytest.raises(RuntimeError):
        falai.fill_function(falai.Budget(0), key="x")
    calls = []

    def poster(payload):
        calls.append(payload)
        import base64
        import io
        from PIL import Image as I
        im = I.open(io.BytesIO(base64.b64decode(payload["image_url"].split(",", 1)[1]))).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return {"images": [{"url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}]}
    budget = falai.Budget(1)
    paid = falai.fill_function(budget, poster=poster)
    plan = widescreen.make_extensions(plan_path, str(tmp_path / "hd"), str(tmp_path / "var"), 3, lama=fake_lama,
                                      paid_fill=paid, recipes={"aperta": {"kind": "rows"}}, only=["aperta"])
    aperta = next(s for s in plan["scenes"] if s["scene"] == "aperta")
    kinds = [v["kind"] for v in aperta["variants"]]
    assert kinds[:3] == ["inpaint", "quilt", "recipe-rows"] and "fal" in kinds and kinds[-1] == "borders"
    assert all("checks" in v for v in aperta["variants"] if v["kind"] != "borders")
    assert len(calls) == 1 and calls[0]["sync_mode"] is True and budget.used == 1
    with pytest.raises(RuntimeError):
        paid(np.zeros((10, 20, 3), np.uint8), np.ones((10, 20)))  # budget exhausted: no second call
    est = falai.estimate(100)
    assert est["max_images"] == 200 and est["max_usd"] == 10.0 and est["likely_usd"] < est["max_usd"]


# ------------------------------------------------------------------ patchable engine
def test_canary_pack_and_coverage(dump, tmp_path):
    res = assets.canary(str(dump / "dump"), str(tmp_path / "canary"), "it")
    assert res["text"] == 3 and res["bg"] == 4 and res["spr"] == 3
    tsv = open(tmp_path / "canary" / "text" / "it.tsv", encoding="utf-8").read()
    assert "«ESCI»" in tsv
    assert os.path.exists(tmp_path / "canary" / "gfx" / "spr" / "index.dat")
    cov = assets.coverage(str(dump / "dump"), str(tmp_path / "canary"), "it")
    assert cov["coverage"]["text/it"]["covered"] == 3 and not cov["problems"]
    with open(tmp_path / "canary" / "text" / "it.tsv", "a", encoding="utf-8") as f:
        f.write("deadbeef\tmai richiesto\n")
    cov = assets.coverage(str(dump / "dump"), str(tmp_path / "canary"), "it")
    assert cov["coverage"]["text/it"]["orphans"] == 1 and cov["problems"]


def test_project_asks_fal_and_manual(tmp_path):
    data = project.init("Avventura di prova", str(tmp_path))
    assert "manuale e aiuti in gioco" in project.missing_answers(data)
    project.set_key(data, "graphics.enabled", True)
    project.set_key(data, "graphics.widescreen.enabled", True)
    assert "fal.ai per le bande 16:9 (opzionale)" in project.missing_answers(data)
    assert data["graphics"]["widescreen"]["fill"] == "local"


def test_cli_new_commands(tmp_path):
    def run(*args):
        return json.loads(subprocess.run([sys.executable, RSTOOL, "--workdir", str(tmp_path), *args],
                                         capture_output=True, text=True, check=True).stdout)
    assert run("widescreen", "aspect", "--platform", "dos", "--w", "320", "--h", "200")["stretch"] == 1.2
    assert run("engine", "reference", "--platform", "atari-st")["emulators"][0]["name"] == "Hatari"
    assert run("widescreen", "fal-estimate", "--scenes", "10")["max_usd"] == 1.0
    r = subprocess.run([sys.executable, RSTOOL, "--workdir", str(tmp_path), "widescreen", "extend", "x.json",
                        "--hd", "hd", "--fal"], capture_output=True, text=True)
    assert r.returncode != 0 and "approved-images" in r.stderr
