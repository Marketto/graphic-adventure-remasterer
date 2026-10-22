"""Extraction without the Remaster Layer: the generic contract of the dump.

Until the Layer is hooked into an engine there is no `remaster_dump=`. The assets are then
extracted with the open source tools of that engine through an ADAPTER that lives in the
private repository of the game (a script or a command: it knows the engine, the suite does not).
The suite runs it and validates what it wrote against the dump format below, the same the Layer
writes, so every later phase (inventory, style, classify, catalog, plan) works the same way.

Dump (`<out>/`), every part optional except `bg/`:

    bg/<scene>.png|.raw          backgrounds at original size (PNG: RGB or indexed)
    bg/names.json                {scene: room name from the game's index} (helps the 16:9 classifier)
    spr/<key>.png|.raw           sprite frames (PNG RGBA, alpha 0 = transparent)
    spr/index.json               list of frames (or {"frames": [...]}) when spr/ holds only a sample
    obj/<name>.png               object images drawn over the backgrounds (PNG RGBA or RGB)
    text.jsonl                   one JSON per line: {"hex": original bytes in hex (required),
                                 "kind", "location", "speaker", "voice", ...}; repeated rows allowed
    voice-index.json             {voice id: {"file", "hex"?, "speaker"?, "seconds"?, "lipsync"?}}
                                 or a list of such objects with "id"
    midi/<name>.mid              standard MIDI files (the music variant closest to General MIDI)
    meta.json                    {"screen": [w, h], "playfield_h"?, "engine"?, "extractor"?}

The adapter is called with the placeholders {game} and {out} replaced; without placeholders
`--game <dir> --out <dir>` is appended. A `.py` adapter runs with this Python.
"""
import json
import os
import re
import shlex
import subprocess
import sys

from PIL import Image

TEXT_KINDS = {"balloon", "answer", "question", "examine", "subtitle", "comment", "choice", "label",
              "name", "menu", "scene", "system", ""}
_HEX = re.compile(r"^(?:[0-9a-fA-F]{2})*$")


def adapter_command(adapter, game_dir, out_dir):
    if "{game}" in adapter or "{out}" in adapter:
        cmd = shlex.split(adapter.replace("{game}", shlex.quote(game_dir)).replace("{out}", shlex.quote(out_dir)))
    else:
        cmd = shlex.split(adapter) + ["--game", game_dir, "--out", out_dir]
    if cmd and cmd[0].endswith(".py"):
        cmd = [sys.executable] + cmd
    return cmd


def run_adapter(adapter, game_dir, out_dir, timeout=None):
    """Run the adapter of the private repository, then validate the dump."""
    os.makedirs(out_dir, exist_ok=True)
    cmd = adapter_command(adapter, game_dir, out_dir)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    res = validate_dump(out_dir)
    res["adapter"] = {"command": cmd, "returncode": r.returncode, "stderr_tail": r.stderr[-2000:]}
    if r.returncode != 0:
        res["ok"] = False
        res["errors"].insert(0, f"l'adattatore è uscito con codice {r.returncode}")
    return res


def _png(path, errors, warnings, want_alpha=False):
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            mode, size = im.mode, im.size
    except Exception as e:  # noqa: BLE001
        errors.append(f"{path}: immagine illeggibile ({e})")
        return None
    if want_alpha and mode not in ("RGBA", "LA", "P", "PA"):
        warnings.append(f"{os.path.basename(path)}: sprite senza trasparenza ({mode})")
    return size


