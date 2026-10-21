#!/usr/bin/env python3
"""Installer of the remaster: checks your copy of the game, then copies or regenerates
the remaster/ folder next to the original files. The original files are never changed.

Usage:  python install.py "<game folder>" [--engine <path to the remaster executable>]
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_version(game_dir):
    with open(os.path.join(HERE, "recipes", "game-md5.json"), encoding="utf-8") as f:
        versions = json.load(f)["versions"]
    present = {}
    for d, _dirs, files in os.walk(game_dir):
        if os.path.abspath(d).startswith(os.path.join(os.path.abspath(game_dir), "remaster")):
            continue
        for fn in files:
            rel = os.path.relpath(os.path.join(d, fn), game_dir).replace(os.sep, "/").lower()
            present[rel] = os.path.join(d, fn)
    best = None
    for name, files in versions.items():
        ok = bad = 0
        for rel, info in files.items():
            p = present.get(rel.lower())
            if p and md5(p) == info["md5"]:
                ok += 1
            else:
                bad += 1
        score = ok / max(1, ok + bad)
        if best is None or score > best[1]:
            best = (name, score, bad)
    return best


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    game = os.path.abspath(sys.argv[1])
    engine = sys.argv[sys.argv.index("--engine") + 1] if "--engine" in sys.argv else None
    if not os.path.isdir(game):
        print("Cartella non trovata:", game)
        return 2
    name, score, bad = find_version(game)
    if score < 1.0:
        print(f"La copia del gioco non corrisponde a nessuna versione supportata "
              f"(più vicina: {name}, {bad} file diversi o mancanti). Installazione annullata.")
        return 1
    print(f"Versione riconosciuta: {name}")
    target = os.path.join(game, "remaster")
    src = os.path.join(HERE, "remaster")
    if os.path.isdir(src):
        if os.path.exists(target):
            shutil.rmtree(target)
        shutil.copytree(src, target)
        print("Asset rimasterizzati copiati in", target)
        return 0
    recipe = os.path.join(HERE, "recipes", "recipe.json")
    if not os.path.exists(recipe):
        print("Pacchetto incompleto: mancano sia remaster/ sia recipes/recipe.json")
        return 1
    cmd = [sys.executable, os.path.join(HERE, "tools", "rstool.py"), "recipe", "run", recipe,
           "--game", game, "--out", target]
    if engine:
        cmd += ["--engine", engine]
    print("Rigenerazione degli asset dalla tua copia (può richiedere tempo e una GPU)...")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
