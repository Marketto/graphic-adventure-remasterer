"""Dub planned per part of the game (chapters, acts, discs, paths), credits available and
voice.scope. All data are invented."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pytest  # noqa: E402

from remaster_tools import plan, project  # noqa: E402

PARTS = [{"id": "1", "label": "Il faro", "chars": 10000, "lines": 300},
         {"id": "2", "label": "La palude", "chars": 20000, "lines": 600},
         {"id": "3", "label": "La torre", "chars": 15000, "lines": 400},
         {"id": "4", "label": "Il ritorno", "chars": 5000, "lines": 150}]
COUNTS = {"text_lines": 2000, "text_chars": 60000, "voice_lines": 1450, "voice_chars": 50000,
          "voice": {"parts": PARTS}, "lipsync": True}
PER_CHAR = 0.43 * 1.15  # no translation: no expansion


def _proj(**voice):
    d = {"voice": {"enabled": True, **voice}, "languages": {"user": "it"}, "game": {"languages_original": ["it"]}}
    return d


def test_one_dub_item_per_part_with_cumulative_credits():
    est = plan.estimate(COUNTS, project=_proj())
    dubs = [i for i in est["items"] if i["paid"] == "voice"]
    assert [i["id"] for i in dubs] == ["dub-1", "dub-2", "dub-3", "dub-4"]
    assert dubs[1]["label"] == "Doppiaggio parte 2/4: La palude"
    assert dubs[0]["credits"] == round(10000 * PER_CHAR)
    assert dubs[2]["part"]["credits_cumulative"] == round(45000 * PER_CHAR)
    assert dubs[0]["part"]["in_credits"] is None  # credits not known
    by = {i["id"]: i for i in est["items"]}
    assert set(by["lipsync"]["depends"]) >= {"dub-1", "dub-4"}
    assert {"dub-1", "dub-2", "dub-3", "dub-4"} <= set(by["mix"]["depends"])
    assert est["voice_parts"]["credits_total"] == round(50000 * PER_CHAR)


def test_parts_in_credits_is_a_prefix_in_play_order():
    assert plan.parts_in_credits([10, 20, 5], 30) == 2
    assert plan.parts_in_credits([10, 20, 5], 9) == 0
    # a cheap later part does not jump ahead of an expensive earlier one
    assert plan.parts_in_credits([10, 50, 1], 40) == 1


def test_credits_available_marks_the_parts_in_the_table():
    avail = round(31000 * PER_CHAR)  # parts 1+2 fit (30000 chars), part 3 does not
    est = plan.estimate(COUNTS, project=_proj(credits_available=avail))
    assert est["voice_parts"]["fit"] == 2
    pk = plan.packages(est, paid={"voice"})
    t = plan.table(pk)
    assert "Doppiaggio parte 1/4" in t and "✅ nei crediti" in t
    assert t.count("⏸️ oltre i crediti") == 2
    assert "stanno 2 parti su 4" in t


def test_scope_parts_leaves_the_others_deferred():
    data = _proj(credits_available=100000)
    project.set_voice_scope(data, "parti", ["1", "2"])
    est = plan.estimate(COUNTS, project=data)
    pk = plan.packages(est, paid={"voice"})
    ids = {p["id"] for p in pk["packages"]}
    assert {"dub-1", "dub-2"} <= ids and not ids & {"dub-3", "dub-4"}
    assert [d["id"] for d in pk["deferred"]] == ["dub-3", "dub-4"]
    mix = next(p for p in pk["packages"] if p["id"] == "mix")
    assert "dub-3" not in mix["depends"] and "dub-1" in mix["depends"]
    t = plan.table(pk)
    assert "esclusa (voice.scope)" in t and "2 parti escluse" in t
    # registry: excluded parts are recorded as deferred, then return pending when chosen again
    project.register_packages(data, pk["packages"], deferred=pk["deferred"])
    st = {p["id"]: p["status"] for p in data["work_packages"]}
    assert st["dub-3"] == "deferred" and st["dub-1"] == "pending"
    assert "dub-3" in plan.status(data)["deferred"]
    project.set_voice_scope(data, "tutto")
    pk2 = plan.packages(plan.estimate(COUNTS, project=data), paid={"voice"})
    assert not pk2["deferred"]
    project.register_packages(data, pk2["packages"], deferred=pk2["deferred"])
    assert {p["id"]: p["status"] for p in data["work_packages"]}["dub-3"] == "pending"


def test_scope_validation():
    with pytest.raises(ValueError):
        project.set_voice_scope({}, "metà")
    with pytest.raises(ValueError):
        project.set_voice_scope({}, "parti", [])


def test_unknown_parts_fall_back_to_lots_and_say_so():
    counts = {k: v for k, v in COUNTS.items() if k != "voice"}
    est = plan.estimate(counts, project=_proj(credits_available=1000))
    dubs = [i for i in est["items"] if i["paid"] == "voice"]
    assert [i["id"] for i in dubs] == ["dub"] and "parti del gioco non note" in dubs[0]["label"]
    t = plan.table(plan.packages(est, paid={"voice"}, budget=100000))
    assert "lotti" in t and "parti del gioco non note" in t


def test_parts_without_chars_share_the_script_by_lines():
    counts = {"voice_lines": 1000, "voice_chars": 40000,
              "voice_parts": [{"id": "a", "lines": 250}, {"id": "b", "lines": 750}]}
    est = plan.estimate(counts, project=_proj())
    by = {i["id"]: i for i in est["items"]}
    assert by["dub-a"]["quote"]["chars"] == 10000 and by["dub-b"]["quote"]["chars"] == 30000
    assert by["dub-a"]["label"].endswith("parte a")
