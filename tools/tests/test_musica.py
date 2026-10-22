"""Tests of the "orchestra" strategy tools: MIDI diagnosis, program remapping, energy per band,
composite SoundFont from a recipe, and of the fixes to normalize / sfx --rates / backends.
All data are invented and generated here (synthetic MIDI, tiny SoundFonts, sine waves)."""
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import wave

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from remaster_tools import audio, audio_midi, audio_sf2  # noqa: E402

RSTOOL = os.path.join(os.path.dirname(__file__), "..", "rstool.py")
need_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg assente")


def vlq(v):
    return audio_midi._enc_vlq(v)


def midi_file(path, channels, division=96, extra=b""):
    """channels: {ch: (program, cc7, [(pitch, velocity)])}: one note per beat at 120 BPM."""
    body = bytearray(b"\x00\xff\x51\x03\x07\xa1\x20" + extra)
    for ch, (prog, cc7, notes) in channels.items():
        body += b"\x00" + bytes([0xC0 | ch, prog]) + b"\x00" + bytes([0xB0 | ch, 7, cc7])
    evs = []
    for ch, (_p, _c, notes) in channels.items():
        for i, (pitch, vel) in enumerate(notes):
            evs.append((i * division, bytes([0x90 | ch, pitch, vel])))
            evs.append((i * division + division // 2, bytes([0x80 | ch, pitch, 0])))
    t = 0
    for tick, ev in sorted(evs, key=lambda e: e[0]):
        body += vlq(tick - t) + ev
        t = tick
    body += b"\x00\xff\x2f\x00"
    path.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 0, 1, division) + b"MTrk"
                     + struct.pack(">I", len(body)) + bytes(body))
    return str(path)


# ------------------------------------------------------------------ MIDI diagnosis
def test_channels_programs_and_warnings(tmp_path):
    melody = [(76 + k % 5, 110) for k in range(16)]
    accomp = [(48 + k % 3, 40) for k in range(16)]
    m = midi_file(tmp_path / "brano.mid", {0: (3, 127, melody), 1: (5, 60, accomp),
                                           9: (0, 100, [(36, 90)] * 4)})
    table = list(range(128))
    table[3], table[5] = 59, 48              # invented engine table: 3 -> muted trumpet
    rep = audio_midi.channel_report(m, table)
    ch1, ch2 = rep["channels"]["1"], rep["channels"]["2"]
    assert ch1["notes"] == 16 and ch1["low"] == "E5" and ch1["programs"][0]["gm"] == 59
    assert any("sordina" in w for w in ch1["warnings"])
    assert ch2["programs"][0]["gm_name"] == "String Ensemble 1"
    # low velocity and CC7: far below the melody with the GM curve, less with a linear one
    assert ch2["level_db"]["gm"] < ch2["level_db"]["linear"]
    assert any("sparire" in w for w in ch2["warnings"])
    assert rep["channels"]["10"]["drums"] and "gm" not in rep["channels"]["10"]["programs"][0]
    # a fix moves the slot and is reported
    fixed = audio_midi.channel_report(m, table, {59: 56})["channels"]["1"]["programs"][0]
    assert fixed["gm"] == 56 and fixed["fixed_from"] == 59
    assert abs(rep["seconds"] - 8) < 0.6


def test_compare_versions_and_remap(tmp_path):
    notes = [(60 + k % 7, 100) for k in range(12)]
    a = midi_file(tmp_path / "a.mid", {0: (10, 100, notes)})
    b = midi_file(tmp_path / "b.mid", {0: (10, 100, [(p + 12, v) for p, v in notes])})
    c = midi_file(tmp_path / "c.mid", {0: (10, 100, notes)})
    r = audio_midi.compare_notes([a, b, c])
    assert r["versions"]["b.mid"]["1"]["octave_shift"] and r["versions"]["b.mid"]["1"]["median_shift"] == 12
    assert r["versions"]["c.mid"]["1"]["same_pitch"] == 1.0 and len(r["differences"]) == 1
    sysex = b"\x00\xf0\x05\x41\x10\x16\x12\xf7"
    src = midi_file(tmp_path / "s.mid", {0: (10, 100, notes), 9: (10, 100, [(38, 90)])}, extra=sysex)
    out = audio_midi.remap(src, str(tmp_path / "gm.mid"), {"10": 73}, fixes={73: 72}, reverb_send=127)
    assert out["programs"] == {"10": 72}
    mid = audio_midi.read_midi(str(tmp_path / "gm.mid"))
    evs = [ev for _t, ev in mid["tracks"][0]]
    assert bytes([0xC0, 72]) in evs and bytes([0xC9, 10]) in evs      # drums untouched
    assert bytes([0xB0, 91, 127]) in evs and not any(e[0] == 0xF0 for e in evs)
    assert audio.midi_stats(str(tmp_path / "gm.mid"))["notes"] == 13
    with pytest.raises(ValueError):
        audio_midi.remap(src, str(tmp_path / "x.mid"), [1, 2, 3])


