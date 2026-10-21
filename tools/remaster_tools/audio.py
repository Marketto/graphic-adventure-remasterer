"""Audio remaster helpers built on ffmpeg (soxr, ebur128, afftdn, adeclip, alimiter) and fluidsynth:
normalization per group (music, sfx, voice), then the mix between groups."""
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


# Two stages, from the reference project:
#  1. normalization PER GROUP (music, sfx, voice): every group is brought to the same reference
#     level, with the policy of the group (see GROUPS);
#  2. MIX: one offset per group sets the balance between groups (voices on top, music well below).
# Gains of both stages are summed and applied in a single encode (no double lossy pass).
REFERENCE_LUFS = -23.0
GROUPS = {
    # "file": every file at the reference (tracks and lines must sound equally loud)
    # "group": one gain for the whole group, so the differences between files intended by the
    #          authors (a whisper and an explosion) are kept; the loud end (p90) goes to the reference
    "music": {"policy": "file", "dir": "music"},
    "voice": {"policy": "file", "dir": "voice"},
    "sfx": {"policy": "group", "dir": "sfx"},
}
# final level of each group after the mix (LUFS); sfx: level of the loud end, and per-file cap
MIX = {"voice": -18.0, "sfx": -16.0, "music": -25.0}
CAP = {"sfx": -16.0}
LEVELS = {"voice": MIX["voice"], "sfx_max": CAP["sfx"], "music": MIX["music"]}  # compatibility
MAX_GAIN_DB = 8.0
AUDIO_EXT = (".wav", ".ogg", ".flac", ".mp3", ".voc", ".aif", ".aiff")


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


def encode(src, dst, gain_db, denoise=False, declip=False, quality=6, loop=None, mono=False):
    """Static gain (dynamics untouched), optional declip/denoise, limiter, 44.1 kHz OGG Vorbis."""
    af = []
    if declip:
        af.append("adeclip")
    if denoise:
        af.append("afftdn=nf=-30")
    af.append(f"volume={gain_db:.2f}dB")
    af.append("alimiter=limit=0.89:attack=5:release=50:level=false")
    af.append("aresample=44100:resampler=soxr")
    extra = ["-ac", "1"] if mono else []
    meta = []
    if loop:
        meta = ["-metadata", f"LOOPSTART={loop[0]}", "-metadata", f"LOOPLENGTH={loop[1]}"]
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    _ffmpeg(["-i", src, "-af", ",".join(af), *extra, "-c:a", "libvorbis", "-q:a", str(quality), *meta, dst])
    return dst


def master(src, dst, lufs=MIX["music"], denoise=False, declip=False, quality=6, loop=None):
    """One file to a fixed level: static gain (at most ±8 dB) towards `lufs`.
    loop=(start_sample, length_samples) is kept as Vorbis comments."""
    gain = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, lufs - loudness(src)))
    return encode(src, dst, gain, denoise, declip, quality, loop)


def _files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for d, _dirs, fs in os.walk(p):
                out += [os.path.join(d, f) for f in sorted(fs) if f.lower().endswith(AUDIO_EXT)]
        elif p.lower().endswith(AUDIO_EXT):
            out.append(p)
    return sorted(out)


