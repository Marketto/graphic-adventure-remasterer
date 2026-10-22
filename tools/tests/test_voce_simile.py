"""Similar-voice casting: speech measures on synthetic signals, shortlist ordering, source work
in remaster.json. All signals and names are invented."""
import json
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
RSTOOL = os.path.join(os.path.dirname(HERE), "rstool.py")

from remaster_tools import project, voiceref  # noqa: E402

SR = voiceref.SR


def speech(f0, syl=4.0, dur=4.0, noise=0.0, tilt=1.0, vib=0.0, gap=0.25, seed=0):
    """Harmonic tone with syllable-like pulses, pauses every second, optional noise/vibrato."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * SR)) / SR
    f = f0 * (1 + vib * np.sin(2 * np.pi * 0.7 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = sum((1 / k ** tilt) * np.sin(k * ph) for k in range(1, int(7500 / f0 / (1 + vib)) + 1))
    env = np.sin(np.pi * syl * t) ** 2
    gate = ((t % 1.0) < 1.0 - gap).astype(float)
    x = x * env * gate + noise * rng.standard_normal(len(t)) * env * gate
    return (0.3 * x / np.abs(x).max()).astype(np.float32)


def write_wav(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return str(path)


def test_pitch_of_a_harmonic_tone():
    m = voiceref.measure_signal(speech(120))
    assert abs(m["f0_median_hz"] - 120) < 2
    assert m["f0_var_st"] < 0.5
    low = voiceref.measure_signal(speech(85))
    high = voiceref.measure_signal(speech(240))
    assert abs(low["f0_median_hz"] - 85) < 2 and abs(high["f0_median_hz"] - 240) < 3


def test_measures_make_sense():
    clean = voiceref.measure_signal(speech(120))
    noisy = voiceref.measure_signal(speech(120, noise=0.6))
    bright = voiceref.measure_signal(speech(120, tilt=0.3))
    moving = voiceref.measure_signal(speech(150, vib=0.15))
    fast = voiceref.measure_signal(speech(120, syl=7))
    pausy = voiceref.measure_signal(speech(120, gap=0.5))
    assert noisy["hnr_db"] < clean["hnr_db"] - 5          # roughness
    assert bright["centroid_hz"] > clean["centroid_hz"] * 1.5
    assert bright["slope_db_khz"] > clean["slope_db_khz"]
    assert moving["f0_var_st"] > 3                         # pitch spread
    assert fast["rate_syl_s"] > clean["rate_syl_s"] * 1.3
    assert pausy["pause_ratio"] > clean["pause_ratio"] + 0.1


def test_reference_combines_and_deletes(tmp_path):
    a = write_wav(tmp_path / "a.wav", speech(110))
    b = write_wav(tmp_path / "b.wav", speech(130, seed=1))
    res = voiceref.reference([a, b], str(tmp_path / "ref.json"), delete_after=True)
    assert res["fragments"] == 2 and res["deleted"] == 2
    assert 112 < res["measures"]["f0_median_hz"] < 128
    assert not os.path.exists(a) and not os.path.exists(b)
    saved = json.load(open(tmp_path / "ref.json"))
    assert "a.wav" not in json.dumps(saved)                 # numbers only


def test_match_picks_the_closest_voice(tmp_path):
    ref = voiceref.reference([write_wav(tmp_path / "r.wav", speech(118, noise=0.15, syl=5))],
                             str(tmp_path / "ref.json"))
    cand = tmp_path / "anteprime"
    cand.mkdir()
    write_wav(cand / "voce_giusta.wav", speech(122, noise=0.15, syl=4.5, seed=3))
    write_wav(cand / "troppo_acuta.wav", speech(230, noise=0.15, syl=5, seed=4))
    write_wav(cand / "ruvida.wav", speech(120, noise=0.5, syl=5, seed=5))
    write_wav(cand / "brillante.wav", speech(118, noise=0.15, syl=5, tilt=0.2, seed=6))
    res = voiceref.match(str(tmp_path / "ref.json"), str(cand), top=3, out_path=str(tmp_path / "s.json"))
    assert res["measured"] == 4 and len(res["shortlist"]) == 3
    best = res["shortlist"][0]
    assert best["voice_id"] == "voce_giusta"
    assert 0.7 <= best["settings"]["speed"] <= 1.2
    assert ref["measures"]["f0_median_hz"] > 100
    names = [r["voice_id"] for r in res["shortlist"]]
    assert "troppo_acuta" not in names[:1]


def test_match_from_voices_json_and_settings(tmp_path):
    voiceref.reference([write_wav(tmp_path / "r.wav", speech(150, vib=0.15, syl=4))], str(tmp_path / "ref.json"))
    write_wav(tmp_path / "piatta.wav", speech(150, syl=6, seed=2))
    write_wav(tmp_path / "grave.wav", speech(90, syl=4, seed=3))
    voices = [{"voice_id": "v1", "name": "Piatta", "file": "piatta.wav"},
              {"voice_id": "v2", "name": "Grave", "file": "grave.wav"},
              {"voice_id": "v3", "name": "Senza anteprima"}]
    (tmp_path / "voices.json").write_text(json.dumps({"voices": voices}))
    res = voiceref.match(str(tmp_path / "ref.json"), str(tmp_path / "voices.json"), out_path=str(tmp_path / "s.json"))
    by = {r["voice_id"]: r for r in res["shortlist"]}
    assert set(by) == {"v1", "v2"} and res["shortlist"][0]["voice_id"] == "v1"
    s = by["v1"]["settings"]
    # the reference moves its pitch much more and speaks slower: lower stability, slower speed
    assert s["stability"] < 0.5 and s["style"] > 0.6 and s["speed"] < 1.0
    assert any("più grave" in n for n in by["v2"]["settings"]["notes"])


def test_cli_reference_and_match(tmp_path):
    write_wav(tmp_path / "r.wav", speech(120))
    d = tmp_path / "c"
    d.mkdir()
    write_wav(d / "x.wav", speech(125))
    write_wav(d / "y.wav", speech(200))
    run = lambda *a: json.loads(subprocess.run([sys.executable, RSTOOL, *a], capture_output=True, text=True,
                                               check=True).stdout)
    r = run("voice", "reference", str(tmp_path / "r.wav"), "--out", str(tmp_path / "ref.json"), "--start", "0.5")
    assert r["fragments"] == 1
    m = run("voice", "match", str(tmp_path / "ref.json"), "--candidates", str(d), "--top", "1",
            "--out", str(tmp_path / "s.json"))
    assert [x["voice_id"] for x in m["shortlist"]] == ["x"]


def test_source_work_questions():
    data = json.loads(json.dumps(project.DEFAULT))
    data["game"]["title"] = "Gioco inventato"
    data["paths"]["game_files"] = "/x"
    data["languages"]["user"] = "it"
    data["analysis"] = {"done": True, "counts": "analysis/conti.json"}
    data["plan"]["approved"] = True
    data["graphics"]["widescreen"]["fal_ai"] = False
    data["voice"].update({"enabled": False, "languages": ["it"]})
    sw = data["source_work"]
    sw.update({"checked": True, "type": "film", "title": "Film inventato", "year": 1990,
               "sources": ["https://example.org/scheda"]})
    sw["characters"].append(project.new_character(
        "Capitano Zeta", "Attore Inventato",
        {"en": {"name": "Attore Inventato"}, "it": {"name": "Doppiatore Inventato", "year": 1990}},
        ["https://example.org/cast"]))
    # no dub chosen: the likeness question is not asked
    assert not any("voce simile" in m for m in project.missing_answers(data))
    data["voice"].update({"enabled": True, "license_confirmed": True})
    data["budget"]["cap_usd"] = 10
    miss = project.missing_answers(data)
    assert "voce simile all'opera d'origine per: Capitano Zeta" in miss
    sw["characters"][0]["imitate_voice"] = False
    assert project.missing_answers(data) == []
    # a dubbed language without the voice of the time is flagged, as are missing sources
    data["voice"]["languages"] = ["it", "fr"]
    sw["characters"][0]["sources"] = []
    probs = project.source_work_problems(data)
    assert any("«fr»" in p for p in probs) and any("senza fonti" in p for p in probs)
    assert "Opera d'origine: Film inventato" in project.summary(data)
