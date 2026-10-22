"""Local, free transcription of voice lines, for the check after generation (voice transcripts)
and for the census of who speaks in original talkies. Backends, in order:
  faster-whisper (pip install faster-whisper; CPU int8 is fine for short lines)
  whisper.cpp    (binary `whisper-cli` or `whisper-cpp` with a ggml model file)
The output is {key: text} with key = file name without extension (textKey for voice/<lang>/).
"""
import json
import os
import shutil
import subprocess
import tempfile

AUDIO = (".ogg", ".mp3", ".wav", ".flac", ".m4a")


def backends():
    try:
        import faster_whisper  # noqa: F401
        fw = True
    except ImportError:
        fw = False
    return {"faster-whisper": fw, "whisper.cpp": bool(shutil.which("whisper-cli") or shutil.which("whisper-cpp")),
            "ffmpeg": bool(shutil.which("ffmpeg"))}


def _faster_whisper(model_name, lang):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    def run(path):
        segs, _info = model.transcribe(path, language=lang, beam_size=5, vad_filter=False)
        return " ".join(s.text.strip() for s in segs).strip()
    return run


def _whisper_cpp(model_path, lang):
    exe = shutil.which("whisper-cli") or shutil.which("whisper-cpp")
    if not model_path or not os.path.exists(model_path):
        raise RuntimeError("whisper.cpp: indica il file del modello ggml con --model")

    def run(path):
        with tempfile.TemporaryDirectory() as d:
            wav = os.path.join(d, "in.wav")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-ar", "16000", "-ac", "1", wav], check=True)
            base = os.path.join(d, "out")
            subprocess.run([exe, "-m", model_path, "-l", lang, "-nt", "-otxt", "-of", base, wav],
                           check=True, capture_output=True)
            with open(base + ".txt", encoding="utf-8") as f:
                return " ".join(f.read().split())
    return run


def transcribe_dir(src_dir, out_json, lang, model="small", backend=None, only=None, runner=None):
    """Transcribe every audio file in src_dir (resumable: keeps what out_json already has)."""
    if runner is None:
        b = backend or ("faster-whisper" if backends()["faster-whisper"] else
                        "whisper.cpp" if backends()["whisper.cpp"] else None)
        if b is None:
            raise RuntimeError("nessun motore di trascrizione: pip install faster-whisper (gratuito, locale)")
        runner = _faster_whisper(model, lang) if b == "faster-whisper" else _whisper_cpp(model, lang)
    done = {}
    if os.path.exists(out_json):
        with open(out_json, encoding="utf-8") as f:
            done = json.load(f)
    files = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(AUDIO))
    new = 0
    for f in files:
        key = os.path.splitext(f)[0]
        if key in done or (only and key not in only):
            continue
        done[key] = runner(os.path.join(src_dir, f))
        new += 1
        if new % 20 == 0:
            _save(done, out_json)
    _save(done, out_json)
    return {"transcribed": new, "total": len(done), "file": out_json,
            "next": "rstool.py voice transcripts <copione> " + out_json}


def _save(data, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
