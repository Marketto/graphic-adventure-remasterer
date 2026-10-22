"""Plan: estimates from the analysis counts, packages under the token budget, table, status.
All data are invented."""
import datetime as dt
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
RSTOOL = os.path.join(os.path.dirname(HERE), "rstool.py")

from remaster_tools import plan, project  # noqa: E402

COUNTS = {"backgrounds": 120, "bg_pixels": 120 * 64000, "sprite_frames": 1500,
          "text_lines": 3200, "text_chars": 140000, "voice_lines": 2600, "voice_chars": 95000,
          "music_tracks": 24, "sfx": 180, "manual_pages": 24, "translate_languages": ["it"],
          "scenes_by_class": {"scroll-wide": 10, "scroll-narrow": 6, "closed-static": 70, "open-static": 34}}


def _ids(items):
    return {i["id"] for i in items}


def test_estimate_counts_costs_and_missing_fields():
    est = plan.estimate(COUNTS)
    by = {i["id"]: i for i in est["items"]}
    # APISR ~100 µs per input pixel
    assert by["bg"]["cpu_s"] == round(120 * 64000 * 100 / 1e6)
    fal = by["ws-fal"]["quote"]
    assert fal["scenes"] == 40 and fal["max_images"] == 80 and fal["max_usd"] == 4.0
    dub = by["dub"]["quote"]
    assert dub["credits"] == round(95000 * 0.43 * 1.15)
    assert by["dub"]["paid"] == "voice" and by["ws-fal"]["paid"] == "fal"
    assert "translate-it" in by and "translate-it" in by["dub"]["depends"]
    # empty analysis: only the fixed packages, no paid ones, no crash
    small = plan.estimate({})
    assert not any(i["paid"] for i in small["items"]) and "qa" in _ids(small["items"])
    # dub already existing in the user's language: no ElevenLabs
    assert "dub" not in _ids(plan.estimate({**COUNTS, "dub_exists": True})["items"])


def test_coefficients_override(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"fal_price_usd": 0.1}))
    c = plan.load_coeffs(str(f))
    assert plan.estimate(COUNTS, c)["items"][-1]  # still works
    assert {i["id"]: i for i in plan.estimate(COUNTS, c)["items"]}["ws-fal"]["quote"]["max_usd"] == 8.0
    f.write_text(json.dumps({"inventato": 1}))
    with pytest.raises(ValueError):
        plan.load_coeffs(str(f))


def test_packages_fit_the_budget_and_have_groups():
    est = plan.estimate(COUNTS)
    pk = plan.packages(est, paid={"voice"}, budget=200000)
    assert not pk["over_budget"]
    assert all(p["tokens"] <= 200000 for p in pk["packages"])
    ids = _ids(pk["packages"])
    assert "ws-fal" not in ids and any(i.startswith("dub-") for i in ids)
    dubs = [p for p in pk["packages"] if p["item"] == "dub"]
    assert sum(p["units"] for p in dubs) == 2600 and sum(p["credits"] for p in dubs) == pytest.approx(
        round(95000 * 0.43 * 1.15), abs=len(dubs))
    g = {p["id"]: p["group"] for p in pk["packages"]}
    assert g["engine-port"] == 1 and g["bg-1"] == 1 and g["engine-layer"] == 2
    assert all(g[d] < g[p["id"]] for p in pk["packages"] for d in p["depends"])
    assert g["release"] == max(g.values())
    # a smaller budget means more, smaller packages
    assert len(plan.packages(est, budget=100000)["packages"]) > len(plan.packages(est)["packages"])


def test_table_separates_free_and_paid():
    pk = plan.packages(plan.estimate(COUNTS), paid={"fal", "voice"})
    t = plan.table(pk, parallel=3)
    assert "**Gratuito (incluso di default)**" in t and "**A pagamento" in t
    assert "🖼️" in t and "💸" in t and "crediti" in t and "**Totale**" in t
    assert "4,00 $" in t
    free_only = plan.table(plan.packages(plan.estimate(COUNTS)))
    assert "A pagamento" not in free_only
    assert plan.wall_minutes(pk, 1) >= plan.wall_minutes(pk, 4)


