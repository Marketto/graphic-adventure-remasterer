"""Deterministic pixel-art scalers (no GPU, bit-identical everywhere).

Scale2x / Scale3x (AdvanceMAME) on palette indices, like the Remaster Layer fallback,
plus helpers to call Real-ESRGAN (ncnn-vulkan build) when installed.
"""
import os
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image


def _neighbours(a):
    p = np.pad(a, 1, mode="edge")
    A, B, C = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    D, E, F = p[1:-1, :-2], p[1:-1, 1:-1], p[1:-1, 2:]
    G, H, I = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    return A, B, C, D, E, F, G, H, I


def scale2x(idx: np.ndarray) -> np.ndarray:
    A, B, C, D, E, F, G, H, I = _neighbours(idx)
    cond = (B != H) & (D != F)
    e0 = np.where(cond & (D == B), D, E)
    e1 = np.where(cond & (B == F), F, E)
    e2 = np.where(cond & (D == H), D, E)
    e3 = np.where(cond & (H == F), F, E)
    h, w = idx.shape
    out = np.empty((h * 2, w * 2), dtype=idx.dtype)
    out[0::2, 0::2], out[0::2, 1::2], out[1::2, 0::2], out[1::2, 1::2] = e0, e1, e2, e3
    return out


def scale3x(idx: np.ndarray) -> np.ndarray:
    A, B, C, D, E, F, G, H, I = _neighbours(idx)
    c = (B != H) & (D != F)
    e = [None] * 9
    e[0] = np.where(c & (D == B), D, E)
    e[1] = np.where(c & (((D == B) & (E != C)) | ((B == F) & (E != A))), B, E)
    e[2] = np.where(c & (B == F), F, E)
    e[3] = np.where(c & (((D == B) & (E != G)) | ((D == H) & (E != A))), D, E)
    e[4] = E
    e[5] = np.where(c & (((B == F) & (E != I)) | ((H == F) & (E != C))), F, E)
    e[6] = np.where(c & (D == H), D, E)
    e[7] = np.where(c & (((D == H) & (E != I)) | ((H == F) & (E != G))), H, E)
    e[8] = np.where(c & (H == F), F, E)
    h, w = idx.shape
    out = np.empty((h * 3, w * 3), dtype=idx.dtype)
    for k in range(9):
        out[k // 3::3, k % 3::3] = e[k]
    return out


def scale_indexed(idx: np.ndarray, factor: int) -> np.ndarray:
    if factor == 1:
        return idx.copy()
    if factor == 2:
        return scale2x(idx)
    if factor == 3:
        return scale3x(idx)
    if factor == 4:
        return scale2x(scale2x(idx))
    if factor == 6:
        return scale2x(scale3x(idx))
    raise ValueError("factor must be 1, 2, 3, 4 or 6")


def realesrgan_binary():
    return shutil.which("realesrgan-ncnn-vulkan")


def realesrgan(img: Image.Image, model="realesrgan-x4plus-anime", scale=4) -> Image.Image:
    exe = realesrgan_binary()
    if not exe:
        raise RuntimeError("realesrgan-ncnn-vulkan non trovato nel PATH")
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in.png"), os.path.join(d, "out.png")
        img.convert("RGB").save(src)
        subprocess.run([exe, "-i", src, "-o", dst, "-n", model, "-s", str(scale)],
                       check=True, capture_output=True)
        return Image.open(dst).convert("RGB")


def upscale_rgb(img: Image.Image, factor: int, prefer="realesrgan") -> Image.Image:
    """Best available upscale of an RGB image to an integer factor."""
    w, h = img.size
    if prefer == "realesrgan" and realesrgan_binary():
        big = realesrgan(img, scale=4)
        return big.resize((w * factor, h * factor), Image.LANCZOS)
    # deterministic fallback: quantize to <=256 colours, Scale2x/3x on indices
    pal_img = img.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    idx = np.array(pal_img)
    pal = np.array(pal_img.getpalette()[:768], dtype=np.uint8).reshape(-1, 3)
    if factor in (1, 2, 3, 4, 6):
        up = scale_indexed(idx, factor)
        return Image.fromarray(pal[up], "RGB")
    return img.resize((w * factor, h * factor), Image.NEAREST)
