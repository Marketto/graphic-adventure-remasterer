"""Automatic pixel aspect: round shapes found in the dump, decision alone when clear, question only
in doubt. Synthetic pictures only (invented discs, rings, a map split between pictures)."""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from remaster_tools import plan, platforms, project  # noqa: E402

RSTOOL = os.path.join(os.path.dirname(HERE), "rstool.py")


def scenes(folder, stretch, n=3, seed=1):
    """Invented scenes drawn for a display that stretches pixels by `stretch`: round things seen
    from the front (discs, rings: w/h = stretch), round things on the floor in perspective (much
    wider), a few tall non-round shapes, on a dithered background."""
    rng = np.random.default_rng(seed)
    os.makedirs(folder, exist_ok=True)
    for k in range(n):
        bg = rng.integers(0, 2, (150, 240))
        a = np.where(bg[..., None] == 1, (40, 60, 90), (44, 66, 96)).astype(np.uint8)
        im = Image.fromarray(a, "RGB")
        d = ImageDraw.Draw(im)
        for j, h in enumerate((16, 22, 30)):
            w = round(h * stretch)
            x, y = 10 + j * 70, 10 + k * 3
            d.ellipse([x, y, x + w - 1, y + h - 1], fill=(200, 40 + 30 * j, 40))
        h = 26
        w = round(h * stretch)
        d.ellipse([20, 60, 20 + w - 1, 60 + h - 1], fill=(230, 220, 60))
        d.ellipse([26, 66, 20 + w - 7, 60 + h - 7], fill=(10, 10, 10))  # ring
        d.ellipse([90, 100, 90 + 70, 100 + 22], fill=(120, 200, 120))  # table top in perspective
        d.ellipse([180, 60, 180 + 14, 60 + 34], fill=(220, 220, 220))  # an egg, not round
        im.save(os.path.join(folder, f"scene_{k}.png"))
    return folder


def quarter_map(folder, stretch):
    """A round map seen from above, split in 4 pictures of 160x100: each holds a quarter arc."""
    os.makedirs(folder, exist_ok=True)
    big = Image.new("RGB", (320, 200), (0, 0, 0))
    d = ImageDraw.Draw(big)
    b = 90
    a = round(b * stretch)
    d.ellipse([160 - a, 100 - b, 160 + a, 100 + b], fill=(90, 120, 80))
    d.ellipse([160 - a // 2, 100 - b // 2, 160 + a // 2, 100 + b // 2], fill=(0, 0, 0))
    for i, (x, y) in enumerate(((0, 0), (160, 0), (0, 100), (160, 100))):
        big.crop((x, y, x + 160, y + 100)).save(os.path.join(folder, f"map_{i}.png"))
    return folder


def test_shapes_measure_the_stretch(tmp_path):
    for s in (1.0, 1.2):
        sh = platforms.find_round_shapes([scenes(str(tmp_path / f"s{s}"), s)])
        est = platforms.estimate_from_shapes(sh, [1.0, 1.2])
        assert est["verdict"] == "agree" and est["best"] == s, est
        assert est["perspective_or_wide"] >= 1 and est["tall"] >= 1  # table top and egg set aside
        assert any(x["kind"] == "ring" for x in sh)


def test_quarter_arcs_of_a_split_map(tmp_path):
    sh = platforms.find_round_shapes([quarter_map(str(tmp_path / "m"), 1.2)])
    arcs = [x for x in sh if x["kind"] == "arc"]
    assert arcs and all(abs(x["ratio"] - 1.2) < 0.06 for x in arcs), arcs


def test_auto_when_table_and_shapes_agree(tmp_path):
    res = platforms.aspect_auto("dos", 320, 200, 1993, evidence=[scenes(str(tmp_path / "a"), 1.2)],
                                sheet_out=str(tmp_path / "sheet.png"))
    assert res["decided_by"] == "auto" and res["stretch"] == 1.2 and res["confidence"] == "alta"
    assert "sheet" not in res
    # square pixels: the table is sure, no evidence needed
    win = platforms.aspect_auto("windows", 640, 480)
    assert win["decided_by"] == "auto" and win["stretch"] == 1.0


def test_ask_when_in_doubt(tmp_path):
    sheet = str(tmp_path / "sheet.png")
    # evidence against a sure table: ask, with the comparison sheet
    res = platforms.aspect_auto("dos", 320, 200, 1993, evidence=[scenes(str(tmp_path / "q"), 1.0)],
                                sheet_out=sheet)
    assert res["decided_by"] == "ask" and res["stretch"] is None and res["proposed"] == 1.0
    assert os.path.exists(res["sheet"]) and any("contraddicono" in r for r in res["reasons"])
    # medium confidence without evidence; digitized art without evidence
    assert platforms.aspect_auto("dos", 640, 400, 1995)["decided_by"] == "ask"
    dig = platforms.aspect_auto("dos", 320, 200, 1993, art="digitized")
    assert dig["decided_by"] == "ask" and any("digitalizzata" in r for r in dig["reasons"])


def test_evidence_settles_medium_confidence(tmp_path):
    res = platforms.aspect_auto("dos", 640, 400, 1995, evidence=[scenes(str(tmp_path / "m"), 1.2)])
    assert res["decided_by"] == "auto" and res["stretch"] == 1.2
    m = tmp_path / "measure.json"
    m.write_text(json.dumps({"ratio": 1.226, "ellipse_fill": 0.98}))
    res = platforms.aspect_auto("amiga-ntsc", 320, 200, measures=[str(m)])
    assert res["decided_by"] == "auto" and res["stretch"] == 1.2
    m.write_text(json.dumps({"ratio": 1.1}))  # halfway: no candidate
    assert platforms.aspect_auto("dos", 320, 200, measures=[str(m)])["decided_by"] == "ask"


def test_record_and_questions(tmp_path):
    wd = str(tmp_path / "p")
    data = project.init("Prova", wd)
    data = project.load(wd)
    ev = scenes(str(tmp_path / "e"), 1.2)
    r = subprocess.run([sys.executable, RSTOOL, "--workdir", wd, "widescreen", "aspect-auto", "--platform", "dos",
                        "--w", "320", "--h", "200", "--year", "1993", "--evidence", ev, "--record"],
                       capture_output=True, text=True, check=True)
    assert json.loads(r.stdout)["decided_by"] == "auto"
    data = project.load(wd)
    pa = data["graphics"]["pixel_aspect"]
    assert pa["stretch"] == 1.2 and pa["decided_by"] == "auto" and pa["evidence"]["shapes"]["verdict"] == "agree"
    assert any("automatica" in d["decision"] and d["date"] for d in data["decisions"])
    assert not any("proporzione" in q for q in project.pixel_aspect_question(data))
    assert "Proporzione dei pixel: 1.2 (decisa da sola)" in project.summary(data)
    assert plan._stretch({}, data) == 1.2

    res = platforms.aspect_auto("dos", 640, 400, 1995, sheet_out=str(tmp_path / "s.png"))
    platforms.record_aspect(data, res)
    q = project.pixel_aspect_question(data)
    assert q and "proposta 1.2" in q[0] and "dubbi" in q[0]
    assert plan._stretch({}, data) == 1.2  # the proposal counts in the estimate until answered
    data["graphics"]["pixel_aspect"].update(stretch=1.0, decided_by="user")
    assert project.pixel_aspect_question(data) == []