def write_wav(path, freqs, seconds=3.0, rate=22050):
    t = np.arange(int(seconds * rate)) / rate
    x = sum(a * np.sin(2 * math.pi * f * t) for f, a in freqs)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32000).astype("<i2").tobytes())
    return str(path)


def test_bands_shrill_and_warm(tmp_path):
    shrill = audio_midi.bands(write_wav(tmp_path / "acuto.wav", [(3000, 0.5), (1200, 0.2)]))
    warm = audio_midi.bands(write_wav(tmp_path / "caldo.wav", [(130.8, 0.5), (523, 0.2)]))
    assert shrill["centroid_hz"] > 1500 and shrill["bands"]["2000-4000"] > 0.5
    assert warm["bands"]["0-250"] > 0.6 and warm["octaves_C1_B3"] > 0.6 and warm["dominant_note"] == "C3"
    d = audio_midi.diagnose(audio=[str(tmp_path / "caldo.wav")])
    assert d["bands"][0]["dominant_note"] == "C3"


# ------------------------------------------------------------------ SoundFont
def tiny_sf2(path, presets, ver=(2, 1), samples=64):
    """A tiny valid SoundFont: one sample, one instrument per preset {(bank, prog): name}."""
    smpl = struct.pack("<%dh" % samples, *[int(8000 * math.sin(k / 3)) for k in range(samples)]) + b"\0" * 92
    shdr = [b"tono".ljust(20, b"\0") + struct.pack("<IIIIIBbHH", 0, samples, 8, samples - 8, 22050, 60, 0, 0, 1)]
    insts, pres = [], []
    for k, ((bank, prog), name) in enumerate(sorted(presets.items())):
        insts.append({"hdr": name.encode().ljust(20, b"\0") + b"\0\0",
                      "zones": [[[(audio_sf2.GEN_SAMPLEID, 0)], []]]})
        pres.append({"hdr": name.encode().ljust(20, b"\0") + struct.pack("<HHHIII", prog, bank, 0, 0, 0, 0),
                     "zones": [[[(audio_sf2.GEN_INSTRUMENT, k)], []]]})
    info = b"ifil" + struct.pack("<IHH", 4, *ver) + b"INAM" + struct.pack("<I", 6) + b"prova\0"
    audio_sf2._write(str(path), info, pres, insts, shdr, smpl)
    return str(path)


