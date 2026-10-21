"""Inventory of a Remaster Layer dump (bg/, spr/, text dump, midi/), with work estimates."""
import csv
import json
import os

from . import rawframe


def inventory(dump_dir, out_csv):
    rows = []
    bg = os.path.join(dump_dir, "bg")
    spr = os.path.join(dump_dir, "spr")
    if os.path.isdir(bg):
        for name in sorted(os.listdir(bg)):
            p = os.path.join(bg, name)
            if name.endswith(".raw"):
                fr = rawframe.read_raw(p)
                rows.append({"type": "bg", "key": name[:-4], "w": fr.w, "h": fr.h, "uses": ""})
    uses = {}
    usage = os.path.join(spr, "usage.json")  # optional: {key: times drawn} from the Layer
    if os.path.exists(usage):
        with open(usage) as f:
            uses = json.load(f)
    if os.path.isdir(spr):
        for name in sorted(os.listdir(spr)):
            if name.endswith(".raw"):
                fr = rawframe.read_raw(os.path.join(spr, name))
                rows.append({"type": "spr", "key": fr.key, "w": fr.w, "h": fr.h, "uses": uses.get(fr.key, "")})
    rows.sort(key=lambda r: (r["type"], -(int(r["uses"]) if str(r["uses"]).isdigit() else 0), r["key"]))
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["type", "key", "w", "h", "uses"])
        w.writeheader()
        w.writerows(rows)
    text_lines = 0
    tdump = os.path.join(dump_dir, "text.jsonl")
    if os.path.exists(tdump):
        with open(tdump, encoding="utf-8") as f:
            text_lines = len({line for line in f if line.strip()})
    midi = os.path.join(dump_dir, "midi")
    return {
        "backgrounds": sum(1 for r in rows if r["type"] == "bg"),
        "sprite_frames": sum(1 for r in rows if r["type"] == "spr"),
        "sprite_pixels": sum(r["w"] * r["h"] for r in rows if r["type"] == "spr"),
        "text_lines": text_lines,
        "midi_files": len(os.listdir(midi)) if os.path.isdir(midi) else 0,
        "csv": out_csv,
    }


# ------------------------------------------------------------------ patchability of the engine
def _keys_in(d, exts):
    if not os.path.isdir(d):
        return set()
    return {os.path.splitext(n)[0] for n in os.listdir(d) if n.lower().endswith(exts) and "." not in os.path.splitext(n)[0]}


def coverage(dump_dir, pack_dir, lang=None):
    """Which contents of the dump (what the engine passed to the Layer) the pack replaces, and
    which pack entries the engine never asked for (orphans: route not hooked in the engine, wrong
    key, or a part of the game the dump pass did not reach)."""
    from . import text as _text
    rep = {}
    seen_text = set()
    tdump = os.path.join(dump_dir, "text.jsonl")
    if os.path.exists(tdump):
        seen_text = {d["key"] for d in _text.read_dump(tdump)}
    langs = [lang] if lang else sorted(os.path.splitext(n)[0] for n in os.listdir(os.path.join(pack_dir, "text"))
                                       if n.endswith(".tsv")) if os.path.isdir(os.path.join(pack_dir, "text")) else []
    for lg in langs:
        p = os.path.join(pack_dir, "text", lg + ".tsv")
        keys = set()
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                keys = {ln.split("\t", 1)[0] for ln in f if "\t" in ln and not ln.startswith("#")}
        rep[f"text/{lg}"] = _cov(seen_text, keys)
        rep[f"voice/{lg}"] = _cov(seen_text, _keys_in(os.path.join(pack_dir, "voice", lg), (".ogg",)), partial=True)
    rep["gfx/bg"] = _cov(_keys_in(os.path.join(dump_dir, "bg"), (".raw",)),
                         _keys_in(os.path.join(pack_dir, "gfx", "bg"), (".png", ".jpg")))
    rep["gfx/spr"] = _cov(_keys_in(os.path.join(dump_dir, "spr"), (".raw",)),
                          _keys_in(os.path.join(pack_dir, "gfx", "spr"), (".png", ".jpg")))
    problems = [f"{k}: {v['orphans']} voci del pacchetto mai richieste dal motore (es. {', '.join(v['orphan_examples'])})"
                for k, v in rep.items() if v["orphans"]]
    return {"coverage": rep, "problems": problems,
            "note": "un orfano indica un percorso del motore che non passa dal Layer (hook mancante) o una "
                    "parte non raggiunta dal dump: rifai il passaggio fuzz/sweep prima di concludere"}


