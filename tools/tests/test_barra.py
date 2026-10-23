"""Barre fisse in 16:9: rilevamento, verifica sulle catture, scelta nel progetto, pacchetti del piano.
Dati inventati: stanze a tinta unita con una barra di pulsanti disegnata sotto."""
import json
import os
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from remaster_tools import plan, project, widescreen  # noqa: E402


def _room(path, color, seed, w=320, h=200, bar=56):
    rng = np.random.default_rng(seed)
    a = np.zeros((h, w, 3), np.uint8)
    a[: h - bar] = color
    a[: h - bar] += rng.integers(0, 40, (h - bar, w, 3), dtype=np.uint8)   # la scena cambia
    a[h - bar:] = (90, 60, 30)                                              # barra uguale ovunque
    for i in range(4):
        a[h - bar + 8: h - bar + 24, 10 + i * 70: 70 + i * 70] = (200, 180, 120)  # pulsanti
    Image.fromarray(a).save(path)
    return str(path)


def test_fixed_rows_finds_the_bar(tmp_path):
    caps = [_room(tmp_path / f"s{i}.png", c, i) for i, c in enumerate([(20, 80, 160), (120, 40, 40), (30, 120, 50)])]
    r = widescreen.fixed_rows(caps)
    assert r["bottom"] == 56 and r["top"] == 0 and r["playfield_h"] == 144 and r["bar"]
    with pytest.raises(ValueError):
        widescreen.fixed_rows(caps[:2])


def _wide(path, filled):
    # 16:9 a 360x200: centro 4:3 di 320 px, 20 px per lato; scena riempita, barra no (o sì)
    a = np.zeros((200, 360, 3), np.uint8)
    a[:, 20:340] = np.asarray(Image.open(_room(path, (20, 80, 160), 1)))
    a[:144, :20] = a[:144, 340:] = (40, 100, 170)
    if filled:
        a[144:, :20] = a[144:, 340:] = (90, 60, 30)
    Image.fromarray(a).save(path)
    return str(path)


def test_bar_check_flags_black_bands_beside_the_bar(tmp_path):
    r = widescreen.bar_check([_wide(tmp_path / "a.png", False)], 320, 200, 144)
    assert r["bar_unfilled"] and r["captures"][0]["scene_black"] == 0 and set(r["options"]) == {"A", "B", "C", "none"}
    ok = widescreen.bar_check([_wide(tmp_path / "b.png", True)], 320, 200, 144)
    assert not ok["bar_unfilled"] and ok["options"] is None


def test_classify_reports_the_bar_with_options(tmp_path):
    src = tmp_path / "bg"
    src.mkdir()
    for i in range(3):
        Image.new("RGB", (320, 144), (10 + i, 20, 30)).save(src / f"r{i}.png")
    pl = widescreen.classify(str(src), 320, 200)
    assert pl["ui_bar"]["bar_h"] == 56 and pl["ui_bar"]["option"] is None and "B" in pl["ui_bar"]["options"]


def test_project_accepts_only_known_options():
    d = {}
    project.set_key(d, "graphics.widescreen.ui_bar", {"option": "B", "notes": "verbi a tutta larghezza"})
    project.set_key(d, "graphics.widescreen.ui_bar.option", "none")
    project.set_key(d, "graphics.widescreen.ui_bar.icons", "paid")
    for k, v in (("graphics.widescreen.ui_bar.option", "D"), ("graphics.widescreen.ui_bar", {"option": "x"}),
                 ("graphics.widescreen.ui_bar.icons", "free"), ("graphics.widescreen.ui_bar", "B")):
        with pytest.raises(ValueError):
            project.set_key(d, k, v)


def test_bar_question_with_the_other_16_9_choices():
    d = {"graphics": {"enabled": True, "widescreen": {"enabled": True, "fal_ai": False}},
         "analysis": {"done": True, "counts": {"screen": [320, 200], "playfield_h": 144}}}
    assert project.ui_bar_question(d)
    d["graphics"]["widescreen"]["ui_bar"] = {"option": "A", "notes": ""}
    assert not project.ui_bar_question(d)
    d["analysis"]["counts"]["playfield_h"] = 200
    d["graphics"]["widescreen"]["ui_bar"] = {}
    assert not project.ui_bar_question(d)
    d["analysis"]["counts"]["ui_bar_unfilled"] = True
    assert project.ui_bar_question(d)


def _ids(option, icons=None, **extra):
    ub = {"option": option}
    if icons:
        ub["icons"] = icons
    proj = {"graphics": {"widescreen": {"enabled": True, "ui_bar": ub}}, "engine": {"layer_hooked": True}}
    counts = dict({"screen": [320, 200], "playfield_h": 144}, **extra)
    return {i["id"]: i for i in plan.estimate(counts, project=proj)["items"]}


def test_plan_packages_follow_the_option():
    c = plan.COEFFS
    a = _ids("A")
    assert "pannelli laterali" in a["ui-bar"]["label"] and a["ui-bar"]["tokens"] == c["tok_ui_bar"]
    assert "da scegliere" in _ids(None)["ui-bar"]["label"]
    assert not {"ui-bar", "ui-bar-B", "ui-bar-icons"} & set(_ids("none"))
    b = _ids("B")
    assert "ui-bar" not in b and b["ui-bar-B"]["tokens"] == c["tok_ui_bar_wide"] and "ui-bar-icons" not in b
    cc = _ids("C", verbs=12)
    assert cc["ui-bar-icons"]["depends"] == ["ui-bar-B"] and cc["ui-bar-icons"]["units"] == 12
    assert not cc["ui-bar-icons"]["paid"] and cc["ui-bar-icons"]["tokens"] == c["tok_ui_bar_icons"]
    paid = _ids("C", icons="paid")["ui-bar-icons"]
    worst = c["ui_bar_verbs"] * c["icon_attempts"]
    assert paid["paid"] == "fal" and paid["quote"]["max_images"] == worst
    assert paid["usd"] == round(worst * c["icon_price_usd"], 2)
    # le icone a pagamento entrano nei pacchetti solo se la spesa è scelta
    est = plan.estimate({"screen": [320, 200], "playfield_h": 144},
                        project={"graphics": {"widescreen": {"enabled": True, "ui_bar": {"option": "C", "icons": "paid"}}}})
    assert "ui-bar-icons" not in {p["item"] for p in plan.packages(est)["packages"]}
    assert "ui-bar-icons" in {p["item"] for p in plan.packages(est, paid={"fal"})["packages"]}
    json.dumps(est)
