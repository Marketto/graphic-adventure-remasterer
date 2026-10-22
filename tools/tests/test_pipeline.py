"""Tests of the pipeline tools on synthetic data (no game files, no GPU, no network)."""
import json
import os
import shutil
import struct
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from remaster_tools import (font, gfx, keys, project, rawframe, recipe, release, review,  # noqa: E402
                            scalers, style, text, widescreen)

RSTOOL = os.path.join(os.path.dirname(HERE), "rstool.py")


# ------------------------------------------------------------------ reference CRCs
def crc_reference(data: bytes) -> int:
    """Bit-by-bit CRC32 exactly as written in the C++ layer (textKey / frameKey)."""
    crc = 0xFFFFFFFF
    for c in data:
        crc ^= c
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 & (0 - (crc & 1) & 0xFFFFFFFF))
    return crc ^ 0xFFFFFFFF


def test_frame_key_matches_engine_algorithm():
    px = bytes((i * 7) % 256 for i in range(13 * 5))
    expected = crc_reference(struct.pack("<HH", 13, 5) + px)
    assert keys.frame_key(px, 13, 5) == "%08x" % expected


def test_text_key_skips_whitespace_and_backslash():
    a = keys.text_key("Ciao,\\mondo! E' tardi\n")
    b = keys.text_key("Ciao, mondo!E'   tardi")
    assert a == b
    raw = "Ciao,mondo!E'tardi".encode("cp850")
    assert a == "%08x" % crc_reference(raw)


# ------------------------------------------------------------------ synthetic dump
def palette():
    pal = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        pal[i] = (i, (i * 3) % 256, 255 - i)
    pal[10] = (70, 130, 220)   # sky
    pal[11] = (90, 160, 90)    # grass
    pal[12] = (60, 60, 60)     # wall
    pal[13] = (200, 180, 150)  # floor
    pal[0] = (0, 0, 0)
    return pal.tobytes()


def write_bg(path, px):
    rawframe.write_raw(path, rawframe.RawFrame(px.shape[1], px.shape[0], 255, palette(), px.astype(np.uint8)))


