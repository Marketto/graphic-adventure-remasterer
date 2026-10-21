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
