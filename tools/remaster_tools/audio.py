"""Audio remaster helpers built on ffmpeg (soxr, loudnorm, afftdn) and fluidsynth."""
import json
import os
import re
import shutil
import subprocess

MUSIC_EXT = {".mid": "midi", ".midi": "midi", ".xmi": "xmidi", ".mus": "mus",
             ".mod": "tracker", ".s3m": "tracker", ".xm": "tracker", ".it": "tracker",
             ".wav": "pcm", ".voc": "creative-voc", ".sfx": "raw-pcm", ".raw": "raw-pcm",
             ".ogg": "ogg", ".mp3": "mp3", ".flac": "flac"}


def backends():
    return {k: bool(shutil.which(k)) for k in ("ffmpeg", "ffprobe", "fluidsynth", "mt32emu-smf2wav", "audiosr")}


def scan(root):
    found = {}
    for d, _dirs, files in os.walk(root):
        for f in files:
            kind = MUSIC_EXT.get(os.path.splitext(f)[1].lower())
            if kind:
                found.setdefault(kind, []).append(os.path.relpath(os.path.join(d, f), root))
    tracks = [f for f in os.listdir(root) if f.lower().startswith("track")] if os.path.isdir(root) else []
    if tracks:
        found["cd-audio"] = sorted(tracks)
    return {k: {"count": len(v), "examples": v[:5]} for k, v in found.items()}


def _ffmpeg(args):
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg non trovato")
    subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


# mix levels from the reference project: music well under the voices
LEVELS = {"voice": -18.0, "sfx_max": -16.0, "music": -25.0}
MAX_GAIN_DB = 8.0


def loudness(path):
    """Integrated loudness (LUFS) measured with ffmpeg's ebur128 filter."""
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg non trovato")
    res = subprocess.run([exe, "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=framelog=quiet",
                          "-f", "null", "-"], capture_output=True, text=True)
    vals = re.findall(r"I:\s*(-?[\d.]+) LUFS", res.stderr)
    if not vals:
        raise RuntimeError(f"loudness non misurabile: {path}")
    return float(vals[-1])


def master(src, dst, lufs=LEVELS["music"], denoise=False, declip=False, quality=6, loop=None):
    """Same level for every track: static gain (at most ±8 dB, dynamics untouched) towards `lufs`,
    optional declip for tracks already clipped in the original, limiter, 44.1 kHz OGG.
    loop=(start_sample, length_samples) is kept as Vorbis comments."""
    gain = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, lufs - loudness(src)))
    af = []
    if declip:
        af.append("adeclip")
    if denoise:
        af.append("afftdn=nf=-30")
    af.append(f"volume={gain:.2f}dB")
    af.append("alimiter=limit=0.89:attack=5:release=50:level=false")
    af.append("aresample=44100:resampler=soxr")
    meta = []
    if loop:
        meta = ["-metadata", f"LOOPSTART={loop[0]}", "-metadata", f"LOOPLENGTH={loop[1]}"]
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    _ffmpeg(["-i", src, "-af", ",".join(af), "-c:a", "libvorbis", "-q:a", str(quality), *meta, dst])
    return dst


def render_midi(mid, soundfont, dst, gain=0.6, rate=44100):
    fs = shutil.which("fluidsynth")
    if not fs:
        raise RuntimeError("fluidsynth non trovato")
    wav = dst + ".tmp.wav"
    subprocess.run([fs, "-ni", "-g", str(gain), "-r", str(rate), "-F", wav, soundfont, mid],
                   check=True, capture_output=True)
    try:
        master(wav, dst)
    finally:
        if os.path.exists(wav):
            os.remove(wav)
    return dst


def raw_to_wav(src, dst, rate, fmt="u8", channels=1):
    _ffmpeg(["-f", fmt, "-ar", str(rate), "-ac", str(channels), "-i", src, dst])
    return dst


def sfx_batch(src_dir, out_dir, rates_json=None, default_rate=11025, raw_fmt="u8", denoise=True):
    """Raw/WAV effects -> 44.1 kHz OGG named <name>_<rate>.ogg (rate = playback rate in the scripts)."""
    rates = {}
    if rates_json and os.path.exists(rates_json):
        with open(rates_json, encoding="utf-8") as f:
            rates = json.load(f)  # {"name": [11025, 22050]}
    os.makedirs(out_dir, exist_ok=True)
    done = []
    for name in sorted(os.listdir(src_dir)):
        base, ext = os.path.splitext(name)
        ext = ext.lower()
        if ext not in (".sfx", ".raw", ".wav", ".voc"):
            continue
        for rate in rates.get(base.lower(), [default_rate]):
            src = os.path.join(src_dir, name)
            tmp = os.path.join(out_dir, f".{base}_{rate}.wav")
            if ext in (".sfx", ".raw"):
                raw_to_wav(src, tmp, rate, raw_fmt)
            else:
                _ffmpeg(["-i", src, tmp])
            af = ["highpass=f=20"]
            if denoise:
                af.append("afftdn=nf=-35")
            af.append("aresample=44100:resampler=soxr:precision=28")
            dst = os.path.join(out_dir, f"{base.lower()}_{rate}.ogg")
            _ffmpeg(["-i", tmp, "-af", ",".join(af), "-c:a", "libvorbis", "-q:a", "5", dst])
            os.remove(tmp)
            done.append(os.path.basename(dst))
    return {"written": done}
