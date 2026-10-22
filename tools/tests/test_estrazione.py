"""Extraction without the Layer (adapter + dump contract), PNG dumps, 16:9 classifier rules,
pixel aspect measured on a round shape, MIDI music/effects, voice estimate, links to third
party sites. All data are invented."""
import json
import os
import shutil
import struct
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
RSTOOL = os.path.join(os.path.dirname(HERE), "rstool.py")

from remaster_tools import assets, audio, detect, extract, manual, platforms, style, voice, widescreen  # noqa: E402


def _png_dump(root):
    bg, spr, mid = root / "bg", root / "spr", root / "midi"
    for d in (bg, spr, mid):
        d.mkdir(parents=True)
    rng = np.random.default_rng(3)
    room = (rng.random((144, 320, 3)) * 60 + 40).astype(np.uint8)
    Image.fromarray(room).save(bg / "stanza_01.png")
    Image.new("RGB", (320, 200), (12, 12, 12)).save(bg / "stanza_02.png")
    Image.new("RGB", (8, 200), (0, 0, 0)).save(bg / "stanza_03.png")
    json.dump({"stanza_01": "cantina", "stanza_02": "mappa-mondo"}, open(bg / "names.json", "w"))
    for i in range(3):
        im = Image.new("RGBA", (24, 32), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle([4, 4, 19, 27], fill=(200, 120, 60, 255), outline=(10, 10, 10, 255))
        im.save(spr / f"fr{i}.png")
    json.dump({"frames": [f"fr{i}" for i in range(7)]}, open(spr / "index.json", "w"))
    rows = [{"hex": "Ciao!".encode("cp850").hex(), "kind": "balloon", "voice": "v1", "speaker": "Pia"},
            {"hex": "Ciao!".encode("cp850").hex(), "kind": "balloon", "voice": "v2", "speaker": "Pia"},
            {"hex": "Che bella giornata.".encode("cp850").hex(), "kind": "question", "speaker": ""},
            {"hex": "Andiamo via".encode("cp850").hex(), "kind": "choice"}]
    with open(root / "text.jsonl", "w") as f:
        f.write("\n".join(json.dumps(r) for r in rows) + "\n")
    json.dump({"v1": {"file": "voice/v1.wav", "lipsync": True}, "v2": {"file": "voice/v2.wav"}},
              open(root / "voice-index.json", "w"))
    (mid / "brano.mid").write_bytes(_midi(notes=120, seconds=30))
    (mid / "colpo.mid").write_bytes(_midi(notes=4, seconds=1))
    (mid / "note.json").write_text("{}")
    return root


def _midi(notes, seconds, div=96):
    """Format 0, 120 bpm: `notes` evenly spaced over `seconds`."""
    ticks = int(seconds * 2 * div)
    step = max(1, ticks // max(1, notes))
    ev = bytearray(b"\x00\xff\x51\x03\x07\xa1\x20")  # tempo 500000 µs per quarter
    for k in range(notes):
        ev += bytes([0x00, 0x90, 60, 100])
        d = step
        vlq = [d & 0x7F]
        while d > 127:
            d >>= 7
            vlq.insert(0, (d & 0x7F) | 0x80)
        ev += bytes(vlq) + bytes([0x80, 60, 0])
    ev += b"\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, div) + b"MTrk" + struct.pack(">I", len(ev)) + bytes(ev)


def test_dump_contract_and_adapter(tmp_path):
    dump = _png_dump(tmp_path / "dump")
    res = extract.validate_dump(str(dump))
    assert res["ok"], res["errors"]
    c = res["counts"]
    assert c["backgrounds"] == 3 and c["text_rows"] == 4 and c["text_unique"] == 3
    assert c["voice_clips"] == 2 and c["voice_lipsync"] == 1 and c["midi_files"] == 2
    # broken parts are reported
    with open(dump / "text.jsonl", "a") as f:
        f.write('{"kind": "balloon"}\n')
    (dump / "midi" / "rotto.mid").write_bytes(b"RIFF....")
    bad = extract.validate_dump(str(dump))
    assert not bad["ok"] and any("hex" in e for e in bad["errors"]) and any("MThd" in e for e in bad["errors"])
    assert not extract.validate_dump(str(tmp_path / "vuoto"))["ok"]
    # the adapter of the private repository: a script that writes the dump
    script = tmp_path / "adattatore.py"
    script.write_text("import argparse, os, json\nfrom PIL import Image\n"
                      "p = argparse.ArgumentParser(); p.add_argument('--game'); p.add_argument('--out')\n"
                      "a = p.parse_args(); os.makedirs(os.path.join(a.out, 'bg'), exist_ok=True)\n"
                      "Image.new('RGB', (320, 200), (90, 30, 30)).save(os.path.join(a.out, 'bg', 'r1.png'))\n")
    r = subprocess.run([sys.executable, RSTOOL, "engine", "extract", "--adapter", str(script),
                        "--game", str(tmp_path), "--out", str(tmp_path / "d2")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["ok"] and out["counts"]["backgrounds"] == 1 and out["adapter"]["returncode"] == 0
    assert extract.adapter_command("estrai {game} -o {out}", "/g", "/o") == ["estrai", "/g", "-o", "/o"]


def test_inventory_and_style_read_png(tmp_path):
    dump = _png_dump(tmp_path / "dump")
    inv = assets.inventory(str(dump), str(tmp_path / "a.csv"))
    assert inv["backgrounds"] == 3
    assert inv["sprite_frames"] == 7          # from spr/index.json
    assert inv["text_lines"] == 3 and inv["text_rows"] == 4   # unique texts, not JSON rows
    assert inv["midi_files"] == 2             # only .mid
    rep = style.analyze(str(dump), str(tmp_path / "style"))
    assert rep["sprites"]["count"] == 7 and rep["sprites"]["outline"]["border_luma"] < 30
    assert all(b["colors_used"] >= 1 and b["dither"] is not None for b in rep["backgrounds"])


def test_classifier_rules(tmp_path):
    bg = tmp_path / "bg"
    bg.mkdir()
    rng = np.random.default_rng(5)

    def noisy(h, w, base):
        return np.clip(np.array(base) + rng.normal(0, 6, (h, w, 3)), 0, 255).astype(np.uint8)
    # dark blue top (ceiling of a night interior) with walls: not a sky
    dark = noisy(144, 320, (20, 25, 60))
    dark[:, 30:34] = 200
    dark[:, 286:290] = 200
    Image.fromarray(dark).save(bg / "a_buia.png")
    # bright smooth blue sky over a field: open
    sky = np.zeros((144, 320, 3), np.uint8)
    for y in range(60):
        sky[y] = (110 + y, 160 + y // 2, 235)
    sky[60:] = noisy(84, 320, (80, 150, 70))
    Image.fromarray(sky).save(bg / "b_campo.png")
    Image.new("RGB", (320, 200), (0, 0, 0)).save(bg / "c_tinta.png")           # flat: UI
    Image.fromarray(noisy(200, 12, (50, 50, 50))).save(bg / "d_fittizia.png")   # dummy room
    Image.fromarray(noisy(144, 380, (60, 50, 40))).save(bg / "e_stretta.png")   # scroll-narrow, closed sides
    Image.fromarray(noisy(144, 320, (90, 80, 70))).save(bg / "f_ritratto.png")  # named as a close-up
    Image.fromarray(noisy(144, 700, (90, 80, 70))).save(bg / "g_mappa.png")     # wide map: still scrolls
    json.dump({"f_ritratto": "cu-ritratto", "g_mappa": "mappa"}, open(bg / "names.json", "w"))
    plan = widescreen.classify(str(bg), 320, 200, 1.2)
    cls = {s["scene"]: s for s in plan["scenes"]}
    assert cls["a_buia"]["class"] == "closed-static"
    assert cls["b_campo"]["class"] == "open-static"
    assert cls["c_tinta"]["class"] == "ui-fixed"
    assert cls["d_fittizia"]["class"] == "skip"
    assert cls["e_stretta"]["class"] == "scroll-narrow" and cls["e_stretta"]["sides"] == "closed"
    assert cls["f_ritratto"]["class"] == "ui-fixed" and cls["f_ritratto"]["room_name"] == "cu-ritratto"
    assert cls["g_mappa"]["class"] == "scroll-wide"
    assert plan["counts"]["scroll-narrow-open"] == 0 and plan["counts"]["skip"] == 1
    assert widescreen.count_inventable(plan) == 1
    # play area lower than the screen: the interface bar below is reported
    assert plan["ui_bar"]["playfield_h"] == 144 and plan["ui_bar"]["bar_h"] == 56
    assert plan["scroll_wide_rule"].startswith("larghezza del fondale ≥ viewport")


def test_aspect_measure_on_a_split_disc(tmp_path):
    # a disc drawn for pixels stretched by 1.2 (w/h = 1.2), split in four rooms
    big = Image.new("RGB", (640, 400), (0, 0, 0))
    ImageDraw.Draw(big).ellipse([80, 40, 80 + 384, 40 + 320], fill=(180, 150, 90))
    paths = []
    for k, (x, y) in enumerate(((0, 0), (320, 0), (0, 200), (320, 200))):
        p = tmp_path / f"q{k}.png"
        big.crop((x, y, x + 320, y + 200)).save(p)
        paths.append(str(p))
    r = platforms.aspect_measure(paths, compose=(2, 2), out_path=str(tmp_path / "m.png"))
    assert r["closest"] == 1.2 and abs(r["ratio"] - 1.2) < 0.02 and 0.9 <= r["ellipse_fill"] <= 1.1
    one = platforms.aspect_measure([str(tmp_path / "q0.png")], box=(0, 0, 320, 200), color="#b4965a")
    assert one["shape_px"][0] > 0
    with pytest.raises(ValueError):
        platforms.aspect_measure(paths[:3], compose=(2, 2))


def test_midi_music_or_effect(tmp_path):
    dump = _png_dump(tmp_path / "dump")
    st = audio.midi_stats(str(dump / "midi" / "brano.mid"))
    assert abs(st["seconds"] - 30) < 1 and st["notes"] == 120
    r = audio.midi_classify(str(dump / "midi"))
    assert [m["file"] for m in r["music"]] == ["brano.mid"] and [m["file"] for m in r["sfx"]] == ["colpo.mid"]
    # a wrong track length (seen in real extractions) does not break the parser
    b = bytearray(_midi(10, 2))
    b[18:22] = struct.pack(">I", len(b))
    (tmp_path / "lungo.mid").write_bytes(bytes(b))
    assert audio.midi_stats(str(tmp_path / "lungo.mid"))["notes"] == 10


def test_voice_estimate_unique_texts_and_target_length(tmp_path):
    dump = _png_dump(tmp_path / "dump")
    e = voice.estimate(str(dump / "text.jsonl"), dedupe=True, expand=1.12)
    # the choice is not spoken; "Ciao!" is recorded once
    assert e["rows_spoken"] == 3 and e["texts_unique"] == 2
    chars = len("Ciao!") + len("Che bella giornata.")
    assert e["chars_source"] == chars and e["credits"] == round(chars * 1.12 * 0.43 * 1.15)
    assert voice.estimate(str(dump / "text.jsonl"), dedupe=False)["chars_source"] == chars + len("Ciao!")


def test_detect_reports_links_to_third_party_sites(tmp_path):
    g = tmp_path / "gioco"
    g.mkdir()
    (g / "GIOCO.EXE").write_bytes(b"MZ")
    (g / "Scarica altri giochi.url").write_text("[InternetShortcut]\nURL=https://giochi-gratis.example/\n")
    (g / "leggimi.txt").write_text("Visita https://www.scummvm.org e https://altro-sito.example/pagina\n")
    (g / "manuale.txt").write_text("Nessun collegamento qui.\n")
    links = detect.third_party_links(str(g))
    files = {x["file"]: x for x in links}
    assert set(files) == {"Scarica altri giochi.url", "leggimi.txt"}
    assert files["leggimi.txt"]["hosts"] == ["altro-sito.example"]
    res = detect.detect(str(g), binary="/nonexistent/scummvm")
    assert res["third_party_links"] and "copia propria" in res["warning"]


@pytest.mark.skipif(not all(shutil.which(t) for t in ("pdftotext", "pdftoppm", "tesseract")),
                    reason="poppler/tesseract non installati")
def test_manual_ocr_of_a_scanned_pdf(tmp_path):
    im = Image.new("RGB", (1240, 400), "white")
    d = ImageDraw.Draw(im)
    try:
        from PIL import ImageFont
        font = ImageFont.load_default(size=64)
    except TypeError:
        pytest.skip("Pillow troppo vecchio per il font di default ridimensionabile")
    d.text((60, 150), "OPEN THE DOOR", fill="black", font=font)
    pdf = tmp_path / "manuale.pdf"
    im.save(pdf, resolution=150)
    r = manual.ocr(str(pdf), str(tmp_path / "ocr"), dpi=150)
    assert r["method"].startswith("tesseract") and r["pages"] == 1
    assert "DOOR" in open(tmp_path / "ocr" / "all.txt").read().upper()
