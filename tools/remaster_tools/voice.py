"""Dubbing script, ElevenLabs generation (API) and checks."""
import csv
import json
import os
import re
import shutil
import subprocess
import urllib.request

from . import text as textmod

SPOKEN_KINDS = {"balloon", "answer", "question", "examine", "subtitle", "comment", ""}
# lines never recorded: values filled in by the game, messages for testers
SKIP_RE = re.compile(r"%[A-Za-z]")
API = "https://api.elevenlabs.io/v1"


def clean(t: str) -> str:
    t = t.replace("\\n", " ").replace("\\", " ")
    t = re.sub(r"[%#@]\w*", "", t)  # engine control codes
    return re.sub(r"\s+", " ", t).strip()


def script(catalog_path, lang, out_path, protagonist=""):
    rows = textmod.read_catalog(catalog_path)
    lines, per = [], {}
    for r in rows:
        if r.get("kind", "") not in SPOKEN_KINDS:
            continue
        spk = r.get("speaker") or protagonist or "NARRATORE"
        raw = r.get("text") or r["source"]
        if SKIP_RE.search(raw) or not re.search(r"[A-Za-zÀ-ÿ]", raw):
            continue
        t = clean(raw)
        if not t:
            continue
        lines.append({"key": r["key"], "speaker": spk, "text": t, "context": r.get("location", ""),
                      "kind": r.get("kind", ""), "tag": "", "recita": ""})
        per[spk] = per.get(spk, 0) + len(t)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["key", "speaker", "text", "context", "kind", "tag", "recita"], delimiter="\t")
        w.writeheader()
        w.writerows(lines)
    return {"lines": len(lines), "characters_total": sum(per.values()),
            "estimated_credits_without_tags": round(sum(per.values()) * CREDITS_PER_CHAR),
            "per_speaker": dict(sorted(per.items(), key=lambda kv: -kv[1]))}


END_OF_SENTENCE = (".", "!", "?", "…", '"', "»")
PAUSE_END, PAUSE_CONTINUE = 0.6, 0.15     # seconds after a line


def pause_after(text: str) -> float:
    """0.6 s after a line that ends a sentence, 0.15 s if the sentence goes on in the next line."""
    return PAUSE_END if text.rstrip().endswith(END_OF_SENTENCE) else PAUSE_CONTINUE


SEQUENCE_KINDS = {"subtitle", "scene"}
TAG_MODELS = ("eleven_v3", "eleven_v4")   # models that act audio tags; older ones read them aloud


def context_of(rows, i):
    """previous_text / next_text: the lines before and after said by the same speaker in the same scene.
    Only for scenes played in sequence: in dialogues short lines borrowed words from the context."""
    r = rows[i]
    if r.get("kind") not in SEQUENCE_KINDS:
        return None, None
    prev = next((rows[j]["text"] for j in range(i - 1, -1, -1)
                 if rows[j]["speaker"] == r["speaker"] and rows[j].get("context") == r.get("context")), None)
    nxt = next((rows[j]["text"] for j in range(i + 1, len(rows))
                if rows[j]["speaker"] == r["speaker"] and rows[j].get("context") == r.get("context")), None)
    return prev, nxt


def spoken(row, model=None):
    """Text sent to the TTS: performance tag + text to speak (may differ from the subtitle)."""
    t = row.get("recita") or row["text"]
    tag = row.get("tag") or ""
    if model and not model.startswith(TAG_MODELS):
        tag = ""
    return (tag + " " + t).strip()