def validate_dump(dump_dir, max_errors=50):
    """Check a dump against the contract. Returns ok, errors, warnings and counts."""
    errors, warnings, counts = [], [], {}
    bg = os.path.join(dump_dir, "bg")
    if not os.path.isdir(bg):
        errors.append("manca bg/ (fondali)")
    else:
        files = [n for n in os.listdir(bg) if n.lower().endswith((".png", ".raw"))]
        if not files:
            errors.append("bg/ non contiene fondali .png o .raw")
        scenes = {os.path.splitext(n)[0] for n in files}
        for n in files:
            if n.lower().endswith(".png"):
                _png(os.path.join(bg, n), errors, warnings)
        counts["backgrounds"] = len(scenes)
        names = os.path.join(bg, "names.json")
        if os.path.exists(names):
            try:
                with open(names, encoding="utf-8") as f:
                    nm = json.load(f)
                if not isinstance(nm, dict) or not all(isinstance(v, str) for v in nm.values()):
                    errors.append("bg/names.json deve essere {scena: nome}")
                else:
                    unknown = sorted(set(nm) - scenes)
                    if unknown:
                        warnings.append(f"bg/names.json: {len(unknown)} scene senza fondale (es. {unknown[0]})")
                    counts["named_scenes"] = len(set(nm) & scenes)
            except ValueError as e:
                errors.append(f"bg/names.json non è JSON valido ({e})")
        else:
            warnings.append("manca bg/names.json: il classificatore 16:9 non vede i nomi delle stanze")
    for sub, alpha in (("spr", True), ("obj", False)):
        d = os.path.join(dump_dir, sub)
        if os.path.isdir(d):
            files = [n for n in os.listdir(d) if n.lower().endswith((".png", ".raw"))]
            for n in files[:2000]:
                if n.lower().endswith(".png"):
                    _png(os.path.join(d, n), errors, warnings, want_alpha=alpha)
            counts[sub] = len(files)
    t = os.path.join(dump_dir, "text.jsonl")
    if os.path.exists(t):
        rows, uniq, kinds = 0, set(), {}
        with open(t, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                rows += 1
                try:
                    r = json.loads(line)
                except ValueError:
                    errors.append(f"text.jsonl:{i}: non è JSON")
                    continue
                h = r.get("hex") if isinstance(r, dict) else None
                if not isinstance(h, str) or not _HEX.match(h):
                    errors.append(f"text.jsonl:{i}: manca \"hex\" (byte originali in esadecimale)")
                    continue
                uniq.add(h)
                k = r.get("kind", "")
                kinds[k] = kinds.get(k, 0) + 1
                if k not in TEXT_KINDS:
                    warnings.append(f"text.jsonl:{i}: tipo «{k}» sconosciuto (ammessi: {', '.join(sorted(TEXT_KINDS - {''}))})")
        counts.update(text_rows=rows, text_unique=len(uniq), text_kinds=kinds)
    v = os.path.join(dump_dir, "voice-index.json")
    if os.path.exists(v):
        try:
            with open(v, encoding="utf-8") as f:
                vi = json.load(f)
            entries = vi.items() if isinstance(vi, dict) else ((e.get("id"), e) for e in vi if isinstance(e, dict))
            n = lip = 0
            for vid, e in entries:
                n += 1
                if not vid or not isinstance(e, dict) or not e.get("file"):
                    errors.append(f"voice-index.json: voce {vid!r} senza \"file\"")
                    continue
                lip += bool(e.get("lipsync"))
            counts.update(voice_clips=n, voice_lipsync=lip)
        except ValueError as e:
            errors.append(f"voice-index.json non è JSON valido ({e})")
    m = os.path.join(dump_dir, "midi")
    if os.path.isdir(m):
        mids = [n for n in os.listdir(m) if n.lower().endswith((".mid", ".midi"))]
        for n in mids:
            with open(os.path.join(m, n), "rb") as f:
                if f.read(4) != b"MThd":
                    errors.append(f"midi/{n}: non è un MIDI standard (manca MThd)")
        counts["midi_files"] = len(mids)
    meta = os.path.join(dump_dir, "meta.json")
    if os.path.exists(meta):
        try:
            with open(meta, encoding="utf-8") as f:
                mt = json.load(f)
            scr = mt.get("screen")
            if scr is not None and not (isinstance(scr, list) and len(scr) == 2):
                errors.append("meta.json: \"screen\" deve essere [larghezza, altezza]")
            counts["meta"] = {k: mt[k] for k in ("screen", "playfield_h", "engine") if k in mt}
        except ValueError as e:
            errors.append(f"meta.json non è JSON valido ({e})")
    more = len(errors) - max_errors
    errors = errors[:max_errors] + ([f"... e altri {more} errori"] if more > 0 else [])
    return {"ok": not errors, "errors": errors, "warnings": warnings[:max_errors], "counts": counts}