def _percentile(vals, q):
    v = sorted(vals)
    if not v:
        return None
    k = (len(v) - 1) * q / 100
    lo, hi = int(k), min(len(v) - 1, int(k) + 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def normalize_group(group, paths, out_path=None, reference=REFERENCE_LUFS, policy=None, measure=loudness,
                    root=None):
    """Stage 1: measure a group and compute the normalization gain of every file (nothing is
    encoded here). Writes/updates a JSON plan {group: {policy, reference, files: [...]}}."""
    if group not in GROUPS and not policy:
        raise ValueError(f"gruppo sconosciuto {group}: usa {', '.join(GROUPS)} o indica --policy")
    policy = policy or GROUPS[group]["policy"]
    files = _files(paths)
    measured = []
    for f in files:
        try:
            measured.append((f, measure(f)))
        except RuntimeError:
            measured.append((f, None))  # silence or too short: left as is
    vals = [l for _f, l in measured if l is not None and l > -70]
    anchor = _percentile(vals, 90) if vals else None
    entries = []
    for f, l in measured:
        if l is None or l <= -70:
            gain = 0.0
        elif policy == "file":
            gain = reference - l
        else:
            gain = reference - anchor
        rel = os.path.relpath(f, root) if root else os.path.basename(f)
        entries.append({"src": f, "name": rel, "lufs": None if l is None else round(l, 2), "norm_gain": round(gain, 2)})
    info = {"policy": policy, "reference": reference, "files": entries,
            "measured": {"count": len(vals), "min": min(vals) if vals else None, "max": max(vals) if vals else None,
                         "p90": None if anchor is None else round(anchor, 2)}}
    if out_path:
        plan = {}
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as fh:
                plan = json.load(fh)
        plan[group] = info
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, indent=2, ensure_ascii=False)
    return info


def load_mix(path=None):
    """Mix file: {"voice": -18, "sfx": -16, "music": -25, "cap": {"sfx": -16}} (LUFS after the mix)."""
    mix, cap = dict(MIX), dict(CAP)
    if path:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        cap.update(data.pop("cap", {}))
        mix.update({k: float(v) for k, v in data.items() if not k.startswith("_")})
    return mix, cap


def mix_gains(plan, mix=None, cap=None, max_gain=MAX_GAIN_DB):
    """Stage 2: total gain per file = normalization gain + group offset (mix - reference),
    limited by the per-file cap of the group and by ±max_gain (dynamics untouched)."""
    mix = mix or MIX
    cap = CAP if cap is None else cap
    out = {}
    for group, info in plan.items():
        if group not in mix:
            raise ValueError(f"livello di mix mancante per il gruppo {group}")
        offset = mix[group] - info["reference"]
        rows = []
        for e in info["files"]:
            g = e["norm_gain"] + offset if e["lufs"] is not None else 0.0
            notes = []
            if e["lufs"] is not None and group in cap and e["lufs"] + g > cap[group]:
                g = cap[group] - e["lufs"]
                notes.append("cap")
            if abs(g) > max_gain:
                g = max(-max_gain, min(max_gain, g))
                notes.append("limitato a ±%g dB" % max_gain)
            final = None if e["lufs"] is None else round(e["lufs"] + g, 2)
            rows.append({**e, "gain": round(g, 2), "final_lufs": final, "notes": notes})
        out[group] = {"offset": round(offset, 2), "target": mix[group], "files": rows}
    return out


def apply_mix(plan_path, out_dir, mix_path=None, groups=None, dry_run=False, quality=6):
    """Encode every file once with its total gain into <out_dir>/<group dir>/<name>.ogg."""
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    if groups:
        plan = {g: plan[g] for g in groups}
    mix, cap = load_mix(mix_path)
    gains = mix_gains(plan, mix, cap)
    written, limited = [], []
    for group, info in gains.items():
        sub = GROUPS.get(group, {}).get("dir", group)
        for e in info["files"]:
            dst = os.path.join(out_dir, sub, os.path.splitext(e["name"])[0] + ".ogg")
            if e["notes"]:
                limited.append({"file": e["name"], "group": group, "notes": e["notes"]})
            if not dry_run:
                encode(e["src"], dst, e["gain"], quality=quality, mono=(group == "voice"))
            written.append(dst)
    return {"mix": mix, "cap": cap, "written": len(written), "limited": limited,
            "groups": {g: {"offset": i["offset"], "target": i["target"]} for g, i in gains.items()}}