def _cov(seen, have, partial=False):
    covered = seen & have
    orphans = sorted(have - seen)
    return {"seen": len(seen), "in_pack": len(have), "covered": len(covered),
            "missing": None if partial else len(seen - have),
            "orphans": len(orphans), "orphan_examples": orphans[:5]}


def canary(dump_dir, out_dir, lang, codepage="cp850", scale=3, voices=0):
    """Test pack that replaces EVERYTHING with visible markers: every text gets «·» around it,
    backgrounds and sprites get a magenta frame, optionally the first `voices` lines a beep.
    Played with the test driver, anything shown without the marker is a route of the engine that
    does not accept patches yet (text drawn directly, background copied without the Layer...)."""
    from PIL import Image as _Image
    from . import text as _text
    os.makedirs(out_dir, exist_ok=True)
    made = {"text": 0, "bg": 0, "spr": 0, "voice": 0}
    tdump = os.path.join(dump_dir, "text.jsonl")
    if os.path.exists(tdump):
        rows = {}
        for d in _text.read_dump(tdump, codepage):
            rows.setdefault(d["key"], d["text"])
        os.makedirs(os.path.join(out_dir, "text"), exist_ok=True)
        with open(os.path.join(out_dir, "text", lang + ".tsv"), "w", encoding="utf-8") as f:
            for k, t in rows.items():
                f.write(f"{k}\t«{t.replace(chr(10), ' ')}»\n")
        made["text"] = len(rows)
        if voices:
            import shutil as _sh
            import subprocess as _sp
            if _sh.which("ffmpeg"):
                vd = os.path.join(out_dir, "voice", lang)
                os.makedirs(vd, exist_ok=True)
                for k in list(rows)[:voices]:
                    _sp.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=880:d=0.4",
                             "-c:a", "libvorbis", os.path.join(vd, k + ".ogg")], check=True)
                    made["voice"] += 1

    def frame(im):
        a = im.copy()
        w, h = a.size
        b = max(2, scale)
        for x0, y0, x1, y1 in ((0, 0, w, b), (0, h - b, w, h), (0, 0, b, h), (w - b, 0, w, h)):
            a.paste((255, 0, 255, 255) if a.mode == "RGBA" else (255, 0, 255), (x0, y0, x1, y1))
        return a
    for sub, kind in (("bg", "bg"), ("spr", "spr")):
        src = os.path.join(dump_dir, sub)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(out_dir, "gfx", sub)
        os.makedirs(dst, exist_ok=True)
        for n in sorted(os.listdir(src)):
            if not n.endswith(".raw"):
                continue
            fr = rawframe.read_raw(os.path.join(src, n))
            im = (fr.rgb() if kind == "bg" else fr.rgba()).resize((fr.w * scale, fr.h * scale), _Image.NEAREST)
            frame(im).save(os.path.join(dst, n[:-4] + ".png"))
            made[kind] += 1
    if made["spr"]:
        rawframe.build_index_from_dump(os.path.join(dump_dir, "spr"), os.path.join(out_dir, "gfx", "spr"),
                                       os.path.join(out_dir, "gfx", "spr", "index.dat"), scale)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"rac": 1, "game": "canary", "pack": "0.0.0-canary", "scale": scale, "languages": [lang],
                   "contents": [k for k, v in made.items() if v]}, f, indent=2)
    return {"pack": out_dir, **made}
