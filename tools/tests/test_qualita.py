"""Speech restoration, local transcription, weight of the pack, visual regression (synthetic data)."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from remaster_tools import audio, release, review, transcribe  # noqa: E402

need_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg assente")


@need_ffmpeg
def test_restore_speech_resamples_and_cleans(tmp_path):
    src = tmp_path / "riga.wav"
    # 8-bit 11 kHz "speech" with hiss and a DC offset
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "sine=f=300:d=1,volume=0.5[a];anoisesrc=d=1:a=0.02[n];[a][n]amix=inputs=2,dcshift=0.1",
                    "-ar", "11025", "-c:a", "pcm_u8", str(src)], check=True)
    out = tmp_path / "out" / "riga.flac"
    audio.restore_speech(str(src), str(out))
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of", "json",
                           str(out)], capture_output=True, text=True).stdout
    s = json.loads(info)["streams"][0]
    assert s["sample_rate"] == "44100" and s["channels"] == 1
    res = audio.restore_speech_batch(str(tmp_path), str(tmp_path / "out2"))
    assert res["written"] >= 1


def test_transcribe_resumable_with_any_backend(tmp_path):
    d = tmp_path / "voci"
    d.mkdir()
    for k in ("a1b2c3d4", "0000beef"):
        (d / f"{k}.ogg").write_bytes(b"x")
    calls = []

    def fake(path):
        calls.append(path)
        return "testo di " + os.path.basename(path)[:4]
    out = str(tmp_path / "t.json")
    r = transcribe.transcribe_dir(str(d), out, "it", runner=fake)
    assert r["transcribed"] == 2 and json.load(open(out))["a1b2c3d4"] == "testo di a1b2"
    r = transcribe.transcribe_dir(str(d), out, "it", runner=fake)
    assert r["transcribed"] == 0 and len(calls) == 2  # already done: not redone
    assert set(transcribe.backends()) == {"faster-whisper", "whisper.cpp", "ffmpeg"}


def test_budget_flags_heavy_pictures(tmp_path):
    bg = tmp_path / "gfx" / "bg"
    bg.mkdir(parents=True)
    Image.new("RGB", (3600, 2400), (10, 20, 30)).save(bg / "grande.jpg", quality=50)
    Image.new("RGB", (960, 600), (10, 20, 30)).save(bg / "piccolo.png")
    (tmp_path / "text").mkdir()
    (tmp_path / "text" / "it.tsv").write_text("a\tb\n")
    r = release.budget(str(tmp_path))
    assert r["files"] == 3 and r["largest_decoded"][0]["file"].endswith("grande.jpg")
    assert r["targets"]["web"]["ok"] is False and r["targets"]["desktop"]["ok"] is True


def test_visual_diff(tmp_path):
    a, b = tmp_path / "prima", tmp_path / "dopo"
    a.mkdir()
    b.mkdir()
    base = np.zeros((60, 80, 3), np.uint8)
    for n in ("stanza1.png", "stanza2.png"):
        Image.fromarray(base).save(a / n)
    Image.fromarray(base).save(b / "stanza1.png")
    changed = base.copy()
    changed[10:30, 10:40] = 200
    Image.fromarray(changed).save(b / "stanza2.png")
    r = review.diff_dirs(str(a), str(b), str(tmp_path / "diff.html"))
    assert r["compared"] == 2 and [c["file"] for c in r["changed"]] == ["stanza2.png"]
    assert "stanza2.png" in open(r["page"], encoding="utf-8").read()


def test_spending_cap_and_readme(tmp_path):
    from remaster_tools import project
    data = project.init("Avventura di prova", str(tmp_path))
    project.set_key(data, "voice.enabled", True)
    assert "tetto di spesa del progetto" in project.missing_answers(data)
    project.set_key(data, "budget.cap_usd", 10)
    assert "tetto di spesa del progetto" not in project.missing_answers(data)
    assert project.spend(data, "fal.ai", 6, "usd", "lotto 1")["over_cap"] == []
    r = project.spend(data, "fal.ai", 5, "usd", "lotto 2")
    assert r["usd"] == 11 and r["over_cap"]
    project.set_key(data, "extras.hints", True)
    text = release.readme(data, "recipe", "1.0.0")
    assert "premi H" in text


def test_cli_audio_sfx_and_spend_units(tmp_path):
    import subprocess as sp
    rst = os.path.join(os.path.dirname(HERE), "rstool.py")
    (tmp_path / "fx").mkdir()
    r = sp.run([sys.executable, rst, "audio", "sfx", str(tmp_path / "fx"), "--out", str(tmp_path / "o")],
               capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    from remaster_tools import project
    data = project.init("Prova", str(tmp_path))
    with pytest.raises(ValueError):
        project.spend(data, "fal.ai", 9, "prova")
    assert project.spend(data, "fal.ai", 9, "USD")["usd"] == 9
