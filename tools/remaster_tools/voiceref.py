"""Measures of speech for the "similar voice" casting: reference fragments versus the previews of
existing library voices.

The reference fragments (short clean clips of a character in the source work) are used ONLY to
measure numbers: they are never uploaded to any service, never used to clone a voice, and can be
deleted right after the measure (`--delete-after`). The output keeps only the numbers.

Measures (per file, then a weighted mean over the voiced time):
- f0_median_hz, f0_p10_hz, f0_p90_hz: pitch from YIN (cumulative mean normalised difference)
  on the voiced frames;
- f0_var_st: spread of the pitch in semitones (p90 - p10), how "musical" the delivery is;
- centroid_hz: spectral centroid of the speech frames (brightness of the timbre);
- slope_db_khz: slope of the spectral envelope up to 4 kHz (more negative = darker, softer);
- hnr_db: harmonics-to-noise ratio estimated from the YIN aperiodicity (low = rough, breathy);
- rate_syl_s: syllable-like energy peaks per second of speech (speaking rate);
- pause_ratio, pause_mean_s: share and mean length of the pauses inside the speech span;
- dyn_range_db: loud speech (95th percentile) minus the quiet frames (10th) inside the speech
  span: low with a music or noise bed under the voice;
- mfcc: 12 mean cepstral coefficients (c1..c12) of the long-term spectrum of the speech frames,
  on 18 mel bands from 80 Hz to 4 kHz (the same limit as the slope, for band-limited copies):
  the overall shape of the timbre, which centroid and slope alone summarise in two numbers.

Checks in the shortlist (`match`):
- a preview without pauses (pause_ratio < NO_PAUSE) has a bed of music or noise: it is flagged
  and its pauses and roughness weigh BED_WEIGHT times less (the bed fills the pauses and lowers
  the harmonics-to-noise ratio);
- a median pitch outside PITCH_RANGE for the declared gender and age (voices.json, or the
  reference) is flagged as a possible octave error of the pitch tracker or a wrong label;
- fewer than MIN_SAME_AGE candidates of the right age: look for more.
"""
import glob
import json
import math
import os
import shutil
import subprocess
import urllib.request
import wave

import numpy as np

SR = 16000
HOP = 160            # 10 ms
WIN = 640            # 40 ms analysis window
F0_MIN, F0_MAX = 60.0, 500.0
YIN_THRESHOLD = 0.15
VOICED_MAX_APERIODICITY = 0.35
SILENCE_DB = 30.0    # frames this far below the loud speech (95th percentile) are silence
MIN_PAUSE_S = 0.15
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".opus", ".aac")

# Distance between reference and candidate: (scale, weight) per measure. The difference is
# divided by the scale (what counts as "clearly different") and multiplied by the weight.
# Pitch and timbre weigh most because the voice settings cannot change them; rate and pauses
# weigh least because speed and the direction (punctuation, pauses) correct them afterwards.
FEATURES = {
    "f0_st":        (2.0, 3.0),    # median pitch, semitones
    "centroid_oct": (0.25, 2.0),   # brightness, octaves (log2 ratio)
    "mfcc":         (3.0, 1.5),    # shape of the timbre: RMS difference of c1..c12, dB
    "hnr_db":       (4.0, 1.5),    # roughness
    "slope_db_khz": (2.0, 1.0),    # spectral tilt
    "f0_var_st":    (2.0, 1.0),    # pitch variability
    "rate_log2":    (0.3, 0.5),    # speaking rate (log2 ratio)
    "pause_ratio":  (0.10, 0.5),   # share of pauses
}
SPEED_RANGE = (0.7, 1.2)          # what ElevenLabs accepts for `speed`
NO_PAUSE = 0.02                   # below this share of pauses: music or noise under the voice
BED_DYN_DB = 20.0                 # ...and with less dynamics than this, almost surely a bed
BED_WEIGHT = 0.2                  # weight factor of pauses and roughness for such a preview
BED_FEATURES = ("pause_ratio", "hnr_db")
MIN_SAME_AGE = 5
N_MEL, N_MFCC, MEL_LO, MEL_HI = 18, 12, 80.0, 4000.0
# plausible median speaking pitch (Hz) by gender and age; None = age not declared
PITCH_RANGE = {
    ("male", "young"): (90, 180), ("male", "middle_aged"): (80, 170), ("male", "old"): (75, 180),
    ("male", None): (75, 180),
    ("female", "young"): (160, 300), ("female", "middle_aged"): (145, 270), ("female", "old"): (130, 260),
    ("female", None): (130, 300),
    (None, "child"): (200, 420),
}
AGES = {"young": "young", "giovane": "young", "middle_aged": "middle_aged", "middle aged": "middle_aged",
        "middle-aged": "middle_aged", "adult": "middle_aged", "adulto": "middle_aged", "adulta": "middle_aged",
        "old": "old", "elderly": "old", "anziano": "old", "anziana": "old", "vecchio": "old",
        "child": "child", "kid": "child", "bambino": "child", "bambina": "child"}