def mix_preview(out, voice=None, music=None, sfx=None, mix_path=None, plan_path=None, duration=12.0,
                music_offsets=(0.0,)):
    """Listening test of the balance: music bed + one effect + one line, with the gains the mix
    would give them. One file per music offset (e.g. 0, -3, +3 dB) to choose by ear."""
    mix, cap = load_mix(mix_path)
    plan = {}
    if plan_path and os.path.exists(plan_path):
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)

    def gain_of(group, path):
        for e in plan.get(group, {}).get("files", []):
            if os.path.abspath(e["src"]) == os.path.abspath(path):
                return mix_gains({group: {**plan[group], "files": [e]}}, mix, cap)[group]["files"][0]["gain"]
        g = mix[group] - loudness(path)
        if group in cap:
            g = min(g, cap[group] - loudness(path))
        return g
    outs = []
    for k, off in enumerate(music_offsets):
        inputs, chains, labels = [], [], []
        for group, path, delay in (("music", music, 0.0), ("sfx", sfx, 1.0), ("voice", voice, 2.0)):
            if not path:
                continue
            g = gain_of(group, path) + (off if group == "music" else 0.0)
            n = len(labels)
            inputs += (["-stream_loop", "-1"] if group == "music" else []) + ["-i", path]
            chains.append(f"[{n}:a]aresample=44100,aformat=channel_layouts=stereo,volume={g:.2f}dB,"
                          f"adelay={int(delay * 1000)}:all=1[a{n}]")
            labels.append(f"[a{n}]")
        if not labels:
            raise ValueError("serve almeno un file tra voce, musica, effetto")
        fc = ";".join(chains) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest," \
            f"atrim=0:{duration},alimiter=limit=0.89[out]"
        base, ext = os.path.splitext(out)
        dst = out if len(music_offsets) == 1 else f"{base}.{k + 1}{ext or '.ogg'}"
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        _ffmpeg([*inputs, "-filter_complex", fc, "-map", "[out]", "-t", str(duration), "-c:a", "libvorbis",
                 "-q:a", "5", dst])
        outs.append({"file": dst, "music_offset_db": off})
    return {"previews": outs, "mix": mix}


def render_midi(mid, soundfont, dst, gain=0.6, rate=44100):
    """MIDI -> audio with fluidsynth. A .wav/.flac destination stays lossless and unleveled, to go
    through `normalize_group` + `apply_mix` with the other tracks; .ogg is leveled at once."""
    fs = shutil.which("fluidsynth")
    if not fs:
        raise RuntimeError("fluidsynth non trovato")
    lossless = dst.lower().endswith((".wav", ".flac"))
    wav = dst if dst.lower().endswith(".wav") else dst + ".tmp.wav"
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    subprocess.run([fs, "-ni", "-g", str(gain), "-r", str(rate), "-F", wav, soundfont, mid],
                   check=True, capture_output=True)
    try:
        if dst.lower().endswith(".flac"):
            _ffmpeg(["-i", wav, dst])
        elif not lossless:
            master(wav, dst)
    finally:
        if wav != dst and os.path.exists(wav):
            os.remove(wav)
    return dst


def raw_to_wav(src, dst, rate, fmt="u8", channels=1):
    _ffmpeg(["-f", fmt, "-ar", str(rate), "-ac", str(channels), "-i", src, dst])
    return dst


def sfx_batch(src_dir, out_dir, rates_json=None, default_rate=11025, raw_fmt="u8", denoise=True, lossless=False):
    """Raw/WAV effects -> 44.1 kHz files named <name>_<rate>.ogg (rate = playback rate in the scripts).
    lossless=True writes .flac, to level them afterwards with normalize_group + apply_mix."""
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
            dst = os.path.join(out_dir, f"{base.lower()}_{rate}." + ("flac" if lossless else "ogg"))
            codec = [] if lossless else ["-c:a", "libvorbis", "-q:a", "5"]
            _ffmpeg(["-i", tmp, "-af", ",".join(af), *codec, dst])
            os.remove(tmp)
            done.append(os.path.basename(dst))
    return {"written": done}
