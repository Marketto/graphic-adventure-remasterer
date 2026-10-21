"""Upscalers for backgrounds, sprites and video frames.

Backends, in order of preference when nothing is forced:
  spandrel   PyTorch weights (.pth/.safetensors: APISR RRDB/GRL, Real-ESRGAN...) loaded with
             `spandrel`, CPU inference in overlapping tiles (bounded memory). torch and spandrel
             are optional and imported lazily. The model comes from an explicit argument or from
             REMASTER_MODEL_BG (backgrounds, bands, video) / REMASTER_MODEL_SPR (sprites).
  realesrgan the `realesrgan-ncnn-vulkan` binary (Vulkan; also works without CUDA).
  scale      deterministic Scale2x/3x (AdvanceMAME) on palette indices, like the Remaster Layer
             fallback: bit-identical everywhere, nothing invented.
"""
import importlib.util
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


MODEL_ENV = {"bg": "REMASTER_MODEL_BG", "spr": "REMASTER_MODEL_SPR"}
WEIGHT_EXT = (".pth", ".pt", ".safetensors", ".ckpt", ".bin")
# reduction from the model scale (4x) to the target scale: LANCZOS keeps backgrounds crisp,
# BOX avoids ringing halos on sprite outlines (reference project)
RESAMPLE = {"bg": Image.LANCZOS, "spr": Image.BOX}
INSTALL_HINT = ("serve PyTorch + spandrel: pip install torch --index-url "
                "https://download.pytorch.org/whl/cpu && pip install spandrel")


def model_for(kind="bg", model=None):
    """Model chosen for a kind of asset: explicit argument, else the environment variable."""
    if model:
        return model
    return os.environ.get(MODEL_ENV.get(kind, "REMASTER_MODEL_BG")) or None


def is_weights(model):
    return bool(model) and str(model).lower().endswith(WEIGHT_EXT)


def torch_status():
    """What the spandrel backend can use, without importing torch."""
    st = {"torch": importlib.util.find_spec("torch") is not None,
          "spandrel": importlib.util.find_spec("spandrel") is not None}
    st["spandrel_ready"] = st["torch"] and st["spandrel"]
    return st


# ---------------------------------------------------------------- tiled inference
def tiled_apply(arr: np.ndarray, fn, scale: int, tile=192, overlap=16) -> np.ndarray:
    """Run `fn` (HxWxC float -> (H*scale)x(W*scale)xC) on overlapping tiles.

    Each tile is processed with `overlap` pixels of real context on every side (clipped at
    the image border) and only its core is kept, so the result matches a whole-image run for
    any operator whose reach is below `overlap`, with memory bounded by the tile size.
    Tiles are visited in a fixed order: same input -> same output."""
    h, w = arr.shape[:2]
    out = None
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            y1, x1 = min(h, y + tile), min(w, x + tile)
            py0, px0 = max(0, y - overlap), max(0, x - overlap)
            py1, px1 = min(h, y1 + overlap), min(w, x1 + overlap)
            res = np.asarray(fn(arr[py0:py1, px0:px1]))
            if res.shape[0] != (py1 - py0) * scale or res.shape[1] != (px1 - px0) * scale:
                raise ValueError(f"il modello ha restituito {res.shape[:2]}, attesi "
                                 f"{((py1 - py0) * scale, (px1 - px0) * scale)}")
            if out is None:
                out = np.zeros((h * scale, w * scale) + res.shape[2:], dtype=res.dtype)
            oy, ox = (y - py0) * scale, (x - px0) * scale
            out[y * scale:y1 * scale, x * scale:x1 * scale] = \
                res[oy:oy + (y1 - y) * scale, ox:ox + (x1 - x) * scale]
    return out


