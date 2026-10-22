"""Stretches of long reference files, reusable measures and the checks of the shortlist. All
signals, names and texts are invented; transcription and voice prints use fake backends."""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
RSTOOL = os.path.join(os.path.dirname(HERE), "rstool.py")

from remaster_tools import voiceref, voiceseg  # noqa: E402
from test_voce_simile import SR, speech, write_wav  # noqa: E402

# who speaks when in the invented "trailer": (start, end, f0)
TURNS = [(0.0, 2.0, 110), (2.5, 4.5, 230), (5.0, 7.0, 110), (7.5, 9.5, 230)]


def trailer(path):
    x = np.zeros(int(10 * SR), dtype=np.float32)
    for i, (a, b, f0) in enumerate(TURNS):
        x[int(a * SR):int(a * SR) + int((b - a) * SR)] = speech(f0, dur=b - a, gap=0.1, seed=i)
    return write_wav(path, x)


def fake_transcriber(x, lang):
    assert lang == "it" and x.dtype == np.float32           # an array decoded by ffmpeg, not a path
    segs = [{"start": a, "end": b, "text": f"battuta inventata {i}", "logprob": -0.3}
            for i, (a, b, _) in enumerate(TURNS)]
    segs.append({"start": 9.6, "end": 9.9, "text": "eh", "logprob": -1.0})
    return segs


