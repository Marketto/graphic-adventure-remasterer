"""Tests of the upscaler backends (tiled inference, model choice), the deterministic sprite
pipeline and the cutscene tools. Synthetic, invented data only: torch is not required (a fake
model stands in for it; the real-model test runs only with REMASTER_TEST_MODEL set)."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from remaster_tools import gfx, rawframe, scalers, video, widescreen  # noqa: E402
from test_pipeline import dump, RSTOOL  # noqa: E402,F401  (fixture with invented scenes)

need_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg assente")


@pytest.fixture(autouse=True)
def no_models(monkeypatch):
    """Tests never depend on the models or binaries of the machine they run on."""
    for env in scalers.MODEL_ENV.values():
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(scalers, "realesrgan_binary", lambda: None)


# ------------------------------------------------------------------ backends
def _local_op(a):
    """A stand-in model: 3x3 mean (edge padded) then nearest 2x. Reach of one pixel."""
    p = np.pad(a, ((1, 1), (1, 1), (0, 0)), mode="edge")
    h, w = a.shape[:2]
    m = sum(p[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)) / 9.0
    return np.repeat(np.repeat(m, 2, 0), 2, 1)


def test_tiled_apply_matches_whole_image():
    rng = np.random.default_rng(3)
    a = rng.random((53, 71, 3)).astype(np.float32)
    calls = []

    def fn(t):
        calls.append(t.shape)
        return _local_op(t)
    tiled = scalers.tiled_apply(a, fn, 2, tile=16, overlap=4)
    assert tiled.shape == (106, 142, 3)
    assert np.allclose(tiled, _local_op(a), atol=1e-6)
    assert max(s[0] for s in calls) <= 16 + 8 and len(calls) == 4 * 5  # bounded tiles
    with pytest.raises(ValueError):
        scalers.tiled_apply(a, lambda t: t, 2, tile=16, overlap=4)  # wrong scale from the model


def test_backend_choice_and_env(monkeypatch):
    assert scalers.choose_backend("bg") == ("scale", None)
    monkeypatch.setenv("REMASTER_MODEL_SPR", "/modelli/finto_GRL.pth")
    monkeypatch.setattr(scalers, "torch_status", lambda: {"torch": False, "spandrel": False, "spandrel_ready": False})
    assert scalers.model_for("spr") == "/modelli/finto_GRL.pth" and scalers.model_for("bg") is None
    with pytest.raises(RuntimeError, match="spandrel"):  # configured model: never a silent fallback
        scalers.choose_backend("spr")
    assert scalers.choose_backend("bg")[0] == "scale"
    monkeypatch.setattr(scalers, "torch_status", lambda: {"torch": True, "spandrel": True, "spandrel_ready": True})
    assert scalers.choose_backend("spr") == ("spandrel", "/modelli/finto_GRL.pth")
    assert scalers.choose_backend("bg", model="/altro/RRDB.safetensors") == ("spandrel", "/altro/RRDB.safetensors")
    with pytest.raises(RuntimeError):
        scalers.choose_backend("bg", prefer="spandrel")
    rep = gfx.backends()
    assert rep["models"]["spr"]["model"] == "/modelli/finto_GRL.pth" and rep["models"]["spr"]["backend"] == "spandrel"
    assert rep["models"]["bg"]["backend"] == "scale" and "ffmpeg" in rep


class FakeNet:
    """Stand-in for SpandrelModel: 4x nearest, records what it was given."""
    name, scale = "finto.pth", 4

    def __init__(self):
        self.inputs = []

    def __call__(self, img):
        self.inputs.append(np.asarray(img).copy())
        return img.resize((img.width * 4, img.height * 4), Image.NEAREST)


def use_fake(monkeypatch, net):
    monkeypatch.setattr(scalers, "torch_status", lambda: {"torch": True, "spandrel": True, "spandrel_ready": True})
    monkeypatch.setattr(scalers, "load_model", lambda path, **kw: net)


def test_upscale_rgb_uses_model_and_reduction(monkeypatch):
    net = FakeNet()
    use_fake(monkeypatch, net)
    img = Image.fromarray(np.random.default_rng(1).integers(0, 255, (10, 12, 3), dtype=np.uint8))
    big, used = scalers.upscale_rgb_info(img, 3, model="/m/finto.pth")
    assert big.size == (36, 30) and used == "spandrel:finto.pth" and len(net.inputs) == 1


@pytest.mark.skipif(not os.environ.get("REMASTER_TEST_MODEL"), reason="REMASTER_TEST_MODEL non impostata")
def test_real_spandrel_model():
    pytest.importorskip("torch")
    pytest.importorskip("spandrel")
    img = Image.new("RGB", (40, 30), (70, 130, 220))
    a, used = scalers.upscale_rgb_info(img, 3, model=os.environ["REMASTER_TEST_MODEL"])
    b = scalers.upscale_rgb(img, 3, model=os.environ["REMASTER_TEST_MODEL"])
    assert a.size == (120, 90) and used.startswith("spandrel:") and np.array_equal(np.asarray(a), np.asarray(b))


# ------------------------------------------------------------------ sprites
def sprite(outline=True, key_rgb=(0, 0, 0)):
    """Invented figure: light disc and a diagonal flank, optional 1 px dark outline."""
    pal = np.zeros((256, 3), np.uint8)
    pal[0] = key_rgb             # transparent key
    pal[1] = (16, 12, 20)        # ink
    pal[2] = (230, 120, 60)      # body
    pal[3] = (250, 220, 180)     # face
    h, w = 32, 28
    yy, xx = np.mgrid[0:h, 0:w]
    px = np.zeros((h, w), np.uint8)
    px[(yy >= 12) & (xx >= 4) & (xx <= 23) & (yy - 12 >= (xx - 14) // 2)] = 2   # body with a slanted top
    px[(yy - 8) ** 2 + (xx - 14) ** 2 <= 30] = 3                                # head
    if outline:
        m = px != 0
        p = np.pad(m, 1)
        inner = m & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
        px[m & ~inner] = 1
    return rawframe.RawFrame(w, h, 0, pal.tobytes(), px)


def test_sprite_alpha_is_smooth():
    pal = np.zeros((256, 3), np.uint8)
    pal[2] = (230, 120, 60)
    yy, xx = np.mgrid[0:24, 0:24]
    px = np.where((xx >= yy) & (yy >= 2) & (xx <= 21), 2, 0).astype(np.uint8)  # 45-degree staircase
    fr = rawframe.RawFrame(24, 24, 0, pal.tobytes(), px)
    img, used = gfx.remaster_sprite(fr, 3)
    a = np.asarray(img)[..., 3].astype(int)
    assert used == "scale" and img.size == (72, 72)
    assert ((a > 0) & (a < 255)).sum() > 50           # antialiased edge
    cols = range(24, 48)                              # middle of the diagonal, HD columns
    edge = np.array([np.where(a[:, x] >= 128)[0].max() for x in cols])
    fit = np.polyval(np.polyfit(list(cols), edge, 1), list(cols))
    assert np.abs(edge - fit).max() <= 1.0            # a straight line at HD...
    near = np.kron(px != 0, np.ones((3, 3), int))
    stairs = np.array([np.where(near[:, x])[0].max() for x in cols])
    assert np.abs(stairs - np.polyval(np.polyfit(list(cols), stairs, 1), list(cols))).max() > 1.0  # ...not stairs
    assert np.array_equal(a[:, 0], np.zeros(72)) and a[30, 50] == 255


def test_sprite_dark_outline_preserved_and_measured():
    fr = sprite(outline=True)
    rgb1 = np.frombuffer(fr.palette, np.uint8).reshape(256, 3)[fr.pixels].astype(float)
    ink_b, thick = gfx.outline_analysis(rgb1, fr.pixels != 0)
    assert ink_b.sum() > 20 and 0.9 <= thick <= 1.2
    img, _ = gfx.remaster_sprite(fr, 3)
    a = np.asarray(img).astype(int)
    lum = a[..., :3] @ np.array([0.299, 0.587, 0.114])
    # along the row through the head: edge -> ink band (about 3 HD px) -> face colour inside
    row = 8 * 3 + 1
    opaque = np.where(a[row, :, 3] >= 128)[0]
    left = opaque[0]
    assert lum[row, left] < 60 and lum[row, left + 1] < 60
    assert lum[row, left + 6] > 180
    no_ink, _ = gfx.remaster_sprite(fr, 3, ink=False)
    assert not np.array_equal(np.asarray(no_ink), np.asarray(img))


def test_sprite_deterministic():
    fr = sprite()
    a = np.asarray(gfx.remaster_sprite(fr, 3)[0])
    b = np.asarray(gfx.remaster_sprite(fr, 3)[0])
    assert np.array_equal(a, b)


def test_sprite_no_dark_fringe_and_key_never_reaches_model(monkeypatch):
    net = FakeNet()
    use_fake(monkeypatch, net)
    fr = sprite(outline=False, key_rgb=(0, 0, 0))   # black key: the classic source of fringes
    img, used = gfx.remaster_sprite(fr, 3, model="/m/finto_GRL.pth")
    assert used == "spandrel:finto.pth"
    seen = net.inputs[0].reshape(-1, 3)
    assert not (seen.sum(1) == 0).any()             # transparent key colour filled before the model
    a = np.asarray(img).astype(int)
    out = a[..., 3] < 255
    lum = a[..., :3] @ np.array([0.299, 0.587, 0.114])
    assert lum[out].min() > 100                      # outside colours are the edge colours, not black
    jpg = np.asarray(img.convert("RGB")).astype(int)  # what a JPEG keeps: no alpha, colours only
    assert (jpg.sum(2) > 0).all()


def test_fill_outside_spreads_edge_colours():
    rgb = np.zeros((20, 20, 3))
    known = np.zeros((20, 20), bool)
    known[8:12, 8:12] = True
    rgb[known] = (200, 100, 50)
    out = gfx.fill_outside(rgb, known)
    assert np.allclose(out, (200, 100, 50))


def test_batch_sprites_jpg_and_no_ink(dump, tmp_path):
    res = gfx.batch_sprites(str(dump / "dump" / "spr"), str(tmp_path / "spr"), scale=3, ink=False, fmt="jpg")
    assert res["sprites"] == 3 and res["indexed"] == 3 and res["backends"] == {"scale": 3}
    jpgs = [f for f in os.listdir(tmp_path / "spr") if f.endswith(".jpg")]
    assert len(jpgs) == 3 and Image.open(tmp_path / "spr" / jpgs[0]).mode == "RGB"


# ------------------------------------------------------------------ backgrounds and bands
def test_backgrounds_resume_and_model_in_meta(dump, tmp_path, monkeypatch):
    src, dst = str(dump / "dump" / "bg"), str(tmp_path / "hd")
    first = gfx.batch_backgrounds(src, dst, scale=2, use_ai=False)
    again = gfx.batch_backgrounds(src, dst, scale=2, use_ai=False)
    assert not any(r.get("skipped") for r in first) and all(r.get("skipped") for r in again)
    net = FakeNet()
    use_fake(monkeypatch, net)
    redo = gfx.batch_backgrounds(src, dst, scale=2, use_ai=False, model="/m/finto.pth")
    assert not any(r.get("skipped") for r in redo) and redo[0]["backend"] == "spandrel:finto.pth"
    assert json.load(open(os.path.join(dst, "aperta.png.json")))["model"] == "finto.pth"


def test_band_upscaler_is_the_background_model(dump, tmp_path, monkeypatch):
    from test_rifiniture import fake_lama
    bgdir = str(dump / "dump" / "bg")
    gfx.batch_backgrounds(bgdir, str(tmp_path / "hd"), scale=3, use_ai=False)
    plan = str(tmp_path / "plan.json")
    widescreen.classify(bgdir, 320, 200, 1.0, plan)
    seen = []
    real = scalers.upscale_rgb

    def spy(im, k, prefer="auto", model=None, kind="bg"):
        seen.append((model, kind))
        return real(im, k, prefer, None, kind)
    monkeypatch.setattr(scalers, "upscale_rgb", spy)
    widescreen.make_extensions(plan, str(tmp_path / "hd"), str(tmp_path / "var"), 3, lama=fake_lama,
                               quilting=False, only=["aperta"], model="/m/APISR_RRDB.pth")
    assert seen and set(seen) == {("/m/APISR_RRDB.pth", "bg")}


# ------------------------------------------------------------------ cutscenes
def make_clip(path, size="32x24", rate=10):
    """1 s of moving test pattern + 1 s of a still colour, with a tone."""
    subprocess.run(["ffmpeg", "-v", "error", "-y",
                    "-f", "lavfi", "-i", f"testsrc=size={size}:rate={rate}:duration=1",
                    "-f", "lavfi", "-i", f"color=c=0x406080:s={size}:r={rate}:d=1",
                    "-f", "lavfi", "-i", "sine=frequency=330:duration=2",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
                    "-c:v", "ffv1", "-c:a", "pcm_s16le", str(path)], check=True)


@need_ffmpeg
def test_video_probe_upscale_reuse_and_resume(tmp_path):
    clip = tmp_path / "clip.avi"
    make_clip(clip)
    info = video.probe(str(clip))
    assert info["video"]["width"] == 32 and info["video"]["fps"] == 10.0 and info["video"]["frames"] == 20
    assert info["audio"][0]["codec"] == "pcm_s16le"
    out = tmp_path / "clip_hd.mkv"
    res = video.upscale(str(clip), str(out), scale=3)
    assert res["frames"] == 20 and res["unique"] == 11 and res["computed"] == 11 and res["audio_copied"]
    hd = video.probe(str(out))
    assert hd["video"]["width"] == 96 and hd["video"]["height"] == 72 and hd["video"]["codec"] == "h264"
    assert hd["video"]["fps"] == 10.0 and hd["video"]["frames"] == 20 and hd["audio"]
    assert abs(hd["duration"] - info["duration"]) < 0.15
    again = video.upscale(str(clip), str(out), scale=3)
    assert again["computed"] == 0 and again["reused"] == 20   # resumable: nothing recomputed
    # frames are upscaled deterministically (Scale3x of the extracted frame)
    f1 = Image.open(tmp_path / "clip_hd.work" / "in" / "000001.png").convert("RGB")
    h1 = video.frame_hash(f1)
    assert np.array_equal(np.asarray(Image.open(tmp_path / "clip_hd.work" / "hd" / f"{h1}.png")),
                          np.asarray(scalers.upscale_rgb(f1, 3)))


@need_ffmpeg
def test_video_from_png_folder_and_theora(tmp_path):
    frames = tmp_path / "dump"
    frames.mkdir()
    for i in range(6):
        im = np.full((20, 30, 3), 40 * (i // 2), np.uint8)   # pairs of identical frames
        Image.fromarray(im).save(frames / f"{i:04d}.png")
    with pytest.raises(ValueError):
        video.upscale(str(frames), str(tmp_path / "x.mkv"))     # fps is required for a folder
    calls = []

    def fake(im, k):
        calls.append(1)
        return im.resize((im.width * k, im.height * k), Image.NEAREST)
    res = video.upscale(str(frames), str(tmp_path / "x.ogv"), scale=2, fps="12", upscale_fn=fake)
    assert res["frames"] == 6 and len(calls) == 3
    v = video.probe(str(tmp_path / "x.ogv"))["video"]
    assert v["codec"] == "theora" and v["width"] == 60 and v["fps"] == 12.0


@need_ffmpeg
def test_video_cli(tmp_path):
    clip = tmp_path / "c.avi"
    make_clip(clip, size="16x12")

    def run(*args, ok=True):
        r = subprocess.run([sys.executable, RSTOOL, *args], capture_output=True, text=True)
        assert (r.returncode == 0) == ok, r.stderr
        return r
    assert json.loads(run("video", "probe", str(clip)).stdout)["video"]["height"] == 12
    res = json.loads(run("video", "upscale", str(clip), "--out", str(tmp_path / "c.mp4"), "--scale", "2",
                         "--max-frames", "5", "--pix-fmt", "yuv420p").stdout)
    assert res["frames"] == 5 and video.probe(str(tmp_path / "c.mp4"))["video"]["width"] == 32
    r = run("video", "upscale", str(clip), "--out", str(tmp_path / "d.mkv"), "--interpolate", ok=False)
    assert "RIFE" in r.stderr
    assert json.loads(run("gfx", "backends").stdout)["cpu_scalers"] is True


def test_example_recipe_matches_loader_and_comfy():
    from remaster_tools import comfy
    path = os.path.join(os.path.dirname(os.path.dirname(HERE)), "references", "style-recipes.example.json")
    for cat in ("background", "background_extension", "sprite"):
        r = gfx.load_recipe(path, cat)
        wf, _model, _pos = comfy._base(r, "x.png", 1)
        assert wf["ckpt"]["inputs"]["ckpt_name"] == r["checkpoint"] and "prompt" in r
    assert gfx.load_recipe(path, "background")["color_lock_radius"] > 0
