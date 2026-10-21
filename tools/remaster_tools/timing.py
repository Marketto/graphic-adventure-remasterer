"""Timing of the original measured from a screen recording (emulator under Xvfb + ffmpeg x11grab),
to compare with the remastered engine's step durations.

A step of the game shows up as a frame that differs from the previous one; the intervals
between changes, in a stretch where something animates continuously, are the step duration.
"""
import json
import shutil
import subprocess

import numpy as np


def read_frames(video, fps=None, size=(160, 100), crop=None, start=None, duration=None):
    """Grayscale frames, downscaled (default 160x100: enough to see changes, little memory).
    crop = (x, y, w, h) in video pixels, e.g. only the game area. Returns (frames, fps)."""
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg non trovato")
    if fps is None:
        probe = shutil.which("ffprobe")
        fps = 60.0
        if probe:
            r = subprocess.run([probe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=r_frame_rate", "-of", "json", video], capture_output=True, text=True)
            try:
                num, den = json.loads(r.stdout)["streams"][0]["r_frame_rate"].split("/")
                fps = float(num) / float(den)
            except (KeyError, IndexError, ValueError, ZeroDivisionError):
                pass
    vf = []
    if crop:
        vf.append("crop=%d:%d:%d:%d" % (crop[2], crop[3], crop[0], crop[1]))
    vf.append("scale=%d:%d:flags=area" % size)
    vf.append("format=gray")
    cmd = [exe, "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", video]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-vf", ",".join(vf), "-vsync", "passthrough", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (size[0] * size[1])
    return np.frombuffer(raw[:n * size[0] * size[1]], np.uint8).reshape(n, size[1], size[0]), fps


def change_intervals(frames, fps, threshold=8, min_pixels=0.002):
    """Indices of frames that differ from the previous one (more than `min_pixels` of the picture
    changed by more than `threshold` gray levels: ignores codec noise) and the intervals in ms."""
    f = frames.astype(np.int16)
    diff = np.abs(f[1:] - f[:-1])
    changed = (diff > threshold).mean(axis=(1, 2)) > min_pixels
    idx = np.nonzero(changed)[0] + 1
    iv = np.diff(idx) * 1000.0 / fps
    return idx, iv


def summarize(iv, fps):
    if len(iv) == 0:
        return {"changes": 0}
    frame_ms = 1000.0 / fps
    q = np.percentile(iv, [10, 50, 90])
    return {"changes": int(len(iv) + 1), "median_ms": round(float(q[1]), 1), "p10_ms": round(float(q[0]), 1),
            "p90_ms": round(float(q[2]), 1), "mean_ms": round(float(iv.mean()), 1),
            "resolution_ms": round(frame_ms, 1),
            "note": "intervalli multipli del fotogramma del video: registra a 60 fps o più; misura tratti "
                    "con animazione continua (le pause degli script falsano la media)"}


def measure(video, segments=None, crop=None, threshold=8, size=(160, 100)):
    """segments: [{"name", "start", "duration"}] in seconds; without, the whole video."""
    out = []
    for seg in segments or [{"name": "tutto", "start": None, "duration": None}]:
        frames, fps = read_frames(video, crop=crop, start=seg.get("start"), duration=seg.get("duration"), size=size)
        idx, iv = change_intervals(frames, fps, threshold)
        out.append({"name": seg.get("name"), "frames": int(len(frames)), "fps": round(fps, 3),
                    "duration_s": round(len(frames) / fps, 2), **summarize(iv, fps)})
    return {"video": video, "segments": out}


def compare(original, remaster, tolerance=0.03):
    """Compare two `measure` results segment by segment (same names): duration and median step."""
    rem = {s["name"]: s for s in remaster["segments"]}
    rows, ok = [], True
    for s in original["segments"]:
        r = rem.get(s["name"])
        if not r:
            rows.append({"name": s["name"], "missing": True})
            ok = False
            continue
        d = (r["duration_s"] - s["duration_s"]) / s["duration_s"] if s["duration_s"] else 0
        m = ((r.get("median_ms", 0) - s.get("median_ms", 0)) / s["median_ms"]) if s.get("median_ms") else 0
        good = abs(d) <= tolerance and abs(m) <= max(tolerance, s.get("resolution_ms", 0) / max(1, s.get("median_ms", 1)))
        ok &= good
        rows.append({"name": s["name"], "duration_delta": round(d, 3), "step_delta": round(m, 3), "ok": bool(good)})
    return {"ok": bool(ok), "tolerance": tolerance, "segments": rows}