def test_registry_and_status(tmp_path):
    data = project.init("Avventura di prova", str(tmp_path))
    pk = plan.packages(plan.estimate({"backgrounds": 10, "text_lines": 50}))
    project.register_packages(data, pk["packages"])
    t0 = dt.datetime(2026, 1, 1, 10, 0, 0)
    project.update_package(data, "engine-port", "running", now=t0.isoformat())
    project.update_package(data, "bg", "running", tokens_used=260000, now=t0.isoformat())
    project.update_package(data, "text", "failed", now=t0.isoformat())
    st = plan.status(data, stale_min=30, now=t0 + dt.timedelta(minutes=45))
    assert "engine-port" in st["stale"] and {"id": "engine-port", "why": "fermo", "attempts": 1} in st["to_restart"]
    assert "bg" in st["over_budget"] and any(x["id"] == "bg" for x in st["to_stop"])
    assert any(x["id"] == "text" for x in st["to_restart"])
    assert "fonts-ui" in st["ready"] and "engine-layer" in st["pending"]
    # a restart counts a new attempt; after max attempts the package is stopped
    for _ in range(3):
        project.update_package(data, "text", "running", now=t0.isoformat())
        project.update_package(data, "text", "failed", now=t0.isoformat())
    st = plan.status(data, max_attempts=3, now=t0)
    assert any(x["id"] == "text" for x in st["to_stop"])
    # registering again keeps the state
    project.register_packages(data, pk["packages"])
    assert next(p for p in data["work_packages"] if p["id"] == "text")["attempts"] == 3
    with pytest.raises(ValueError):
        project.update_package(data, "text", "boh")


def test_language_default_and_phase0_questions(tmp_path):
    data = project.init("Avventura di prova", str(tmp_path))
    assert project.missing_answers(data) == ["file di gioco", "lingua dell'utente"]
    project.set_key(data, "game.languages_original", ["en", "de"])
    project.set_key(data, "languages.user", "it")
    project.apply_defaults(data)
    assert data["languages"]["translate"] == ["it"] and data["languages"]["requested"] == ["it"]
    other = project.init("Altra", str(tmp_path / "b"))
    project.set_key(other, "game.languages_original", ["it"])
    project.set_key(other, "languages.user", "it")
    assert project.apply_defaults(other)["languages"]["translate"] == []
    # dub already existing in the user's language: no ElevenLabs question
    for d, k in ((data, False), (other, True)):
        project.set_key(d, "paths.game_files", "/giochi/x")
        project.set_key(d, "analysis.done", True)
        project.set_key(d, "analysis.counts", "c.json")
        project.set_key(d, "graphics.widescreen.fal_ai", False)
        project.set_key(d, "voice.existing", {"it": k})
    assert "doppiaggio ElevenLabs (con preventivo)" in project.missing_answers(data)
    assert project.missing_answers(other) == ["approvazione del piano"]


def test_cli_plan(tmp_path):
    def run(*args):
        r = subprocess.run([sys.executable, RSTOOL, "--workdir", str(tmp_path), *args],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout
    c = tmp_path / "conti.json"
    c.write_text(json.dumps(COUNTS))
    run("project", "init", "Gioco di prova")
    run("plan", "estimate", str(c), "--record")
    assert project.load(str(tmp_path))["analysis"]["done"]
    assert "A pagamento" in run("plan", "table", str(c), "--paid", "all")
    assert "A pagamento" not in run("plan", "table", str(c))  # auto: nothing paid chosen yet
    run("plan", "packages", str(c), "--register")
    run("plan", "update", "engine-port", "--status", "running", "--tokens-used", "1000")
    st = json.loads(run("plan", "status", "--stale-min", "30"))
    assert st["running"] == ["engine-port"]