def _tts(api_key, voice_id, text, model, settings, lang, previous_text=None, next_text=None):
    body = {"text": text, "model_id": model, "voice_settings": settings}
    if lang:
        body["language_code"] = lang
    if previous_text:
        body["previous_text"] = previous_text
    if next_text:
        body["next_text"] = next_text
    req = urllib.request.Request(f"{API}/text-to-speech/{voice_id}?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode(),
                                 headers={"xi-api-key": api_key, "Content-Type": "application/json",
                                          "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def generate(script_path, cast_path, out_dir, lang, api_key=None, limit=None, dry_run=False):
    """Generate missing lines only (never regenerates an existing file)."""
    api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    with open(cast_path, encoding="utf-8") as f:
        cast = json.load(f)
    cast = cast.get("voci", cast)   # nested layout: {"modello", "voci": {...}, "scartate": {...}}
    with open(script_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    os.makedirs(out_dir, exist_ok=True)
    for i, r in enumerate(rows):
        r["_prev"], r["_next"] = context_of(rows, i)
    todo = [r for r in rows if not os.path.exists(os.path.join(out_dir, r["key"] + ".ogg"))]
    missing_cast = sorted({r["speaker"] for r in todo if r["speaker"] not in cast})
    if missing_cast:
        raise KeyError("personaggi senza voce nel cast: " + ", ".join(missing_cast))
    if limit:
        todo = todo[:limit]
    if dry_run:
        chars = sum(len(spoken(r)) for r in todo)
        return {"would_generate": len(todo), "characters": chars,
                "estimated_credits": round(chars * CREDITS_PER_CHAR)}
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY non impostata")
    keep = os.path.join(out_dir, "originali")
    os.makedirs(keep, exist_ok=True)
    done = 0
    for r in todo:
        c = cast[r["speaker"]]
        mp3_path = os.path.join(keep, r["key"] + ".mp3")
        if not os.path.exists(mp3_path):
            # every paid call is made once: on an error stop and say why (never retry, never change voice)
            try:
                model = c.get("model", DEFAULT_MODEL)
                mp3 = _tts(api_key, c["voice_id"], spoken(r, model), model, voice_settings(c), lang,
                           r["_prev"], r["_next"])
            except Exception as e:  # noqa: BLE001
                return {"generated": done, "stopped_at": r["key"], "error": str(e)[:300]}
            with open(mp3_path, "wb") as f:
                f.write(mp3)
        to_ogg(mp3_path, os.path.join(out_dir, r["key"] + ".ogg"), pad=pause_after(r["text"]), filt=c.get("filter") or c.get("filtro"))
        done += 1
    return {"generated": done}


DEFAULT_MODEL = "eleven_v4"
CREDITS_PER_CHAR = 0.43      # measured on a real dubbing (performance tags included)
FILTERS = {
    "robot": "afftfilt=real='hypot(re,im)*0.9':imag='0':win_size=1024:overlap=0.75,aecho=0.8:0.6:12:0.4,highpass=f=150",
    "telefono": "highpass=f=320,lowpass=f=3300,acompressor=threshold=0.1:ratio=4",
    "tv": "highpass=f=180,lowpass=f=6000,acompressor=threshold=0.2:ratio=3",
    # child voices can't be made with Voice Design: a woman's voice made into a boy's,
    # formants -10% (longer vocal tract), pitch -15% in all, less air (needs ffmpeg with rubberband)
    "ragazzo": "aresample=44100,asetrate=39690,aresample=44100,atempo=1.1111,"
               "rubberband=pitch=0.9444:formant=preserved,highshelf=f=7000:g=-3",
}


def voice_settings(c):
    if "impostazioni" in c:          # nested settings layout
        return dict(c["impostazioni"])
    s = {"stability": c.get("stability", 0.3), "similarity_boost": c.get("similarity", 0.8),
         "style": c.get("style", 0.7)}
    if "speed" in c:
        s["speed"] = c["speed"]   # pace is set in the voice, never by time-stretching afterwards
    return s


def to_ogg(src, dst, lufs=None, pad=0.0, filt=None):
    """Trim silences, optional character filter, level of the `voice` group in the mix (per
    file: normalization and mix in one encode, default -18 LUFS), mono 44.1 kHz, pause appended."""
    if lufs is None:
        from . import audio
        lufs = audio.MIX["voice"]
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg non trovato")
    chain = ["silenceremove=start_periods=1:start_threshold=-50dB",
             "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse"]
    if filt:
        chain.append(FILTERS.get(filt, filt))
    chain.append(f"loudnorm=I={lufs}:TP=-1.5:LRA=11")
    if pad > 0:
        chain.append(f"apad=pad_dur={pad}")
    subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-af", ",".join(chain),
                    "-ac", "1", "-ar", "44100", "-c:a", "libvorbis", "-q:a", "5", dst], check=True)


def duration(path):
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    out = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def check(script_path, voice_dir):
    with open(script_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    issues = []
    for r in rows:
        p = os.path.join(voice_dir, r["key"] + ".ogg")
        if not os.path.exists(p):
            issues.append({"key": r["key"], "issue": "mancante"})
            continue
        d = duration(p)
        if d is None:
            continue
        cps = len(r["text"]) / max(d, 0.05)
        if cps > 28 or cps < 5:
            issues.append({"key": r["key"], "issue": f"durata anomala ({d:.1f}s, {cps:.0f} car/s)"})
    return {"lines": len(rows), "issues": issues}


def check_transcripts(script_path, transcripts_path):
    """Compare each line with its automatic transcription ({key: text}): missing words,
    performance tags read aloud. Returns the lines to listen to."""
    import difflib
    with open(script_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    with open(transcripts_path, encoding="utf-8") as f:
        heard = json.load(f)

    def words(t):
        return re.findall(r"[\wÀ-ÿ']+", t.lower())
    flagged = []
    for r in rows:
        h = heard.get(r["key"])
        if h is None:
            continue
        want, got = words(r.get("recita") or r["text"]), words(h)
        sm = difflib.SequenceMatcher(None, want, got)
        ratio = sm.ratio()
        # a single missing word ("non") can turn the line around: report every one
        missing = [w for tag, i1, i2, _, _ in sm.get_opcodes() if tag in ("delete", "replace") for w in want[i1:i2]]
        tag_words = set(words(r.get("tag", "")))
        read_tag = bool(tag_words) and len(tag_words & set(got) - set(want)) >= max(1, len(tag_words) // 2)
        if missing or read_tag or ratio < 0.80:     # WER above ~20% or any missing word
            flagged.append({"key": r["key"], "similarity": round(ratio, 2), "missing_words": missing,
                            "tag_read_aloud": read_tag, "expected": r.get("recita") or r["text"], "heard": h})
    return {"lines": len(rows), "flagged": flagged}