def test_sf2_compose_recipe(tmp_path):
    tiny_sf2(tmp_path / "base.sf2", {(0, 56): "Tromba", (0, 59): "Sordina", (0, 73): "Flauto",
                                     (0, 79): "Ocarina", (128, 0): "Batteria"})
    tiny_sf2(tmp_path / "ottoni.sf2", {(0, 0): "Ottoni aperti"})
    recipe = {"base": "base.sf2",
              "imports": [{"slot": [0, 59], "from": "ottoni.sf2", "attenuation_cb": 20}],
              "copies": [{"slot": [0, 79], "from_slot": [0, 73]}],
              "velocity_attenuation_cb": -480,
              "credits": [{"source": "ottoni.sf2", "author": "Autore Inventato", "license": "CC BY 3.0"}]}
    (tmp_path / "orchestra.json").write_text(json.dumps(recipe))
    out = str(tmp_path / "out" / "orchestra.sf2")
    res = audio_sf2.compose(str(tmp_path / "orchestra.json"), out)
    assert res["presets"] == 5 and res["warnings"] == [] and res["attribution_required"] == ["ottoni.sf2"]
    names = {(p["bank"], p["program"]): p["name"] for p in audio_sf2.info(out)["presets"]}
    assert names[(0, 59)] == "Ottoni aperti" and names[(0, 79)] == "Flauto" and names[(128, 0)] == "Batteria"
    sf = audio_sf2.SoundFont(out)
    assert len(sf.shdr) == 2 and len(sf.insts) == 6
    p59 = sf.find(0, 59)
    inst_zone = [z for z in p59["zones"] if any(o == audio_sf2.GEN_INSTRUMENT for o, _ in z[0])][0]
    assert any(o == audio_sf2.GEN_INSTRUMENT and a == 5 for o, a in inst_zone[0])   # imported instrument
    assert any(struct.unpack("<HHhHH", m)[2] == -480 for m in inst_zone[1])
    assert (0x2, 20) in [(o - 46, a) for o, a in p59["zones"][0][0]]               # attenuation 48
    s2 = bytes(sf.shdr[1])
    assert struct.unpack("<I", s2[20:24])[0] == len(audio_sf2.SoundFont(str(tmp_path / "base.sf2")).smpl) // 2
    assert "Autore Inventato" in open(out + ".crediti.txt", encoding="utf-8").read()
    if shutil.which("fluidsynth"):   # the result loads in the real synthesizer
        mid = midi_file(tmp_path / "n.mid", {0: (59, 100, [(60, 100)] * 2)})
        r = subprocess.run(["fluidsynth", "-ni", "-F", str(tmp_path / "n.wav"), out, mid],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "error" not in r.stderr.lower(), r.stderr


def test_sf2_light_variant_and_errors(tmp_path):
    tiny_sf2(tmp_path / "leggera.sf3", {(0, 56): "Tromba", (0, 73): "Flauto"}, ver=(3, 1))
    tiny_sf2(tmp_path / "x.sf2", {(0, 0): "X"})
    ok = audio_sf2.compose({"base": "leggera.sf3", "copies": [{"slot": [0, 59], "from_slot": [0, 56]}],
                            "keep": [[0, 56]]}, str(tmp_path / "l.sf3"), root=str(tmp_path))
    assert ok["format"] == "sf3" and ok["presets"] == 2
    assert audio_sf2.info(str(tmp_path / "l.sf3"))["version"] == "3.01"
    with pytest.raises(ValueError, match="sf3"):
        audio_sf2.compose({"base": "leggera.sf3", "imports": [{"slot": [0, 59], "from": "x.sf2"}]},
                          str(tmp_path / "e.sf3"), root=str(tmp_path))
    warn = audio_sf2.compose({"base": "x.sf2", "imports": [{"slot": [0, 1], "from": "x.sf2"}]},
                             str(tmp_path / "w.sf2"), root=str(tmp_path))
    assert any("crediti" in w for w in warn["warnings"])
    with pytest.raises(ValueError):
        audio_sf2.compose({"base": "x.sf2", "copies": [{"slot": [0, 1], "from_slot": [0, 9]}]},
                          str(tmp_path / "k.sf2"), root=str(tmp_path))
    (tmp_path / "nonsf.sf2").write_bytes(b"RIFF\0\0\0\0WAVE")
    with pytest.raises(ValueError):
        audio_sf2.SoundFont(str(tmp_path / "nonsf.sf2"))


def test_cli_music_commands(tmp_path):
    tiny_sf2(tmp_path / "b.sf2", {(0, 0): "Piano"})
    (tmp_path / "r.json").write_text(json.dumps({"base": "b.sf2", "copies": [{"slot": [0, 1], "from_slot": [0, 0]}]}))
    run = lambda *a: subprocess.run([sys.executable, RSTOOL, "audio", *a], capture_output=True, text=True, cwd=tmp_path)
    r = run("sf2-compose", str(tmp_path / "r.json"), "--out", str(tmp_path / "o.sf2"))
    assert r.returncode == 0, r.stderr
    assert json.loads(run("sf2-info", str(tmp_path / "o.sf2")).stdout)["presets"][1]["program"] == 1
    m = midi_file(tmp_path / "m.mid", {0: (0, 100, [(60, 100)] * 3)})
    (tmp_path / "t.json").write_text(json.dumps({"0": 59}))
    d = json.loads(run("midi-diagnose", m, "--table", str(tmp_path / "t.json")).stdout)
    assert d["midi"][0]["channels"]["1"]["programs"][0]["gm"] == 59 and d["warnings"]
    bad = run("midi-diagnose", str(tmp_path / "t.json"))
    assert bad.returncode != 0 and "MIDI" in bad.stderr


# ------------------------------------------------------------------ fixes of the audio tools
def test_normalize_short_clips_one_group_gain(tmp_path):
    files = []
    for n in ("a", "b", "c"):
        p = tmp_path / f"{n}.wav"
        p.write_bytes(b"")
        files.append(str(p))
    long_ = {str(tmp_path / "c.wav"): -14.0}
    measure = lambda f: long_.get(f, -70.0)          # a, b: shorter than 400 ms
    seen = []

    def concat(paths):
        seen.append(sorted(os.path.basename(p) for p in paths))
        return -20.0
    info = audio.normalize_group("voice", files, measure=measure, measure_concat=concat)
    g = {e["name"]: e for e in info["files"]}
    assert seen == [["a.wav", "b.wav"]]
    assert g["a.wav"]["norm_gain"] == g["b.wav"]["norm_gain"] == -3.0 and g["a.wav"]["short"]
    assert g["c.wav"]["norm_gain"] == -9.0 and info["measured"]["short"] == 2
    # in the mix the short clips get the group offset like the others, not +7 dB up to the limiter
    rows = audio.mix_gains({"voice": info})["voice"]["files"]
    assert {r["name"]: r["final_lufs"] for r in rows}["a.wav"] == -18.0
    # sfx (group policy) made only of short clips: the concatenation is the anchor
    s = audio.normalize_group("sfx", files[:2], measure=measure, measure_concat=concat)
    assert {e["norm_gain"] for e in s["files"]} == {-3.0}


@need_ffmpeg
def test_loudness_concat_real_short_clips(tmp_path):
    clips = []
    for k, f in enumerate((440, 660)):
        p = tmp_path / f"c{k}.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=f={f}:d=0.25",
                        str(p)], check=True)
        clips.append(str(p))
    lv = audio.loudness_concat(clips)
    assert -22 < lv < -15, lv


