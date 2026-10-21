"""Minimal ComfyUI client (local GPU) for style-preserving img2img and outpainting.

Only core ComfyUI nodes are used, so a stock install with the chosen checkpoint, the
game's style LoRA and a tile ControlNet is enough. Server: env COMFYUI_URL or
http://127.0.0.1:8188.
"""
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PIL import Image

URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")


def available(url=URL, timeout=2):
    try:
        with urllib.request.urlopen(url + "/system_stats", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _post(path, payload, url=URL):
    req = urllib.request.Request(url + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def upload(img: Image.Image, name: str, url=URL):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            "Content-Type: image/png\r\n\r\n").encode() + buf.getvalue() + \
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url + "/upload/image", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["name"]


def run(workflow, url=URL, poll=1.0, timeout=900):
    pid = _post("/prompt", {"prompt": workflow, "client_id": uuid.uuid4().hex}, url)["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        with urllib.request.urlopen(f"{url}/history/{pid}", timeout=30) as r:
            hist = json.loads(r.read())
        if pid in hist:
            outs = []
            for node in hist[pid]["outputs"].values():
                for im in node.get("images", []):
                    q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im["subfolder"], "type": im["type"]})
                    with urllib.request.urlopen(f"{url}/view?{q}", timeout=60) as r:
                        outs.append(Image.open(io.BytesIO(r.read())).convert("RGB"))
            return outs
        time.sleep(poll)
    raise TimeoutError("ComfyUI non ha finito in tempo")


def _base(recipe, image_name, seed):
    r = recipe
    wf = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": r["checkpoint"]}},
        "img": {"class_type": "LoadImage", "inputs": {"image": image_name}},
    }
    model, clip = ["ckpt", 0], ["ckpt", 1]
    if r.get("lora"):
        wf["lora"] = {"class_type": "LoraLoader", "inputs": {
            "model": model, "clip": clip, "lora_name": r["lora"],
            "strength_model": r.get("lora_strength", 0.8), "strength_clip": r.get("lora_strength", 0.8)}}
        model, clip = ["lora", 0], ["lora", 1]
    wf["pos"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": r["prompt"]}}
    wf["neg"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": r.get("negative", "")}}
    pos = ["pos", 0]
    if r.get("controlnet"):
        wf["cn"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": r["controlnet"]}}
        wf["cnapply"] = {"class_type": "ControlNetApply", "inputs": {
            "conditioning": pos, "control_net": ["cn", 0], "image": ["img", 0],
            "strength": r.get("controlnet_strength", 0.7)}}
        pos = ["cnapply", 0]
    return wf, model, pos


def img2img(img: Image.Image, recipe: dict, seed: int, url=URL) -> Image.Image:
    name = upload(img, f"rs_{uuid.uuid4().hex[:8]}.png", url)
    wf, model, pos = _base(recipe, name, seed)
    wf["enc"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["img", 0], "vae": ["ckpt", 2]}}
    wf["ks"] = {"class_type": "KSampler", "inputs": {
        "model": model, "positive": pos, "negative": ["neg", 0], "latent_image": ["enc", 0],
        "seed": seed, "steps": recipe.get("steps", 28), "cfg": recipe.get("cfg", 5.5),
        "sampler_name": recipe.get("sampler", "dpmpp_2m"), "scheduler": recipe.get("scheduler", "karras"),
        "denoise": recipe.get("denoise", 0.25)}}
    wf["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["ckpt", 2]}}
    wf["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": "remaster"}}
    return run(wf, url)[0]


def outpaint(img: Image.Image, left: int, right: int, recipe: dict, seed: int, url=URL) -> Image.Image:
    name = upload(img, f"rs_{uuid.uuid4().hex[:8]}.png", url)
    wf, model, pos = _base(recipe, name, seed)
    wf.pop("cnapply", None)
    wf.pop("cn", None)
    pos = ["pos", 0]
    wf["pad"] = {"class_type": "ImagePadForOutpaint", "inputs": {
        "image": ["img", 0], "left": left, "top": 0, "right": right, "bottom": 0,
        "feathering": recipe.get("feathering", 24)}}
    wf["enc"] = {"class_type": "VAEEncodeForInpaint", "inputs": {
        "pixels": ["pad", 0], "vae": ["ckpt", 2], "mask": ["pad", 1], "grow_mask_by": 8}}
    wf["ks"] = {"class_type": "KSampler", "inputs": {
        "model": model, "positive": pos, "negative": ["neg", 0], "latent_image": ["enc", 0],
        "seed": seed, "steps": recipe.get("steps", 32), "cfg": recipe.get("cfg", 6.0),
        "sampler_name": recipe.get("sampler", "dpmpp_2m"), "scheduler": recipe.get("scheduler", "karras"),
        "denoise": 1.0}}
    wf["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["ckpt", 2]}}
    wf["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": "remaster_wide"}}
    return run(wf, url)[0]
