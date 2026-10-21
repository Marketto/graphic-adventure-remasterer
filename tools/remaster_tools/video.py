"""Cutscenes and FMV: probe, deterministic per-frame upscale, re-encode to a modern file.

Many period formats (Smacker, FLIC, early AVI/QuickTime codecs...) are read by ffmpeg. For the
others the engine dumps the decoded frames as PNG (remaster_dump): pass that folder and the fps.

Flow of `upscale`:
  1. frames extracted 1:1 with ffmpeg (no frame dropped or duplicated) as RGB PNG;
  2. every distinct frame upscaled ONCE with the same backend as the backgrounds (spandrel model,
     Real-ESRGAN ncnn or Scale2x/3x): identical frames (static shots, holds) are recognised by
     the hash of their pixels and reused, so they are neither recomputed nor allowed to flicker;
  3. re-encoded at the original fps (MKV/MP4 H.264 at low CRF, or Ogg Theora) with the original
     audio copied when the container accepts it (otherwise lossless FLAC, or AAC/Vorbis).
The work folder keeps the upscaled frames by hash, so an interrupted run resumes where it stopped.
Frame interpolation (RIFE) is deliberately absent: it changes the animator's timing and must be
proposed on a sample and approved first (see skills/hd-graphics).
"""
import hashlib
import json
import os
import shutil
import subprocess
from fractions import Fraction

import numpy as np
from PIL import Image

from . import scalers

# audio codecs each container takes as they are (stream copy); otherwise re-encode
COPY_OK = {
    "mkv": {"aac", "mp3", "mp2", "ac3", "flac", "vorbis", "opus", "alac"} | {"pcm_s16le", "pcm_s24le", "pcm_u8",
                                                                          "pcm_s16be", "pcm_f32le"},
    "mp4": {"aac", "mp3", "alac", "ac3"},
    "ogv": {"vorbis"},
}
REENCODE = {"mkv": ["-c:a", "flac"], "mp4": ["-c:a", "aac", "-b:a", "192k"], "ogv": ["-c:a", "libvorbis", "-q:a", "6"]}
US_PER_PIXEL_CPU = 80  # APISR RRDB/GRL on a 2-core CPU, measured per input pixel (references/conoscenza/grafica.md)


def _need(tool):
    exe = shutil.which(tool)
    if not exe:
        raise RuntimeError(f"{tool} non trovato nel PATH (installa ffmpeg)")
    return exe


def _rate(s):
    try:
        f = Fraction(s)
        return f if f > 0 else None
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def probe(path):
    """Format, resolution, fps, duration, frame count and audio of a video file (ffprobe)."""
    res = subprocess.run([_need("ffprobe"), "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", path], check=True, capture_output=True, text=True)
    info = json.loads(res.stdout)
    fmt = info.get("format", {})
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = [{"codec": s.get("codec_name"), "sample_rate": int(s.get("sample_rate", 0) or 0),
              "channels": s.get("channels"), "index": s.get("index")}
             for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    out = {"file": path, "format": fmt.get("format_name"), "duration": float(fmt.get("duration", 0) or 0),
           "video": None, "audio": audio}
    if v:
        fps = _rate(v.get("r_frame_rate")) or _rate(v.get("avg_frame_rate"))
        frames = int(v.get("nb_frames") or 0) or (int(round(out["duration"] * fps)) if fps else 0)
        out["video"] = {"codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"),
                        "pix_fmt": v.get("pix_fmt"), "fps": float(fps) if fps else None,
                        "fps_fraction": str(fps) if fps else None, "frames": frames}
        px = (v.get("width") or 0) * (v.get("height") or 0) * frames
        out["estimate_cpu_minutes_model"] = round(px * US_PER_PIXEL_CPU / 1e6 / 60, 1)
    return out


def extract_frames(src, dst_dir, max_frames=None):
    """All frames 1:1 (no fps conversion) as RGB PNG 000001.png, 000002.png..."""
    os.makedirs(dst_dir, exist_ok=True)
    cmd = [_need("ffmpeg"), "-v", "error", "-y", "-i", src, "-map", "0:v:0", "-fps_mode", "passthrough",
           "-pix_fmt", "rgb24"]
    if max_frames:
        cmd += ["-frames:v", str(max_frames)]
    subprocess.run(cmd + [os.path.join(dst_dir, "%06d.png")], check=True, capture_output=True)
    return sorted(f for f in os.listdir(dst_dir) if f.endswith(".png"))


def frame_hash(img: Image.Image) -> str:
    a = np.asarray(img.convert("RGB"))
    return hashlib.sha256(np.array(a.shape, np.int32).tobytes() + a.tobytes()).hexdigest()[:24]


