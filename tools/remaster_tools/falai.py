"""OPTIONAL paid outpainting of the 16:9 bands with FLUX.1 Fill pro on fal.ai (masked
outpainting: the centre is not repainted). Used only if the user said yes in the interview
(`widescreen.fal_ai`) AND approved a quote for this batch: `fill_function` refuses otherwise.

Lessons of the reference project: canvas at 1.5x the original (enough for narrow bands, half
the price of HD), `sync_mode` (images not kept in the service history), at most 2 attempts per
scene then the local method, edit-the-whole-image models rejected (they move the framing).
"""
import base64
import io
import json
import os
import urllib.request

import numpy as np
from PIL import Image

ENDPOINT = "https://fal.run/fal-ai/flux-pro/v1/fill"
PRICE_USD = 0.05  # per image, indicative: check the current price before quoting
PROMPT = ("Extend this hand-painted background of a 1990s point-and-click adventure game into the "
          "masked side areas. Finished, fully coloured painting with the same palette, brushwork, "
          "lighting and perspective; continue walls, floors, sky and objects cut by the border. "
          "Not a sketch, not line art, no white paper, no people, no text, no signature, no logos.")
DARK = " The scene is dark: keep the extended areas equally dark and painted, no light paper."


def estimate(scenes, attempts=2, price=PRICE_USD, accept_first=0.65):
    """Quote: worst case (every scene uses all attempts) and the likely case seen on the
    reference project (~2/3 accepted at the first attempt)."""
    worst = scenes * attempts
    likely = scenes * (accept_first + (1 - accept_first) * attempts)
    return {"scenes": scenes, "max_images": worst, "max_usd": round(worst * price, 2),
            "likely_images": int(round(likely)), "likely_usd": round(likely * price, 2),
            "price_per_image_usd": price,
            "note": "prezzo indicativo: verificalo sul sito prima di chiedere l'approvazione"}


def _data_uri(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _post(payload, key, timeout=180):
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Key {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _fetch_image(url):
    if url.startswith("data:"):
        return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")
    with urllib.request.urlopen(url, timeout=120) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


class Budget:
    """Counts paid calls against the approved number of images; never retries on its own."""

    def __init__(self, approved_images, log_path=None):
        self.approved = int(approved_images)
        self.used = 0
        self.log_path = log_path

    def take(self, what):
        if self.used >= self.approved:
            raise RuntimeError(f"budget approvato esaurito ({self.approved} immagini): chiedi una nuova approvazione")
        self.used += 1
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"image": self.used, "what": what}) + "\n")


def fill_function(budget, key=None, canvas_scale=1.5, poster=None, seed=None):
    """A `fill(img, mask)` like LaMa's, for extend_inpaint: sends the 1x picture with its mask
    (scaled to `canvas_scale`) and returns the painted picture at 1x. Each call costs one image."""
    key = key or os.environ.get("FAL_KEY")
    if poster is None and not key:
        raise RuntimeError("FAL_KEY mancante")
    if not isinstance(budget, Budget) or budget.approved <= 0:
        raise RuntimeError("fal.ai solo con un budget approvato dall'utente (preventivo prima)")
    post = poster or (lambda payload: _post(payload, key))

    def fill(img, mask):
        h, w = img.shape[:2]
        W, H = int(round(w * canvas_scale)), int(round(h * canvas_scale))
        im = Image.fromarray(img).resize((W, H), Image.LANCZOS)
        mk = Image.fromarray((mask > 0).astype(np.uint8) * 255).resize((W, H), Image.NEAREST)
        known = np.asarray(im.convert("L"))[np.asarray(mk) == 0]
        lum = float(known.mean()) if known.size else 128.0
        prompt = PROMPT + (DARK if lum < 45 else "")
        budget.take(f"{w}x{h}")
        payload = {"prompt": prompt, "image_url": _data_uri(im), "mask_url": _data_uri(mk),
                   "sync_mode": True, "output_format": "png", "safety_tolerance": "2"}
        if seed is not None:
            payload["seed"] = seed
        res = post(payload)
        out = _fetch_image(res["images"][0]["url"]).resize((w, h), Image.LANCZOS)
        return np.asarray(out, np.uint8)
    return fill