@need_ffmpeg
def test_sfx_rates_plain_number(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "colpo.raw").write_bytes(bytes(128 + int(60 * math.sin(k / 4)) for k in range(4000)))
    (src / "porta.raw").write_bytes(bytes(128 + int(60 * math.sin(k / 6)) for k in range(4000)))
    (tmp_path / "rates.json").write_text(json.dumps({"COLPO": 22050, "porta": [11025, "8000"]}))
    r = audio.sfx_batch(str(src), str(tmp_path / "out"), str(tmp_path / "rates.json"), lossless=True)
    assert sorted(r["written"]) == ["colpo_22050.flac", "porta_11025.flac", "porta_8000.flac"]
    r = audio.sfx_batch(str(src), str(tmp_path / "out2"), "16000", lossless=True)
    assert sorted(r["written"]) == ["colpo_16000.flac", "porta_16000.flac"]
    (tmp_path / "bad.json").write_text(json.dumps({"colpo": "veloce"}))
    with pytest.raises(ValueError, match="colpo"):
        audio.sfx_batch(str(src), str(tmp_path / "out3"), str(tmp_path / "bad.json"))


def test_backends_library_counts(monkeypatch):
    monkeypatch.setattr(audio.shutil, "which", lambda k: None)
    monkeypatch.setattr(audio, "_libfluidsynth", lambda: "/usr/lib/libfluidsynth.so.3")
    b = audio.backends()
    assert b["fluidsynth"] is True and b["fluidsynth_cli"] is False and "note" in b
    assert b["fluidsynth_sf3"] is None          # no ldd: unknown, not False
    monkeypatch.setattr(audio, "_libfluidsynth", lambda: None)
    assert audio.backends()["fluidsynth"] is False
