"""Recipes: the reproducible steps that rebuild remaster/ from the user's own copy.

recipes/recipe.json
{
  "rac": 1, "game": "<game-id>", "scale": 3,
  "steps": [
    {"name": "dump", "exec": ["{engine}", "--config={work}/dump.ini", "--path={game}", "<game-id>"]},
    {"name": "backgrounds", "rstool": ["gfx", "bg", "{work}/dump/bg", "--out", "{out}/gfx/bg",
                                       "--scale", "3", "--recipe", "{recipes}/style-recipes.json"]},
    {"name": "copy approved extensions", "copy": ["{recipes}/wide", "{out}/gfx/bg"]}
  ]
}
Placeholders: {game} {out} {work} {engine} {recipes} {python}.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

RSTOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rstool.py")


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _sub(v, ctx):
    if isinstance(v, list):
        return [_sub(x, ctx) for x in v]
    return v.format(**ctx) if isinstance(v, str) else v


def run(recipe_path, game, out, engine=None, work=None, only=None, dry_run=False):
    with open(recipe_path, encoding="utf-8") as f:
        recipe = json.load(f)
    work = work or os.path.join(os.path.dirname(os.path.abspath(out)), ".remaster-work")
    ctx = {"game": game, "out": out, "work": work, "engine": engine or "scummvm",
           "recipes": os.path.dirname(os.path.abspath(recipe_path)), "python": sys.executable}
    os.makedirs(work, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    log = []
    for step in recipe.get("steps", []):
        if only and step["name"] not in only:
            continue
        if "exec" in step:
            cmd = _sub(step["exec"], ctx)
        elif "rstool" in step:
            cmd = [sys.executable, RSTOOL, *_sub(step["rstool"], ctx)]
        elif "copy" in step:
            src, dst = _sub(step["copy"], ctx)
            log.append({"step": step["name"], "copy": [src, dst]})
            if not dry_run and os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            continue
        else:
            raise ValueError(f"passo senza azione: {step}")
        log.append({"step": step["name"], "cmd": cmd})
        if not dry_run:
            subprocess.run(cmd, check=True)
    if not dry_run:
        manifest = {"rac": 1, "game": recipe.get("game"), "pack": recipe.get("version", "recipe"),
                    "scale": recipe.get("scale", 3), "aspect": recipe.get("aspect", "16:9"),
                    "contents": recipe.get("contents", []), "languages": recipe.get("languages", []),
                    "recipe": {"file": os.path.basename(recipe_path), "hash": "sha256:" + _sha256(recipe_path)}}
        with open(os.path.join(out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
    return log