def read_tsv(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    head = lines[0].split("\t")
    return head, [dict(zip(head, ln.split("\t"))) for ln in lines[1:]]


def test_segments_groups_two_speakers(tmp_path):
    src = trailer(tmp_path / "trailer.wav")
    res = voiceseg.segments([src], str(tmp_path / "seg.tsv"), transcriber=fake_transcriber,
                            printer=voiceseg.SimplePrint())
    head, rows = read_tsv(tmp_path / "seg.tsv")
    assert head[:5] == ["id", "file", "inizio", "fine", "gruppo"] and "testo" in head
    assert rows[0]["file"] == "trailer.wav"                  # relative to the TSV
    g = [r["gruppo"] for r in rows]
    assert g[0] == g[2] != g[1] == g[3] and g[4] == "-"       # the short one is not attributed
    assert res["unattributed"] == 1 and len(res["groups"]) == 2
    assert all(float(r["sicurezza"]) > 0.3 for r in rows[:4])


def test_segments_fixed_number_of_speakers_and_cosine(tmp_path):
    src = trailer(tmp_path / "t.wav")

    class FakePrint:
        metric, threshold, name = "cosine", 0.25, "finta"

        def __call__(self, x):          # a print that only depends on the pitch of the stretch
            f0 = voiceref.measure_signal(x)["f0_median_hz"]
            return np.array([1.0, 0.2]) if f0 < 160 else np.array([0.9, 0.6])
    res = voiceseg.segments([src], str(tmp_path / "s.tsv"), speakers=2, transcriber=fake_transcriber,
                            printer=FakePrint())
    _, rows = read_tsv(tmp_path / "s.tsv")
    assert res["grouping"] == "2 gruppi" and {r["gruppo"] for r in rows[:4]} == {"G1", "G2"}
    res1 = voiceseg.segments([src], str(tmp_path / "s1.tsv"), speakers=1, transcriber=fake_transcriber,
                             printer=FakePrint())
    assert len(res1["groups"]) == 1


def test_split_on_long_word_gaps():
    seg = {"start": 0, "end": 3, "logprob": -0.2, "words": [
        {"start": 0.0, "end": 0.4, "word": " uno"}, {"start": 0.5, "end": 0.9, "word": " due"},
        {"start": 2.0, "end": 2.5, "word": " tre"}]}
    parts = voiceseg._split(seg)
    assert [(p["start"], p["end"], p["text"]) for p in parts] == [(0.0, 0.9, "uno due"), (2.0, 2.5, "tre")]


def test_clustering_threshold():
    E = np.array([[0.0], [0.1], [5.0], [5.2], [10.0]])
    lab, _ = voiceseg.cluster(E, "euclidean", threshold=1.0)
    assert lab[0] == lab[1] != lab[2] == lab[3] != lab[4]


def test_missing_optional_dependencies(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    monkeypatch.setitem(sys.modules, "resemblyzer", None)
    with pytest.raises(RuntimeError, match="pip install faster-whisper"):
        voiceseg.whisper_transcriber()
    with pytest.raises(RuntimeError, match="setuptools<81"):
        voiceseg.voice_prints("resemblyzer")
    assert voiceseg.voice_prints("auto").name == "simple"     # free fallback


def test_reference_from_segments_keeps_sources(tmp_path):
    src = trailer(tmp_path / "trailer.wav")
    voiceseg.segments([src], str(tmp_path / "seg.tsv"), transcriber=fake_transcriber, printer=voiceseg.SimplePrint())
    _, rows = read_tsv(tmp_path / "seg.tsv")
    low = rows[0]["gruppo"]                                   # the 110 Hz voice
    res = voiceref.reference([], str(tmp_path / "ref.json"), segments=str(tmp_path / "seg.tsv"), group=low,
                             gender="male", age="adulto", delete_after=True)
    assert res["fragments"] == 2 and abs(res["measures"]["f0_median_hz"] - 110) < 3
    assert [s["start"] for s in res["sources"]] == [0.0, 5.0] and res["sources"][0]["file"] == "trailer.wav"
    assert res["character"] == {"gender": "male", "age": "middle_aged"} and "warnings" not in res
    assert not os.path.exists(src) and res["deleted"] == 1
    saved = json.load(open(tmp_path / "ref.json"))
    assert "battuta" not in json.dumps(saved)                 # no text of the source in the reference
    with pytest.raises(ValueError):
        voiceref.reference([], None, segments=str(tmp_path / "seg.tsv"))
    with pytest.raises(ValueError):
        voiceref.reference([], None, segments=str(tmp_path / "seg.tsv"), group=low, start=1.0)


def test_select_ranges(tmp_path):
    src = trailer(tmp_path / "t.wav")
    voiceseg.segments([src], str(tmp_path / "seg.tsv"), transcriber=fake_transcriber, printer=voiceseg.SimplePrint())
    rows = voiceref.read_segments(str(tmp_path / "seg.tsv"), select="2-4")
    assert [r["id"] for r in rows] == ["2", "3", "4"]
    res = voiceref.reference([], None, segments=str(tmp_path / "seg.tsv"), select="2,4,5")
    assert res["fragments"] == 2 and len(res["skipped"]) == 1 # the 0.3 s stretch is too short
    assert abs(res["measures"]["f0_median_hz"] - 230) < 5


def test_mfcc_tells_formants_apart():
    def vowel(formant):
        t = np.arange(int(3 * SR)) / SR
        ph = 2 * np.pi * 120 * t
        x = sum(np.exp(-((k * 120 - formant) / 300.0) ** 2) * np.sin(k * ph) / k ** 0.5 for k in range(1, 60))
        x = x * np.sin(np.pi * 4 * t) ** 2 * ((t % 1.0) < 0.75)
        return (0.3 * x / np.abs(x).max()).astype(np.float32)
    a, b = voiceref.measure_signal(vowel(600)), voiceref.measure_signal(vowel(1800))
    assert len(a["mfcc"]) == 12
    _, parts = voiceref.distance(a, b)
    assert parts["mfcc"] > 1.0
    _, same = voiceref.distance(a, voiceref.measure_signal(vowel(620)))
    assert same["mfcc"] < parts["mfcc"] / 3


def _bed(x):
    t = np.arange(len(x)) / SR
    return (x + 0.03 * (np.sin(2 * np.pi * 220 * t) + np.sin(2 * np.pi * 330 * t))).astype(np.float32)


def test_measure_reuse_and_match_checks(tmp_path):
    voiceref.reference([write_wav(tmp_path / "r.wav", speech(115, noise=0.1))], str(tmp_path / "ref.json"),
                       gender="male", age="old")
    d = tmp_path / "anteprime"
    d.mkdir()
    write_wav(d / "a.wav", speech(118, noise=0.1, seed=1))
    write_wav(d / "musica.wav", _bed(speech(118, noise=0.1, seed=2)))
    write_wav(d / "ottava.wav", speech(240, noise=0.1, seed=3))
    voices = [{"voice_id": "a", "name": "A", "file": "anteprime/a.wav", "labels": {"gender": "male", "age": "old"}},
              {"voice_id": "m", "name": "M", "file": "anteprime/musica.wav", "gender": "male", "age": "old"},
              {"voice_id": "o", "name": "O", "file": "anteprime/ottava.wav", "gender": "male", "age": "old"},
              {"voice_id": "y", "name": "Y", "file": "anteprime/a.wav", "gender": "female", "age": "young"}]
    (tmp_path / "voices.json").write_text(json.dumps(voices))
    m1 = voiceref.measure(str(tmp_path / "voices.json"), str(tmp_path / "misure.json"))
    assert m1["measured"] == 4 and m1["reused"] == 0
    m2 = voiceref.measure(str(tmp_path / "voices.json"), str(tmp_path / "misure.json"))
    assert m2["measured"] == 0 and m2["reused"] == 4          # measures kept across sessions
    res = voiceref.match(str(tmp_path / "ref.json"), measured=str(tmp_path / "misure.json"), top=4,
                         out_path=str(tmp_path / "s.json"))
    by = {r["voice_id"]: r for r in res["shortlist"]}
    assert by["m"]["music_bed"] and any("musica" in w for w in by["m"]["warnings"])
    assert not by["a"]["music_bed"] and by["a"]["warnings"] == []
    assert any("errore d'ottava" in w for w in by["o"]["warnings"])
    assert any("diversi dal personaggio" in w for w in by["y"]["warnings"])
    assert any("solo 3 candidate dell'età giusta" in w for w in res["warnings"])
    assert any("anteprime con musica" in w for w in res["warnings"])
    assert "mfcc" in by["a"]["parts"]
    strict = voiceref.match(str(tmp_path / "ref.json"), measured=str(tmp_path / "misure.json"), strict=True)
    assert [e["voice_id"] for e in strict["excluded"]] == ["y"]


def test_bed_lowers_weights_of_pauses_and_roughness():
    ref = voiceref.measure_signal(speech(120, noise=0.1))
    bed = voiceref.measure_signal(_bed(speech(120, noise=0.1, seed=4)))
    assert bed["pause_ratio"] < voiceref.NO_PAUSE and bed["dyn_range_db"] < ref["dyn_range_db"]
    full, _ = voiceref.distance(ref, bed)
    low, _ = voiceref.distance(ref, bed, {k: voiceref.FEATURES[k][1] * voiceref.BED_WEIGHT
                                          for k in voiceref.BED_FEATURES})
    assert low < full


def test_old_measures_without_mfcc_still_match():
    a = voiceref.measure_signal(speech(120))
    b = dict(a)
    b.pop("mfcc")
    d, parts = voiceref.distance(b, a)
    assert "mfcc" not in parts and d < 0.05


def test_cli_measure_match_and_segments_reference(tmp_path):
    run = lambda *a: json.loads(subprocess.run([sys.executable, RSTOOL, *a], capture_output=True, text=True,
                                               check=True).stdout)
    write_wav(tmp_path / "r.wav", speech(120))
    d = tmp_path / "c"
    d.mkdir()
    write_wav(d / "x.wav", speech(125))
    write_wav(d / "y.wav", speech(200))
    run("voice", "reference", str(tmp_path / "r.wav"), "--out", str(tmp_path / "ref.json"), "--gender", "male")
    m = run("voice", "measure", str(d), "--out", str(tmp_path / "misure.json"))
    assert m["measured"] == 2
    s = run("voice", "match", str(tmp_path / "ref.json"), "--measured", str(tmp_path / "misure.json"),
            "--top", "1", "--out", str(tmp_path / "s.json"))
    assert [x["voice_id"] for x in s["shortlist"]] == ["x"]
    src = trailer(tmp_path / "t.wav")
    voiceseg.segments([src], str(tmp_path / "seg.tsv"), transcriber=fake_transcriber, printer=voiceseg.SimplePrint())
    r = run("voice", "reference", "--segments", str(tmp_path / "seg.tsv"), "--select", "1,3",
            "--out", str(tmp_path / "ref2.json"))
    assert r["fragments"] == 2 and len(r["sources"]) == 2
    bad = subprocess.run([sys.executable, RSTOOL, "voice", "reference", "--segments", str(tmp_path / "seg.tsv"),
                          "--out", str(tmp_path / "x.json")], capture_output=True, text=True)
    assert bad.returncode != 0 and "--group" in bad.stderr and "Traceback" not in bad.stderr
