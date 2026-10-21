"""Release packaging and verification (no original game file may ever ship)."""
import hashlib
import json
import os
import shutil

from . import detect

REQUIRED_LICENSES = ["GPL-3.0.txt"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def package(project, out_root, game_md5_json, patches_dir=None, engines_dir=None, remaster_dir=None,
            recipes_dir=None, licenses_dir=None, version="1.0.0"):
    title = (project.get("game", {}).get("title") or "game").lower().replace(" ", "-")
    mode = project.get("distribution", {}).get("mode", "recipe")
    if mode == "asset-pack" and not project.get("distribution", {}).get("rights_confirmed"):
        raise PermissionError("modalità asset-pack senza permesso dei titolari registrato (distribution.rights_confirmed)")
    root = os.path.join(out_root, f"{title}-remaster-{version}")
    if os.path.exists(root):
        shutil.rmtree(root)
    os.makedirs(root)

    def copytree(src, name):
        if src and os.path.isdir(src):
            shutil.copytree(src, os.path.join(root, name))

    copytree(patches_dir, "patches")
    copytree(engines_dir, "engine")
    copytree(licenses_dir, "LICENSES")
    if mode == "asset-pack":
        copytree(remaster_dir, "remaster")
    else:
        copytree(recipes_dir, "recipes")
        tools_src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        shutil.copytree(tools_src, os.path.join(root, "tools"),
                        ignore=shutil.ignore_patterns("__pycache__", "tests", "*.pyc"))
    os.makedirs(os.path.join(root, "recipes"), exist_ok=True)
    shutil.copyfile(game_md5_json, os.path.join(root, "recipes", "game-md5.json"))
    here = os.path.dirname(os.path.abspath(__file__))
    shutil.copyfile(os.path.join(here, "templates", "install.py"), os.path.join(root, "install.py"))
    with open(os.path.join(root, "LEGGIMI.txt"), "w", encoding="utf-8") as f:
        f.write(readme(project, mode, version))
    write_checksums(root)
    return root


def readme(project, mode, version):
    g = project.get("game", {})
    plats = ", ".join(project.get("platforms", []))
    key = project.get("toggle_key", "F8")
    lines = [
        f"{g.get('title', 'Gioco')} — Remaster {version}",
        "",
        "Serve una copia originale del gioco: questo pacchetto non contiene alcun file del gioco.",
        "",
        "Installazione",
        "1. Copia i file del gioco originale in una cartella del tuo computer.",
        "2. Esegui:  python install.py \"<cartella del gioco>\"",
        "   Lo script verifica la tua copia (MD5) e " + ("copia" if mode == "asset-pack" else "genera") +
        " la cartella remaster/ accanto ai file originali, senza modificarli.",
        "3. Avvia l'eseguibile per la tua piattaforma (cartella engine/) e aggiungi la cartella del gioco.",
        "",
        f"Durante il gioco premi {key} per passare in qualsiasi momento tra versione originale e rimasterizzata.",
        "Salvataggi e menu: menu del gioco o menu globale (Ctrl+F5 su PC).",
    ]
    ex = project.get("extras", {})
    if ex.get("hints"):
        lines.append("Aiuti: premi H durante il gioco (sul telefono e sul web c'è un pulsante).")
    if ex.get("manual"):
        lines.append("Manuale: dal menu del gioco (voce Manuale) o aprendo manual/<lingua>.html accanto all'eseguibile.")
    if project.get("ui_theme", {}).get("enabled", True):
        lines.append("I menu usano il tema grafico del remaster (remaster/theme/), impostato al primo avvio.")
    lines += [
        "",
        f"Piattaforme: {plats}.",
        "",
        "Licenze: il motore è software libero (GPL-3.0, sorgenti e patch in patches/). Vedi LICENSES/.",
    ]
    if project.get("voice", {}).get("enabled"):
        lines.append("Voci sintetiche generate con ElevenLabs.")
    return "\n".join(lines) + "\n"


def write_checksums(root):
    entries = []
    for d, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f == "checksums.sha256":
                continue
            p = os.path.join(d, f)
            entries.append(f"{sha256(p)}  {os.path.relpath(p, root).replace(os.sep, '/')}")
    with open(os.path.join(root, "checksums.sha256"), "w") as f:
        f.write("\n".join(sorted(entries, key=lambda e: e[66:])) + "\n")


def verify(root, game_md5_json=None):
    problems = []
    md5s = set()
    if game_md5_json is None:
        game_md5_json = os.path.join(root, "recipes", "game-md5.json")
    if os.path.exists(game_md5_json):
        with open(game_md5_json, encoding="utf-8") as f:
            data = json.load(f)
        versions = data.get("versions", {"default": data})
        for files in versions.values():
            for info in files.values():
                md5s.add(info["md5"])
    else:
        problems.append("manca recipes/game-md5.json")
    for d, _dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, root)
            if rel.replace(os.sep, "/") == "recipes/game-md5.json":
                continue
            if md5(p) in md5s:
                problems.append(f"file originale del gioco incluso: {rel}")
    lic = os.path.join(root, "LICENSES")
    for name in REQUIRED_LICENSES:
        if not os.path.exists(os.path.join(lic, name)):
            problems.append(f"licenza mancante: LICENSES/{name}")
    ck = os.path.join(root, "checksums.sha256")
    if os.path.exists(ck):
        for line in open(ck):
            h, rel = line.rstrip("\n").split("  ", 1)
            p = os.path.join(root, rel)
            if not os.path.exists(p) or sha256(p) != h:
                problems.append(f"checksum non valido: {rel}")
    else:
        problems.append("manca checksums.sha256")
    man = os.path.join(root, "remaster", "manifest.json")
    if os.path.exists(man):
        with open(man) as f:
            m = json.load(f)
        if m.get("rac") != 1:
            problems.append("manifest RAC con versione inattesa")
    return {"ok": not problems, "problems": problems}