def _link(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def upscale_frames(frames, hd_dir, seq_dir, scale, model=None, upscale=None, log=None):
    """Upscale a list of frame files; identical frames are computed once (by pixel hash) and a
    frame already in hd_dir (earlier, interrupted run) is not recomputed. Writes the numbered
    sequence in seq_dir. `upscale(img, scale) -> img` replaces the backend (tests)."""
    os.makedirs(hd_dir, exist_ok=True)
    if os.path.isdir(seq_dir):
        shutil.rmtree(seq_dir)
    os.makedirs(seq_dir)
    up = upscale or (lambda im, k: scalers.upscale_rgb_info(im, k, model=model, kind="bg"))
    stats = {"frames": 0, "unique": 0, "computed": 0, "reused": 0, "backend": None}
    seen = set()
    for i, path in enumerate(frames, 1):
        img = Image.open(path).convert("RGB")
        h = frame_hash(img)
        out = os.path.join(hd_dir, h + ".png")
        if h not in seen:
            seen.add(h)
            stats["unique"] += 1
        if os.path.exists(out):
            stats["reused"] += 1
        else:
            res = up(img, scale)
            big, used = res if isinstance(res, tuple) else (res, "custom")
            if big.size != (img.width * scale, img.height * scale):
                big = big.resize((img.width * scale, img.height * scale), Image.LANCZOS)
            big.save(out + ".tmp.png")
            os.replace(out + ".tmp.png", out)
            stats["computed"] += 1
            stats["backend"] = used
        _link(out, os.path.join(seq_dir, "%06d.png" % i))
        stats["frames"] += 1
        if log and i % 50 == 0:
            log(f"{i}/{len(frames)} fotogrammi")
    return stats


def _container(out):
    ext = os.path.splitext(out)[1].lower().lstrip(".")
    if ext in ("mkv", "mp4"):
        return ext
    if ext in ("ogv", "ogg"):
        return "ogv"
    raise ValueError("uscita: .mkv, .mp4 (H.264) oppure .ogv (Theora)")


def encode(seq_dir, out, fps, audio_src=None, audio_codec=None, crf=12, preset="slow", pix_fmt="yuv444p",
           shortest=False):
    """Numbered PNG sequence -> video at `fps` (string or number, e.g. "15" or "30000/1001")."""
    cont = _container(out)
    cmd = [_need("ffmpeg"), "-v", "error", "-y", "-framerate", str(fps), "-i", os.path.join(seq_dir, "%06d.png")]
    if audio_src:
        cmd += ["-i", audio_src, "-map", "0:v:0", "-map", "1:a:0?"]
    if cont == "ogv":
        cmd += ["-c:v", "libtheora", "-q:v", "9", "-pix_fmt", "yuv444p" if pix_fmt == "yuv444p" else "yuv420p"]
    else:
        cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", pix_fmt]
        if pix_fmt == "yuv420p":  # 4:2:0 needs even dimensions
            cmd += ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
        if cont == "mp4":
            cmd += ["-movflags", "+faststart"]
    if audio_src:
        cmd += ["-c:a", "copy"] if audio_codec in COPY_OK[cont] else REENCODE[cont]
        if shortest:  # trial on the first frames only
            cmd += ["-shortest"]
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    subprocess.run(cmd + [out], check=True, capture_output=True)
    return out


def upscale(src, out, scale=3, model=None, fps=None, audio=None, work=None, crf=12, pix_fmt="yuv444p",
            max_frames=None, keep_work=True, upscale_fn=None, log=None):
    """Video file (or folder of PNG frames + fps) -> upscaled video with the original audio.

    src     video read by ffmpeg, or a folder of numbered PNG frames dumped by the engine
    fps     required for a folder; for a file the original rate is kept (override only if wrong)
    audio   separate audio file for a folder of frames (optional)
    work    work folder (default: <out>.work), keeps frames by hash for resuming
    """
    work = work or os.path.splitext(out)[0] + ".work"
    os.makedirs(work, exist_ok=True)
    info = None
    if os.path.isdir(src):
        if not fps:
            raise ValueError("cartella di fotogrammi: serve --fps")
        frames = sorted(os.path.join(src, f) for f in os.listdir(src) if f.lower().endswith(".png"))
        if max_frames:
            frames = frames[:max_frames]
        audio_src, audio_codec = audio, None
        if audio:
            a = probe(audio)["audio"]
            audio_codec = a[0]["codec"] if a else None
    else:
        info = probe(src)
        if not info["video"]:
            raise ValueError(f"{src}: nessuna traccia video")
        fps = fps or info["video"]["fps_fraction"]
        names = extract_frames(src, os.path.join(work, "in"), max_frames)
        frames = [os.path.join(work, "in", n) for n in names]
        audio_src = audio or (src if info["audio"] else None)
        audio_codec = (probe(audio)["audio"] or [{}])[0].get("codec") if audio else \
            (info["audio"][0]["codec"] if info["audio"] else None)
    if not frames:
        raise ValueError("nessun fotogramma")
    stats = upscale_frames(frames, os.path.join(work, "hd"), os.path.join(work, "seq"), scale, model,
                           upscale_fn, log)
    encode(os.path.join(work, "seq"), out, fps, audio_src, audio_codec, crf, pix_fmt=pix_fmt,
           shortest=bool(max_frames))
    if not keep_work:
        shutil.rmtree(work, ignore_errors=True)
    res = {"out": out, "fps": str(fps), "scale": scale, **stats,
           "audio": audio_codec, "audio_copied": bool(audio_src) and audio_codec in COPY_OK[_container(out)]}
    if info:
        res["source"] = {k: info["video"][k] for k in ("codec", "width", "height")}
    return res
