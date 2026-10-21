"""Image utilities: quality metrics, colour lock to the original, comparisons, contact sheets."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def to_f(img):
    return np.asarray(img.convert("RGB"), dtype=np.float64) / 255.0


def srgb_to_lab(rgb):
    """rgb: float array in [0,1] (..., 3) -> CIE Lab (D65)."""
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def mean_delta_e(img_a, img_b):
    """Mean CIE76 ΔE between two images of the same size."""
    return float(np.mean(np.linalg.norm(srgb_to_lab(to_f(img_a)) - srgb_to_lab(to_f(img_b)), axis=-1)))


def ssim(img_a, img_b, win=8):
    """Block SSIM on luminance (no SciPy needed)."""
    a = np.asarray(img_a.convert("L"), dtype=np.float64)
    b = np.asarray(img_b.convert("L"), dtype=np.float64)
    h, w = a.shape
    h, w = h - h % win, w - w % win
    if h == 0 or w == 0:
        return 1.0
    a = a[:h, :w].reshape(h // win, win, w // win, win)
    b = b[:h, :w].reshape(h // win, win, w // win, win)
    ma, mb = a.mean(axis=(1, 3)), b.mean(axis=(1, 3))
    va, vb = a.var(axis=(1, 3)), b.var(axis=(1, 3))
    cov = ((a - ma[:, None, :, None]) * (b - mb[:, None, :, None])).mean(axis=(1, 3))
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    s = ((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma ** 2 + mb ** 2 + c1) * (va + vb + c2))
    return float(s.mean())


def color_lock(hd: Image.Image, original: Image.Image, radius=2.0, strength=1.0) -> Image.Image:
    """Bring the low-frequency colours of an HD image back to the original's.

    The HD image is reduced to the original size, the difference to the original is
    blurred (only broad tints, no detail) and added back at full size.
    """
    hd = hd.convert("RGB")
    W, H = hd.size
    small = hd.resize(original.size, Image.BOX)
    diff = to_f(original) - to_f(small)
    # blur each channel of the signed difference via an offset image
    off = Image.fromarray(np.clip((diff * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8), "RGB")
    off = off.filter(ImageFilter.GaussianBlur(radius)).resize((W, H), Image.BICUBIC)
    corr = (to_f(off) - 0.5) * 2.0
    out = np.clip(to_f(hd) + strength * corr, 0, 1)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGB")


def side_by_side(original: Image.Image, hd: Image.Image, label_a="Originale", label_b="Rimasterizzato"):
    W, H = hd.size
    orig = original.convert("RGB").resize((W, H), Image.NEAREST)
    canvas = Image.new("RGB", (W * 2 + 16, H + 36), (24, 24, 24))
    canvas.paste(orig, (0, 36))
    canvas.paste(hd.convert("RGB"), (W + 16, 36))
    d = ImageDraw.Draw(canvas)
    d.text((8, 10), label_a, fill=(230, 230, 230))
    d.text((W + 24, 10), label_b, fill=(230, 230, 230))
    return canvas


def contact_sheet(images, cols=4, thumb=320, labels=None):
    if not images:
        return Image.new("RGB", (thumb, thumb), (24, 24, 24))
    rows = (len(images) + cols - 1) // cols
    th = thumb * 3 // 4
    sheet = Image.new("RGB", (cols * thumb, rows * (th + 18)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(images):
        t = im.convert("RGB").copy()
        t.thumbnail((thumb, th), Image.NEAREST)
        x, y = (i % cols) * thumb, (i // cols) * (th + 18)
        sheet.paste(t, (x, y))
        if labels:
            d.text((x + 4, y + th + 3), str(labels[i])[:40], fill=(220, 220, 220))
    return sheet