def game_md5(game_dir, out_json, version_name="default"):
    data = {"versions": {version_name: detect.md5_tree(game_dir)}}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return {"files": len(data["versions"][version_name])}


# ------------------------------------------------------------------ weight of the pack
TARGETS = {
    # total pack, biggest single picture decoded (MB of RGBA), file size of one volume of the patch
    "desktop": {"pack_mb": 4000, "decoded_mb": 64, "volume_mb": None},
    "android": {"pack_mb": 1500, "decoded_mb": 32, "volume_mb": None},
    "web": {"pack_mb": 800, "decoded_mb": 24, "volume_mb": 29},
}


def budget(remaster_dir, targets=("desktop", "android", "web"), top=10):
    """Size of the pack per folder, biggest files, decoded memory of the largest pictures, and
    the checks for each target platform (phone and browser have much less memory)."""
    from PIL import Image
    per_dir, files = {}, []
    for d, _dirs, fs in os.walk(remaster_dir):
        for f in fs:
            p = os.path.join(d, f)
            s = os.path.getsize(p)
            rel = os.path.relpath(p, remaster_dir)
            top_dir = rel.split(os.sep)[0] if os.sep in rel else "."
            sub = os.sep.join(rel.split(os.sep)[:2]) if rel.count(os.sep) >= 2 else top_dir
            per_dir[sub] = per_dir.get(sub, 0) + s
            files.append((s, rel))
    total = sum(s for s, _r in files)
    pics = []
    for s, rel in files:
        if rel.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            try:
                with Image.open(os.path.join(remaster_dir, rel)) as im:
                    w, h = im.size
            except OSError:
                continue
            pics.append((w * h * 4 / 2 ** 20, rel, w, h, s))
    pics.sort(reverse=True)
    png_bg = [r for _m, r, _w, _h, s in pics if r.startswith(os.path.join("gfx", "bg")) and r.endswith(".png")
              and s > 3 * 2 ** 20]
    checks = {}
    for t in targets:
        lim = TARGETS[t]
        probs = []
        if total / 2 ** 20 > lim["pack_mb"]:
            probs.append(f"pacchetto {total / 2 ** 20:.0f} MB > {lim['pack_mb']} MB")
        big = [r for m, r, *_x in pics if m > lim["decoded_mb"]]
        if big:
            probs.append(f"{len(big)} immagini decodificate oltre {lim['decoded_mb']} MB (es. {big[0]})")
        if lim["volume_mb"]:
            n = int(total / (lim["volume_mb"] * 2 ** 20)) + 1
            probs.append(f"info: {n} volumi da {lim['volume_mb']} MB per la consegna da telefono")
        checks[t] = {"ok": not [p for p in probs if not p.startswith("info")], "notes": probs}
    advice = []
    if png_bg:
        advice.append(f"{len(png_bg)} fondali PNG oltre 3 MB: JPEG q90 4:4:4 li riduce di 5-10 volte senza "
                      "sporcare i bordi")
    return {"total_mb": round(total / 2 ** 20, 1), "files": len(files),
            "per_dir_mb": {k: round(v / 2 ** 20, 1) for k, v in sorted(per_dir.items(), key=lambda x: -x[1])},
            "biggest": [{"file": r, "mb": round(s / 2 ** 20, 2)} for s, r in sorted(files, reverse=True)[:top]],
            "largest_decoded": [{"file": r, "size": [w, h], "decoded_mb": round(m, 1)} for m, r, w, h, _s in pics[:top]],
            "targets": checks, "advice": advice}