GENDERS = {"male": "male", "m": "male", "man": "male", "maschio": "male", "uomo": "male",
           "female": "female", "f": "female", "woman": "female", "femmina": "female", "donna": "female"}


# ---------------------------------------------------------------------------- audio input

def load(path, start=None, end=None):
    """Mono float32 at 16 kHz. ffmpeg when present (any format); plain WAV otherwise."""
    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-v", "error", "-nostdin"]
        if start is not None:
            cmd += ["-ss", str(start)]
        if end is not None:
            cmd += ["-to", str(end)]
        cmd += ["-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg non legge {path}: {r.stderr.decode(errors='replace')[:200]}")
        return np.frombuffer(r.stdout, dtype="<f4").astype(np.float32)
    with wave.open(path, "rb") as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise RuntimeError("senza ffmpeg si leggono solo WAV a 16 bit")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        t = np.arange(0, len(x) / sr, 1.0 / SR)
        x = np.interp(t, np.arange(len(x)) / sr, x).astype(np.float32)
    a = int((start or 0) * SR)
    b = int(end * SR) if end is not None else len(x)
    return x[a:b]


# ---------------------------------------------------------------------------- analysis

def _frames(x, length):
    n = 1 + max(0, (len(x) - length) // HOP)
    if len(x) < length:
        x = np.pad(x, (0, length - len(x)))
    idx = np.arange(length)[None, :] + HOP * np.arange(n)[:, None]
    return x[idx]


def _yin(frames):
    """f0 (Hz) and aperiodicity per frame. frames: (n, WIN + tau_max)."""
    tau_max = int(SR / F0_MIN)
    tau_min = int(SR / F0_MAX)
    w = WIN
    x0 = frames[:, :w]
    nfft = 1 << int(math.ceil(math.log2(w + tau_max + w)))
    A = np.fft.rfft(frames, nfft)
    B = np.fft.rfft(x0, nfft)
    r = np.fft.irfft(A * np.conj(B), nfft)[:, :tau_max + 1]          # sum x[j] x[j+tau], j < w
    sq = np.concatenate([np.zeros((frames.shape[0], 1)), np.cumsum(frames ** 2, axis=1)], axis=1)
    e0 = sq[:, w][:, None]
    taus = np.arange(tau_max + 1)
    et = sq[:, taus + w] - sq[:, taus]
    d = np.maximum(e0 + et - 2 * r, 0.0)
    d[:, 0] = 0.0
    cum = np.cumsum(d[:, 1:], axis=1)
    dn = np.ones_like(d)
    dn[:, 1:] = d[:, 1:] * taus[1:] / np.maximum(cum, 1e-12)
    f0 = np.zeros(frames.shape[0])
    ap = np.ones(frames.shape[0])
    for i in range(frames.shape[0]):
        row = dn[i]
        below = np.nonzero(row[tau_min:tau_max] < YIN_THRESHOLD)[0]
        if below.size:
            t = tau_min + below[0]
            while t + 1 < tau_max and row[t + 1] < row[t]:
                t += 1
        else:
            t = tau_min + int(np.argmin(row[tau_min:tau_max]))
        if 1 <= t < tau_max:
            a, b, c = row[t - 1], row[t], row[t + 1]
            den = a - 2 * b + c
            shift = 0.5 * (a - c) / den if abs(den) > 1e-12 else 0.0
            shift = max(-1.0, min(1.0, shift))
        else:
            shift = 0.0
        ap[i] = float(row[t])
        f0[i] = SR / (t + shift)
    return f0, ap


def measure_signal(x):
    x = np.asarray(x, dtype=np.float64)
    if len(x) < SR // 2:
        raise ValueError("frammento troppo corto (serve almeno mezzo secondo)")
    x = x - x.mean()
    tau_max = int(SR / F0_MIN)
    fr = _frames(x, WIN + tau_max + 1)
    rms = np.sqrt((fr[:, :WIN] ** 2).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    loud = np.percentile(db, 95)
    speech = db > loud - SILENCE_DB
    f0, ap = _yin(fr)
    voiced = speech & (ap < VOICED_MAX_APERIODICITY) & (db > loud - 20)
    if voiced.sum() < 10:
        raise ValueError("troppo poco parlato con voce nel frammento")
    fv = f0[voiced]
    p10, p50, p90 = np.percentile(fv, [10, 50, 90])
    # spectrum of the speech frames
    win = np.hanning(WIN)
    spec = np.abs(np.fft.rfft(fr[speech, :WIN] * win, axis=1)) ** 2
    freqs = np.fft.rfftfreq(WIN, 1.0 / SR)
    band = (freqs >= 80) & (freqs <= 7500)
    p = spec[:, band].mean(axis=0) + 1e-12
    f = freqs[band]
    centroid = float((p * f).sum() / p.sum())
    # tilt of the spectral envelope: loudest bin of each 250 Hz band from 80 Hz to 4 kHz (the
    # harmonic peaks, not the gaps between them), floored 60 dB under the peak; up to 4 kHz only,
    # because old trailers and broadcast copies are often band-limited above it
    pdb = 10 * np.log10(p)
    edges = np.arange(80, 4000, 250)
    bx, by = [], []
    for lo in edges:
        m = (f >= lo) & (f < lo + 250)
        if m.any():
            bx.append((lo + 125) / 1000.0)
            by.append(pdb[m].max())
    by = np.maximum(np.array(by), max(by) - 60)
    slope = float(np.polyfit(np.array(bx), by, 1)[0])
    mfcc = _mfcc(p, f)
    apv = np.clip(ap[voiced], 1e-4, 0.999)
    hnr = float(np.median(10 * np.log10((1 - apv) / apv)))
    # pauses and rate, on a 10 ms envelope
    k = 5
    env = np.convolve(rms, np.ones(k) / k, mode="same")
    edb = 20 * np.log10(env + 1e-9)
    sp = edb > loud - SILENCE_DB
    idx = np.nonzero(sp)[0]
    first, last = idx[0], idx[-1]
    span = sp[first:last + 1]
    pauses, run = [], 0
    for s in span:
        if not s:
            run += 1
        else:
            if run * HOP / SR >= MIN_PAUSE_S:
                pauses.append(run * HOP / SR)
            run = 0
    span_s = len(span) * HOP / SR
    sdb = np.maximum(db[first:last + 1], loud - 80)
    dyn = float(np.percentile(sdb, 95) - np.percentile(sdb, 10))
    pause_s = sum(pauses)
    speech_s = max(span_s - pause_s, 1e-3)
    # syllable nuclei: local maxima of the envelope within ±60 ms, at least 3 dB above the
    # lowest point between them and the previous nucleus
    rad = 6
    peaks, last_peak = 0, None
    for i in range(first, last + 1):
        lo, hi = max(0, i - rad), min(len(edb), i + rad + 1)
        if not sp[i] or edb[i] < edb[lo:hi].max() or edb[i] < loud - 20:
            continue
        if last_peak is not None:
            if i - last_peak < rad:
                continue
            if edb[i] - edb[last_peak:i + 1].min() < 3.0:
                continue
        peaks += 1
        last_peak = i
    return {"f0_median_hz": round(float(p50), 1), "f0_p10_hz": round(float(p10), 1),
            "f0_p90_hz": round(float(p90), 1),
            "f0_var_st": round(float(12 * math.log2(p90 / p10)), 2),
            "centroid_hz": round(centroid, 0), "slope_db_khz": round(slope, 2),
            "hnr_db": round(hnr, 1), "rate_syl_s": round(peaks / speech_s, 2),
            "pause_ratio": round(pause_s / span_s, 3) if span_s else 0.0,
            "pause_mean_s": round(pause_s / len(pauses), 2) if pauses else 0.0,
            "dyn_range_db": round(dyn, 1), "mfcc": [round(float(c), 2) for c in mfcc],
            "voiced_s": round(float(voiced.sum()) * HOP / SR, 2), "seconds": round(len(x) / SR, 2)}


def _mfcc(power, freqs):
    """Mean cepstrum of a long-term power spectrum: log mel energies (dB) -> DCT-II, c1..c12."""
    mel = lambda hz: 2595.0 * np.log10(1.0 + hz / 700.0)
    pts = 700.0 * (10 ** (np.linspace(mel(MEL_LO), mel(MEL_HI), N_MEL + 2) / 2595.0) - 1.0)
    e = np.empty(N_MEL)
    for i in range(N_MEL):
        lo, c, hi = pts[i:i + 3]
        w = np.clip(np.minimum((freqs - lo) / (c - lo), (hi - freqs) / (hi - c)), 0.0, None)
        e[i] = (w * power).sum() / max(w.sum(), 1e-9)
    ldb = 10 * np.log10(e + 1e-12)
    n = np.arange(N_MEL)
    k = np.arange(1, N_MFCC + 1)[:, None]
    return math.sqrt(2.0 / N_MEL) * (ldb[None, :] * np.cos(np.pi * k * (2 * n + 1) / (2 * N_MEL))).sum(axis=1)


MEAN_KEYS = ("f0_median_hz", "f0_p10_hz", "f0_p90_hz", "f0_var_st", "centroid_hz", "slope_db_khz",
             "hnr_db", "rate_syl_s", "pause_ratio", "pause_mean_s", "dyn_range_db")


def combine(measures):
    """Mean weighted by voiced time (pitch in the log domain)."""
    w = np.array([m["voiced_s"] for m in measures], dtype=float)
    w = w / w.sum()
    out = {}
    for k in MEAN_KEYS:
        if any(k not in m for m in measures):
            continue
        v = np.array([m[k] for m in measures], dtype=float)
        if k.endswith("_hz") and k.startswith("f0"):
            out[k] = round(float(2 ** (w * np.log2(v)).sum()), 1)
        else:
            out[k] = round(float((w * v).sum()), 3)
    if all("mfcc" in m for m in measures):
        out["mfcc"] = [round(float(c), 2) for c in (w[:, None] * np.array([m["mfcc"] for m in measures])).sum(axis=0)]
    out["voiced_s"] = round(sum(m["voiced_s"] for m in measures), 2)
    out["seconds"] = round(sum(m["seconds"] for m in measures), 2)
    return out


def norm_gender(v):
    return GENDERS.get(str(v).strip().lower()) if v else None


def norm_age(v):
    return AGES.get(str(v).strip().lower().replace("-", "_")) if v else None


def read_segments(tsv, group=None, select=None):
    """Rows of a `voice segments` TSV, filtered by group(s) and/or ids ("3,5-7")."""
    base = os.path.dirname(os.path.abspath(tsv))
    with open(tsv, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    if not lines:
        raise ValueError(f"{tsv}: vuoto")
    head = lines[0].split("\t")
    for col in ("file", "inizio", "fine"):
        if col not in head:
            raise ValueError(f"{tsv}: manca la colonna «{col}» (serve id, file, inizio, fine, gruppo)")
    rows = []
    for i, ln in enumerate(lines[1:], 1):
        r = dict(zip(head, ln.split("\t")))
        r["id"] = r.get("id") or str(i)
        r["path"] = r["file"] if os.path.isabs(r["file"]) else os.path.join(base, r["file"])
        r["inizio"], r["fine"] = float(r["inizio"]), float(r["fine"])
        rows.append(r)
    if group:
        groups = {g.strip() for g in str(group).split(",") if g.strip()}
        rows = [r for r in rows if r.get("gruppo") in groups]
    if select:
        ids = set()
        for part in str(select).split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                ids |= {str(n) for n in range(int(a), int(b) + 1)}
            elif part:
                ids.add(part)
        rows = [r for r in rows if r["id"] in ids]
    return rows


def reference(paths, out_path=None, start=None, end=None, delete_after=False, segments=None, group=None,
              select=None, gender=None, age=None):
    """Measure the reference. Only numbers are kept; with delete_after the audio is removed once
    measured (it must stay local and short-lived).

    With `segments` (a TSV of `voice segments`) the stretches chosen by `group` and/or `select`
    are measured straight from the long files, without cutting them first; the JSON then keeps
    the sources (file name, interval, group, attribution confidence) so that the measure can be
    redone or checked after the audio is gone."""
    sources, errors = [], []
    if segments:
        if start is not None or end is not None:
            raise ValueError("--start/--end non valgono con --segments (gli intervalli sono nel TSV)")
        if not group and not select:
            raise ValueError("con --segments indica --group o --select")
        rows = read_segments(segments, group, select)
        if not rows:
            raise ValueError("nessun tratto corrisponde a --group/--select")
        loaded, ms = {}, []
        for r in rows:
            if r["path"] not in loaded:
                loaded[r["path"]] = load(r["path"])
            x = loaded[r["path"]][int(r["inizio"] * SR):int(r["fine"] * SR)]
            src = {"id": r["id"], "file": os.path.basename(r["file"]), "start": r["inizio"], "end": r["fine"],
                   "group": r.get("gruppo"), "confidence": _num(r.get("sicurezza"))}
            try:
                ms.append(measure_signal(x))
                sources.append(src)
            except ValueError as e:
                errors.append({**src, "error": str(e)})
        if not ms:
            raise ValueError("nessun tratto misurabile: " + "; ".join(e["error"] for e in errors))
        files = sorted(loaded)
    else:
        files = _expand(paths)
        if not files:
            raise ValueError("nessun file audio (o usa --segments)")
        ms = [measure_signal(load(p, start, end)) for p in files]
    comb = combine(ms)
    res = {"kind": "voice-reference", "fragments": len(ms), "measures": comb, "per_fragment": ms,
           "note": "solo misure: i frammenti non si caricano su nessun servizio e non servono a clonare"}
    char = {k: v for k, v in (("gender", norm_gender(gender)), ("age", norm_age(age))) if v}
    if char:
        res["character"] = char
    if sources:
        res["sources"] = sources
    if errors:
        res["skipped"] = errors
    warn = _checks(comb, char.get("gender"), char.get("age"), reference=True)
    if warn:
        res["warnings"] = warn
    if out_path:
        _write(out_path, res)
    if delete_after:
        for p in files:
            os.remove(p)
        res["deleted"] = len(files)
    return res


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _checks(m, gender=None, age=None, reference=False):
    """Warnings on one set of measures: bed of music/noise, implausible pitch. For a reference
    made of short stretches the lack of pauses is normal: only a low dynamics is flagged."""
    out = []
    nopause = m.get("pause_ratio", 1.0) < NO_PAUSE
    flat = m.get("dyn_range_db", 99.0) < BED_DYN_DB
    if nopause and flat:
        out.append(f"nessuna pausa e dinamica bassa ({m.get('dyn_range_db', 0):.0f} dB): probabile musica o rumore "
                   "sotto la voce" + ("; cerca tratti più puliti" if reference else ", pause e ruvidità pesano meno"))
    elif nopause and not reference:
        out.append(f"nessuna pausa (quota {m['pause_ratio']:.2f}): possibile musica o sottofondo, "
                   "pause e ruvidità pesano meno")
    rng = PITCH_RANGE.get((gender, age)) or PITCH_RANGE.get((None, age)) or PITCH_RANGE.get((gender, None))
    f0 = m.get("f0_median_hz")
    if rng and f0 and not rng[0] <= f0 <= rng[1]:
        what = " ".join(x for x in (gender, age) if x)
        msg = f"altezza {f0:.0f} Hz fuori dall'intervallo plausibile {rng[0]}-{rng[1]} Hz per {what}"
        alt = [v for v in (f0 / 2, f0 * 2) if rng[0] <= v <= rng[1]]
        if alt:
            msg += f": possibile errore d'ottava (la metà o il doppio, {alt[0]:.0f} Hz, sarebbe plausibile)"
        else:
            msg += ": controlla l'etichetta o l'anteprima"
        out.append(msg)
    return out


# ---------------------------------------------------------------------------- matching

def _vec(m):
    v = {"f0_st": 12 * math.log2(max(m["f0_median_hz"], 1.0)),
         "centroid_oct": math.log2(max(m["centroid_hz"], 1.0)),
         "hnr_db": m["hnr_db"], "slope_db_khz": m["slope_db_khz"], "f0_var_st": m["f0_var_st"],
         "rate_log2": math.log2(max(m["rate_syl_s"], 0.1)), "pause_ratio": m["pause_ratio"]}
    if m.get("mfcc"):
        v["mfcc"] = np.array(m["mfcc"], dtype=float)
    return v


def distance(ref, cand, weights=None):
    """Weighted distance; features missing on either side (old measures without mfcc) are left
    out, and the total is normalised by the weights actually used."""
    a, b = _vec(ref), _vec(cand)
    w = {k: (weights or {}).get(k, wt) for k, (_, wt) in FEATURES.items()}
    parts = {}
    for k, (s, _) in FEATURES.items():
        if k not in a or k not in b:
            continue
        d = float(np.sqrt(np.mean((a[k] - b[k]) ** 2))) if k == "mfcc" else a[k] - b[k]
        parts[k] = w[k] * (d / s) ** 2
    total = math.sqrt(sum(parts.values()) / sum(w[k] for k in parts))
    return round(total, 3), {k: round(math.sqrt(v), 2) for k, v in parts.items()}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def suggest(ref, cand):
    """Starting settings for a candidate, to refine by ear with the trial lines."""
    s = {"similarity_boost": 0.8}
    if ref["rate_syl_s"] > 0 and cand["rate_syl_s"] > 0:
        s["speed"] = round(_clamp(ref["rate_syl_s"] / cand["rate_syl_s"], *SPEED_RANGE), 2)
    dv = ref["f0_var_st"] - cand["f0_var_st"]
    s["stability"] = round(_clamp(0.5 - 0.08 * dv, 0.2, 0.85), 2)
    s["style"] = round(_clamp(0.6 + 0.06 * dv, 0.3, 0.9), 2)
    notes = []
    dst = 12 * math.log2(cand["f0_median_hz"] / ref["f0_median_hz"])
    if abs(dst) >= 1.5:
        notes.append(f"voce {'più acuta' if dst > 0 else 'più grave'} del riferimento di "
                     f"{abs(dst):.1f} semitoni: i parametri non la correggono")
    doct = math.log2(cand["centroid_hz"] / ref["centroid_hz"])
    if abs(doct) >= 0.25:
        notes.append("timbro più " + ("brillante" if doct > 0 else "scuro") + " del riferimento")
    if ref["hnr_db"] - cand["hnr_db"] >= 4:
        notes.append("riferimento più pulito: la candidata è più ruvida o soffiata")
    elif cand["hnr_db"] - ref["hnr_db"] >= 4:
        notes.append("riferimento più ruvido: la candidata è più pulita")
    dp = ref["pause_ratio"] - cand["pause_ratio"]
    if dp >= 0.08:
        notes.append("il riferimento fa più pause: in regia punteggiatura e pause più lunghe")
    elif dp <= -0.08:
        notes.append("il riferimento è più incalzante: meno pause in regia")
    if dv >= 2:
        notes.append("riferimento molto mosso: stabilità bassa, tag di regia più espressivi")
    s["notes"] = notes
    return s


def _candidates(src, cache):
    if os.path.isdir(src) or (os.path.isfile(src) and src.lower().endswith(AUDIO_EXT)):
        return [{"voice_id": os.path.splitext(os.path.basename(p))[0],
                 "name": os.path.splitext(os.path.basename(p))[0], "file": p}
                for p in sorted(_expand([src]))]
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("voices") or data.get("candidates") or []
    base = os.path.dirname(os.path.abspath(src))
    out = []
    for v in data:
        labels = v.get("labels") or {}
        c = {"voice_id": v.get("voice_id") or v.get("id"), "name": v.get("name") or v.get("voice_id"),
             "gender": norm_gender(v.get("gender") or labels.get("gender")),
             "age": norm_age(v.get("age") or labels.get("age"))}
        if v.get("file"):
            c["file"] = v["file"] if os.path.isabs(v["file"]) else os.path.join(base, v["file"])
        elif v.get("preview_url") or v.get("url"):
            c["url"] = v.get("preview_url") or v.get("url")
        else:
            continue
        out.append(c)
    for c in out:
        if "url" in c and "file" not in c:
            os.makedirs(cache, exist_ok=True)
            ext = os.path.splitext(c["url"].split("?")[0])[1] or ".mp3"
            dst = os.path.join(cache, f"{c['voice_id']}{ext}")
            if not os.path.exists(dst):
                # download only: nothing is ever sent to the service
                with urllib.request.urlopen(c["url"], timeout=60) as r, open(dst, "wb") as f:
                    f.write(r.read())
            c["file"] = dst
    return out


def measure(candidates, out_path=None, cache=None, reuse=True):
    """Measure the candidate previews once (folder, single file or voices.json) and keep the
    numbers in out_path, to reuse across characters and sessions (`match --measured`). With
    reuse, voices already in out_path are not measured again."""
    cache = cache or os.path.join(os.path.dirname(os.path.abspath(out_path or candidates)), "previews")
    done = {}
    if reuse and out_path and os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            done = {v["voice_id"]: v for v in json.load(f).get("voices", [])}
    voices, errors, new = [], [], 0
    for c in _candidates(candidates, cache):
        old = done.get(c["voice_id"])
        if old and "mfcc" in old.get("measures", {}):
            voices.append({**old, **{k: v for k, v in c.items() if k in ("name", "gender", "age") and v}})
            continue
        try:
            m = measure_signal(load(c["file"]))
        except (RuntimeError, ValueError, OSError) as e:
            errors.append({"voice_id": c["voice_id"], "error": str(e)})
            continue
        new += 1
        voices.append({"voice_id": c["voice_id"], "name": c["name"], "gender": c.get("gender"),
                       "age": c.get("age"), "measures": m})
    res = {"kind": "voice-measures", "voices": voices, "measured": new, "reused": len(voices) - new,
           "errors": errors}
    if out_path:
        _write(out_path, res)
    return res


def match(ref_path, candidates=None, top=5, out_path=None, cache=None, measured=None, gender=None, age=None,
          strict=False):
    """Shortlist of the existing voices closest to the reference. Candidates come from a folder or
    a voices.json (measured now) and/or from a `voice measure` file (measured before)."""
    if not candidates and not measured:
        raise ValueError("indica --candidates o --measured")
    with open(ref_path, encoding="utf-8") as f:
        ref = json.load(f)
    rm = ref.get("measures", ref)
    char = ref.get("character") or {}
    gender = norm_gender(gender) or char.get("gender")
    age = norm_age(age) or char.get("age")
    pool, errors = [], []
    if measured:
        with open(measured, encoding="utf-8") as f:
            pool += json.load(f).get("voices", [])
    if candidates:
        cache = cache or os.path.join(os.path.dirname(os.path.abspath(out_path or ref_path)), "previews")
        got = measure(candidates, None, cache, reuse=False)
        seen = {v["voice_id"] for v in pool}
        pool += [v for v in got["voices"] if v["voice_id"] not in seen]
        errors += got["errors"]
    rows, excluded = [], []
    for v in pool:
        m = v["measures"]
        vg, va = v.get("gender"), v.get("age")
        mismatch = [x for x, want, have in (("genere", gender, vg), ("età", age, va)) if want and have and want != have]
        if strict and mismatch:
            excluded.append({"voice_id": v["voice_id"], "reason": " e ".join(mismatch) + " diversi"})
            continue
        warn = _checks(m, vg or gender, va or age)
        bed = m.get("pause_ratio", 1.0) < NO_PAUSE
        weights = {k: FEATURES[k][1] * BED_WEIGHT for k in BED_FEATURES} if bed else None
        d, parts = distance(rm, m, weights)
        if mismatch:
            warn.append(" e ".join(mismatch) + " dichiarati diversi dal personaggio")
        rows.append({"voice_id": v["voice_id"], "name": v.get("name"), "gender": vg, "age": va, "distance": d,
                     "parts": parts, "measures": m, "settings": suggest(rm, m), "warnings": warn,
                     "music_bed": bed})
    rows.sort(key=lambda r: r["distance"])
    warnings = _checks(rm, gender, age, reference=True)
    warnings = ["riferimento: " + w for w in warnings]
    if age:
        same = sum(1 for r in rows if r["age"] == age)
        if same < MIN_SAME_AGE:
            warnings.append(f"solo {same} candidate dell'età giusta ({age}, servono almeno {MIN_SAME_AGE}): "
                            "cercane altre nella libreria prima di scegliere")
    flagged = sum(1 for r in rows if r["music_bed"])
    if flagged:
        warnings.append(f"{flagged} anteprime con musica o senza pause: pause e ruvidità pesate meno, "
                        "ascoltale prima di fidarti della classifica")
    res = {"kind": "voice-shortlist", "reference": rm, "character": {"gender": gender, "age": age},
           "weights": {k: w for k, (_, w) in FEATURES.items()}, "shortlist": rows[:top], "measured": len(rows),
           "errors": errors, "warnings": warnings}
    if excluded:
        res["excluded"] = excluded
    if out_path:
        _write(out_path, res)
    return res


def _expand(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += [q for q in sorted(glob.glob(os.path.join(p, "*"))) if q.lower().endswith(AUDIO_EXT)]
        else:
            out.append(p)
    return out


def _write(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