class SpandrelModel:
    """A super-resolution model loaded with spandrel, run on the CPU in tiles."""

    def __init__(self, path, tile=256, overlap=16, threads=None):
        try:
            import torch
            import spandrel
        except ImportError as e:  # optional dependency
            raise RuntimeError(f"{INSTALL_HINT} ({e})") from e
        if not os.path.isfile(path):
            raise FileNotFoundError(f"modello non trovato: {path}")
        self.torch = torch
        torch.set_num_threads(threads or int(os.environ.get("REMASTER_THREADS", 0)) or os.cpu_count() or 1)
        desc = spandrel.ModelLoader(device="cpu").load_from_file(path)
        if not isinstance(desc, spandrel.ImageModelDescriptor):
            raise ValueError(f"{path}: non è un modello di super-risoluzione")
        desc.model.eval()
        self.desc = desc
        self.path = path
        self.name = os.path.basename(path)
        self.scale = int(desc.scale)
        self.arch = getattr(getattr(desc, "architecture", None), "name", "?")
        self.tile, self.overlap = tile, overlap

    def _pad_needed(self, h, w):
        req = getattr(self.desc, "size_requirements", None)
        if req is None:
            return 0, 0
        m = max(1, getattr(req, "multiple_of", 1) or 1)
        mn = getattr(req, "minimum", 0) or 0
        ph, pw = max(mn, h), max(mn, w)
        if getattr(req, "square", False):
            ph = pw = max(ph, pw)
        ph, pw = -(-ph // m) * m, -(-pw // m) * m
        return ph - h, pw - w

    def run(self, arr: np.ndarray) -> np.ndarray:
        """float32 HxWx3 in [0,1] -> float32 (H*s)x(W*s)x3, one forward pass."""
        torch = self.torch
        h, w = arr.shape[:2]
        dh, dw = self._pad_needed(h, w)
        if dh or dw:
            arr = np.pad(arr, ((0, dh), (0, dw), (0, 0)), mode="reflect" if min(h, w) > 1 else "edge")
        t = torch.from_numpy(np.ascontiguousarray(arr.transpose(2, 0, 1)))[None]
        with torch.inference_mode():
            y = self.desc(t)[0].clamp(0, 1).permute(1, 2, 0).numpy()
        return y[:h * self.scale, :w * self.scale]

    def __call__(self, img: Image.Image) -> Image.Image:
        arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
        big = tiled_apply(arr, self.run, self.scale, self.tile, self.overlap)
        return Image.fromarray((big * 255 + 0.5).astype(np.uint8), "RGB")


_MODELS = {}


def load_model(path, **kw) -> SpandrelModel:
    """Cached: a batch loads the weights once."""
    key = (os.path.abspath(path), tuple(sorted(kw.items())))
    if key not in _MODELS:
        _MODELS[key] = SpandrelModel(path, **kw)
    return _MODELS[key]


# ---------------------------------------------------------------- Real-ESRGAN ncnn
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


# ---------------------------------------------------------------- choice
def choose_backend(kind="bg", model=None, prefer="auto"):
    """(backend, model) that upscale_rgb would use. prefer: auto | spandrel | realesrgan | scale.
    An explicit or configured weights file must work: no silent fallback to a lesser upscaler."""
    m = model_for(kind, model)
    if prefer in ("auto", "spandrel") and is_weights(m):
        if not torch_status()["spandrel_ready"]:
            raise RuntimeError(f"modello {m} richiesto ma {INSTALL_HINT}")
        return "spandrel", m
    if prefer == "spandrel":
        raise RuntimeError("backend spandrel richiesto senza modello: passa --model o imposta "
                           f"{MODEL_ENV.get(kind, 'REMASTER_MODEL_BG')}")
    if prefer in ("auto", "realesrgan") and realesrgan_binary():
        return "realesrgan", (m if m and not is_weights(m) else "realesrgan-x4plus-anime")
    return "scale", None


def upscale_rgb_info(img: Image.Image, factor: int, prefer="auto", model=None, kind="bg",
                     resample=None):
    """Upscale an RGB image to an integer factor; returns (image, backend description).
    Model outputs (4x) are reduced to the factor with LANCZOS (bg) or BOX (spr)."""
    w, h = img.size
    backend, m = choose_backend(kind, model, prefer)
    rs = resample if resample is not None else RESAMPLE.get(kind, Image.LANCZOS)
    if backend == "spandrel":
        net = load_model(m)
        big = net(img)
        if big.size != (w * factor, h * factor):
            big = big.resize((w * factor, h * factor), rs)
        return big, f"spandrel:{net.name}"
    if backend == "realesrgan":
        big = realesrgan(img, model=m, scale=4)
        return big.resize((w * factor, h * factor), rs), f"realesrgan:{m}"
    # deterministic fallback: quantize to <=256 colours, Scale2x/3x on indices
    pal_img = img.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    idx = np.array(pal_img)
    pal = np.array(pal_img.getpalette()[:768], dtype=np.uint8).reshape(-1, 3)
    if factor in (1, 2, 3, 4, 6):
        up = scale_indexed(idx, factor)
        return Image.fromarray(pal[up], "RGB"), "scale"
    return img.resize((w * factor, h * factor), Image.NEAREST), "nearest"


def upscale_rgb(img: Image.Image, factor: int, prefer="auto", model=None, kind="bg") -> Image.Image:
    """Best available upscale of an RGB image to an integer factor (see upscale_rgb_info)."""
    return upscale_rgb_info(img, factor, prefer, model, kind)[0]