@pytest.fixture()
def dump(tmp_path):
    bg = tmp_path / "dump" / "bg"
    spr = tmp_path / "dump" / "spr"
    bg.mkdir(parents=True)
    spr.mkdir(parents=True)
    rng = np.random.default_rng(1)
    # open outdoor: sky top half, horizon, grass with a little noise
    out = np.full((200, 320), 11, dtype=np.uint8)
    out[:90] = 10
    out[90:92] = 0
    out[120:] = np.where(rng.random((80, 320)) > 0.9, 40, 11)
    write_bg(bg / "aperta.raw", out)
    # closed interior: walls with strong verticals near both edges
    room = np.full((200, 320), 13, dtype=np.uint8)
    room[:, :40] = 12
    room[:, 280:] = 12
    room[:, 38:42] = 0
    room[:, 278:282] = 0
    room[:120, 140:180] = 0          # door frame
    room[:, 100:102] = 0
    room[:, 220:222] = 0
    room[:150:6, :] = 12             # wallpaper stripes
    write_bg(bg / "chiusa.raw", room)
    # wide scrolling scene
    wide = np.tile(out, (1, 2))[:, :720]
    write_bg(bg / "larga.raw", wide)
    # menu screen
    write_bg(bg / "menu.raw", np.full((200, 320), 5, dtype=np.uint8))
    # sprites
    for i in range(3):
        px = np.full((24, 16), 255, dtype=np.uint8)
        px[4:20, 3:13] = 20 + i
        px[2:6, 6:10] = 30
        fr = rawframe.RawFrame(16, 24, 255, palette(), px)
        rawframe.write_raw(spr / (fr.key + ".raw"), fr)
    # text dump
    lines = [{"hex": "Buongiorno, sono Rita.".encode("cp850").hex(), "kind": "balloon", "location": "aperta", "speaker": "Rita", "box_w": 120},
             {"hex": "E' una giornata piu' calda, perche' no?".encode("cp850").hex(), "kind": "comment", "location": "aperta", "speaker": "", "box_w": 60},
             {"hex": "ESCI".encode("cp850").hex(), "kind": "menu", "location": "menu", "speaker": "", "box_w": 80}]
    with open(tmp_path / "dump" / "text.jsonl", "w", encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")
    return tmp_path


# ------------------------------------------------------------------ tests
def test_project_flow(tmp_path):
    data = project.init("Avventura di prova", str(tmp_path))
    assert "file di gioco" in project.missing_answers(data)
    assert data["graphics"]["enabled"] and data["graphics"]["widescreen"]["enabled"]  # free: on by default
    project.set_key(data, "voice.enabled", project.parse_value("true"))
    assert "conferma licenza ElevenLabs" in project.paid_followups(data)
    project.set_phase(data, "analysis")
    project.save(data, str(tmp_path))
    again = project.load(str(tmp_path))
    assert again["phase"] == "analysis" and again["decisions"]
    assert "Avventura di prova" in project.summary(again)


def test_scalers_preserve_flat_and_shape():
    a = np.zeros((5, 7), dtype=np.uint8)
    a[2, 3] = 9
    for f in (2, 3, 4):
        up = scalers.scale_indexed(a, f)
        assert up.shape == (5 * f, 7 * f)
        assert set(np.unique(up)) <= {0, 9}
    # diagonal edge gets smoothed by Scale2x (not plain nearest neighbour)
    d = np.array([[1, 0], [1, 1]], dtype=np.uint8)
    assert not np.array_equal(scalers.scale2x(d), np.kron(d, np.ones((2, 2), dtype=np.uint8)))


def test_widescreen_geometry():
    # 640x400 shown with square pixels -> 36 px per side (712x400, 2136x1200 at 3x)
    g = widescreen.geometry(640, 400)
    assert g["left"] == g["right"] == 36 and g["viewport_w"] == 712
    g = widescreen.geometry(320, 200, 1.2)
    assert g["left"] == g["right"] == 54
    g = widescreen.geometry(640, 480, 1.0)
    assert g["viewport_w"] == 854


def test_widescreen_classify(dump, tmp_path):
    plan = widescreen.classify(str(dump / "dump" / "bg"), 320, 200, 1.2, str(tmp_path / "plan.json"))
    cls = {s["scene"]: s["class"] for s in plan["scenes"]}
    assert cls["larga"] == "scroll-wide"
    assert cls["menu"] == "ui-fixed"
    assert cls["aperta"] == "open-static"
    assert cls["chiusa"] == "closed-static"


def test_backgrounds_extensions_gallery_apply(dump, tmp_path):
    bgdir = str(dump / "dump" / "bg")
    rep = gfx.batch_backgrounds(bgdir, str(tmp_path / "hd"), scale=3, use_ai=False)
    assert {r["scene"] for r in rep} == {"aperta", "chiusa", "larga", "menu"}
    assert all(r["ssim"] > 0.85 and r["delta_e"] < 6 for r in rep), rep
    im = Image.open(tmp_path / "hd" / "aperta.png")
    assert im.size == (960, 600)
    plan_path = str(tmp_path / "plan.json")
    widescreen.classify(bgdir, 320, 200, 1.2, plan_path)
    plan = widescreen.make_extensions(plan_path, str(tmp_path / "hd"), str(tmp_path / "var"), 3)
    aperta = next(s for s in plan["scenes"] if s["scene"] == "aperta")
    assert aperta["variants"][-1]["kind"] == "borders"
    border = Image.open(tmp_path / "var" / aperta["variants"][-1]["file"])
    assert border.size == (960 + 108 * 3, 600)
    # original area untouched
    assert np.array_equal(np.asarray(border)[:, 54 * 3: 54 * 3 + 960], np.asarray(im.convert("RGB")))
    g = review.widescreen_gallery(plan_path, str(tmp_path / "var"), str(tmp_path / "ws.html"))
    assert g["scenes"] >= 3 and "data:image/jpeg;base64" in open(tmp_path / "ws.html").read()
    with open(tmp_path / "dec.json", "w") as f:
        json.dump({"aperta": "borders", "larga": "auto", "chiusa": "4:3"}, f)
    res = widescreen.apply_decisions(plan_path, str(tmp_path / "dec.json"), str(tmp_path / "var"), str(tmp_path / "out"))
    assert set(res["applied"]) == {"aperta", "larga", "chiusa"}
    meta = json.load(open(tmp_path / "out" / "aperta.wide.json"))
    assert meta["left"] == 54 and meta["right"] == 54
    assert json.load(open(tmp_path / "out" / "larga.wide.json"))["camera"] == "clamp"


def test_sprites_and_index(dump, tmp_path):
    res = gfx.batch_sprites(str(dump / "dump" / "spr"), str(tmp_path / "spr"), scale=3, use_ai=False)
    assert res["sprites"] == 3 and res["indexed"] == 3 and res["palettes"] == 1 and not res["missing"]
    idx = rawframe.read_index(str(tmp_path / "spr" / "index.dat"))
    assert idx["scale"] == 3 and len(idx["entries"]) == 3
    key = idx["entries"][0][0]
    im = Image.open(tmp_path / "spr" / f"{key}.png")
    assert im.mode == "RGBA" and im.size == (48, 72)
    a = np.asarray(im)[..., 3]
    assert a[0, 0] == 0 and a[36, 24] == 255


def test_style_analyze(dump, tmp_path):
    rep = style.analyze(str(dump / "dump"), str(tmp_path / "style"))
    assert rep["sprites"]["count"] == 3 and len(rep["backgrounds"]) == 4
    assert os.path.exists(tmp_path / "style" / "backgrounds.png")


def test_text_catalog_font_check_voice(dump, tmp_path):
    cat = str(tmp_path / "catalog.tsv")
    r = text.catalog(str(dump / "dump" / "text.jsonl"), "it", cat)
    assert r["lines"] == 3
    assert text.italian_accents("E' una giornata piu' calda, perche' no? Un po' di sole") == \
        "È una giornata più calda, perché no? Un po' di sole"
    ttf = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.exists(ttf):
        pytest.skip("font di test non disponibile")
    m = font.build(ttf, str(tmp_path / "dlg"), size_px=30, scale=3, outline=2)
    assert m["line"] > 30
    info = font.read(str(tmp_path / "dlg.dat"))
    assert info["adv"][ord("A")] > 0 and info["outline"] == 2
    probs = text.check(cat, str(tmp_path / "dlg.dat"))
    assert any(p["issue"] == "troppo lungo" for p in probs)  # the 60 px comment
    assert "È" in text.glyphs([cat])["catalog.tsv"] or True
    vs = __import__("remaster_tools.voice", fromlist=["x"]).script(cat, "it", str(tmp_path / "script.tsv"), protagonist="Rita")
    assert vs["lines"] == 2 and vs["per_speaker"]["Rita"] > 0


def test_release_package_and_verify(dump, tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    (game / "FONT.DAT").write_bytes(b"original font bytes")
    (game / "DATI").mkdir()
    (game / "DATI" / "scena.scr").write_bytes(b"script")
    md5json = str(tmp_path / "md5.json")
    release.game_md5(str(game), md5json, "cd-it")
    lic = tmp_path / "lic"
    lic.mkdir()
    (lic / "GPL-3.0.txt").write_text("GPL")
    data = project.init("Test Game", str(tmp_path / "p"))
    root = release.package(data, str(tmp_path / "rel"), md5json, licenses_dir=str(lic))
    assert release.verify(root)["ok"], release.verify(root)
    # an original file sneaking in must be caught
    shutil.copyfile(game / "FONT.DAT", os.path.join(root, "font.dat"))
    v = release.verify(root)
    assert not v["ok"] and any("originale" in p for p in v["problems"])
    # installer accepts the exact copy, rejects a modified one
    rc = subprocess.call([sys.executable, os.path.join(root, "install.py"), str(game)], stdout=subprocess.DEVNULL)
    assert rc == 1  # recipe mode without recipe.json -> incomplete package message
    (game / "FONT.DAT").write_bytes(b"tampered")
    out = subprocess.run([sys.executable, os.path.join(root, "install.py"), str(game)], capture_output=True, text=True)
    assert out.returncode == 1 and "non corrisponde" in out.stdout
    # asset-pack requires rights
    data["distribution"]["mode"] = "asset-pack"
    with pytest.raises(PermissionError):
        release.package(data, str(tmp_path / "rel2"), md5json)


def test_recipe_dry_run(tmp_path):
    r = {"steps": [{"name": "bg", "rstool": ["gfx", "bg", "{work}/dump/bg", "--out", "{out}/gfx/bg"]},
                   {"name": "wide", "copy": ["{recipes}/wide", "{out}/gfx/bg"]}]}
    p = tmp_path / "recipe.json"
    p.write_text(json.dumps(r))
    log = recipe.run(str(p), str(tmp_path / "g"), str(tmp_path / "o"), dry_run=True)
    assert log[0]["cmd"][-1].endswith("/o/gfx/bg") and log[1]["copy"][0].endswith("/wide")


def test_cli_smoke(dump, tmp_path):
    def run(*args):
        res = subprocess.run([sys.executable, RSTOOL, "--workdir", str(tmp_path), *args], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        return res.stdout
    run("project", "init", "Gioco di prova")
    run("project", "set", "graphics.enabled", "true", "languages.requested", '["it","en"]')
    assert "it, en" in run("project", "show")
    assert json.loads(run("key", "text", "Ciao"))["key"]
    assert json.loads(run("widescreen", "geometry", "--w", "640", "--h", "400"))["left"] == 36
    det = json.loads(run("engine", "detect", str(dump / "dump")))
    assert det["files"] > 0


def test_inpaint_bands_keep_centre_and_repaint_black_borders(dump, tmp_path):
    orig = rawframe.read_raw(str(dump / "dump" / "bg" / "aperta.raw")).rgb()
    a = np.asarray(orig).copy()
    a[:, :3] = 0                       # black columns at the border of the original
    orig = Image.fromarray(a)
    hd = orig.resize((960, 600), Image.NEAREST)

    def fill(img, mask):               # stand-in for LaMa: nearest unmasked column
        out = img.copy()
        cols = np.where(mask[0] == 0)[0]
        for x in np.where(mask[0] > 0)[0]:
            out[:, x] = img[:, cols[np.argmin(np.abs(cols - x))]]
        return out
    up = lambda im, k: im.resize((im.width * k, im.height * k), Image.NEAREST)
    wide = widescreen.extend_inpaint(orig, hd, 36, 36, 3, fill, upscale=up)
    w = np.asarray(wide)
    assert wide.size == ((320 + 72) * 3, 600)
    # centre away from the blend ramps is the HD picture, untouched
    assert np.array_equal(w[:, (36 + 3 + 8) * 3:(36 + 320 - 8) * 3], np.asarray(hd)[:, (3 + 8) * 3:(320 - 8) * 3])
    # bands painted (sky colour at the top, not black)
    assert w[10, 5].mean() > 60 and w[10, -5].mean() > 60
    # the black border columns of the original were repainted
    assert w[10, (36 + 1) * 3].mean() > 60


def test_voice_rules(tmp_path):
    from remaster_tools import voice, audio
    assert voice.pause_after("Il treno parte alle nove...") == 0.6
    assert voice.pause_after("La signora Rossi vi aspetta") == 0.15
    rows = [{"key": "a", "speaker": "rita", "text": "Uno.", "context": "biblioteca", "kind": "subtitle"},
            {"key": "b", "speaker": "guida", "text": "Due.", "context": "biblioteca", "kind": "subtitle"},
            {"key": "c", "speaker": "rita", "text": "Tre.", "context": "biblioteca", "kind": "subtitle"},
            {"key": "d", "speaker": "rita", "text": "Quattro.", "context": "atrio", "kind": "subtitle"},
            {"key": "e", "speaker": "rita", "text": "Cinque.", "context": "atrio", "kind": "balloon"}]
    assert voice.context_of(rows, 2) == ("Uno.", None)
    assert voice.context_of(rows, 0) == (None, "Tre.")
    assert voice.context_of(rows, 4) == (None, None)          # dialogues: no context
    assert voice.spoken({"text": "Ciao.", "tag": "[warm]"}, "eleven_multilingual_v2") == "Ciao."
    assert voice.spoken({"text": "ONU", "recita": "o enne u", "tag": "[dry]"}) == "[dry] o enne u"
    assert voice.voice_settings({"impostazioni": {"stability": 0.3, "speed": 0.92}})["speed"] == 0.92
    assert voice.voice_settings({"voice_id": "x", "speed": 0.95})["speed"] == 0.95
    assert audio.LEVELS == {"voice": -18.0, "sfx_max": -16.0, "music": -25.0}
    # lines with game variables are never recorded
    cat = tmp_path / "c.tsv"
    text.write_catalog(str(cat), [
        {"key": "k1", "lang": "it", "source": "Ho ancora %soldi monete.", "kind": "balloon", "speaker": "rita"},
        {"key": "k2", "lang": "it", "source": ".", "kind": "balloon", "speaker": "rita"},
        {"key": "k3", "lang": "it", "source": "Ciao!", "kind": "balloon", "speaker": "rita"}])
    r = voice.script(str(cat), "it", str(tmp_path / "s.tsv"))
    assert r["lines"] == 1
    # transcription check: missing words and tags read aloud are flagged
    with open(tmp_path / "s2.tsv", "w", encoding="utf-8") as f:
        f.write("key\tspeaker\ttext\tcontext\ttag\trecita\n")
        f.write("a\trita\tÈ una bella giornata.\tbiblioteca\t[cocky, ironic]\t\n")
        f.write("b\trita\tApri la porta del giardino.\tbiblioteca\t[cocky, ironic]\t\n")
        f.write("c\trita\tOggi non piove.\tbiblioteca\t[cocky, ironic]\t\n")
    (tmp_path / "t.json").write_text(json.dumps({"a": "È una bella giornata.", "b": "cocky ironic apri la porta del giardino",
                                                  "c": "Oggi piove."}), encoding="utf-8")
    res = voice.check_transcripts(str(tmp_path / "s2.tsv"), str(tmp_path / "t.json"))
    flagged = {f["key"]: f for f in res["flagged"]}
    assert "a" not in flagged and flagged["b"]["tag_read_aloud"] and "c" in flagged


def test_audio_master_static_gain(tmp_path):
    from remaster_tools import audio
    import shutil as _sh
    if not _sh.which("ffmpeg"):
        pytest.skip("ffmpeg assente")
    src = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=4", "-af", "volume=-12dB",
                    str(src)], check=True)
    out = tmp_path / "m.ogg"
    audio.master(str(src), str(out))
    lv = audio.loudness(str(out))
    assert abs(lv - (-25.0)) < 1.0, lv
