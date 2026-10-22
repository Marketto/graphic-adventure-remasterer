"""Game identification from the user's own files.

No list of games or proprietary engines is shipped with the tools: recognition is delegated
to ScummVM's own detection tables (`scummvm --detect`, open source, MD5 based), and this
module only adds a neutral inventory (extensions, executables, disc images) that the agent
uses to search for the engine online.
"""
import collections
import hashlib
import os
import re
import shutil
import subprocess

DISC_IMAGES = (".iso", ".img", ".bin", ".cue", ".ccd", ".mdf", ".nrg", ".7z", ".zip")


def list_files(root):
    out = []
    for d, _dirs, files in os.walk(root):
        for f in files:
            out.append(os.path.relpath(os.path.join(d, f), root))
    return out


def inventory(root):
    """Neutral facts about the folder: extension histogram, largest files, executables, disc images."""
    files = list_files(root)
    ext = collections.Counter(os.path.splitext(f)[1].lower() or "<none>" for f in files)
    sizes = sorted(((os.path.getsize(os.path.join(root, f)), f) for f in files), reverse=True)
    exes = [f for f in files if f.lower().endswith((".exe", ".com", ".bat"))]
    discs = [f for f in files if f.lower().endswith(DISC_IMAGES)]
    dirs = sorted({os.path.dirname(f) for f in files if os.path.dirname(f)})
    return {
        "files": len(files),
        "extensions": dict(ext.most_common(25)),
        "largest": [{"file": f.replace(os.sep, "/"), "size": s} for s, f in sizes[:10]],
        "executables": exes[:20],
        "disc_images": discs,
        "directories": dirs[:40],
    }


def exe_strings(root, exe, min_len=6, limit=60):
    """Printable strings of an executable (copyright lines, engine banners) to search online."""
    with open(os.path.join(root, exe), "rb") as fh:
        blob = fh.read(8 * 1024 * 1024)
    found = re.findall(rb"[\x20-\x7e]{%d,}" % min_len, blob)
    keep = [s.decode("ascii", "replace") for s in found
            if re.search(rb"(?i)(copyright|\(c\)|version|engine|interpreter|19[89]\d)", s)]
    return keep[:limit]


def scummvm_detect(root, binary=None):
    exe = binary or shutil.which("scummvm")
    if not exe:
        return None
    try:
        res = subprocess.run([exe, "--detect", f"--path={root}"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}
    games = []
    for line in res.stdout.splitlines():
        m = re.match(r"^(\S+:\S+)\s+(.+?)\s{2,}(\S.*)$", line.strip())
        if m:
            games.append({"id": m.group(1), "description": m.group(2).strip(), "path": m.group(3).strip()})
    return {"games": games, "raw": res.stdout[-4000:]}


def md5_tree(root, limit_mb=2048):
    out = {}
    for rel in sorted(list_files(root)):
        p = os.path.join(root, rel)
        if os.path.getsize(p) > limit_mb * 1024 * 1024:
            continue
        h = hashlib.md5()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        out[rel.replace(os.sep, "/")] = {"md5": h.hexdigest(), "size": os.path.getsize(p)}
    return out


LINK_FILES = (".url", ".lnk", ".webloc", ".desktop", ".website")
TEXT_FILES = (".txt", ".nfo", ".diz", ".htm", ".html", ".md", ".rtf")
_URL = re.compile(rb"(?:https?://|www\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s\"'<>\x00]*", re.I)
# hosts of the official stores and of the open source tools: links to them are not reported
KNOWN_HOSTS = ("scummvm.org", "dosbox.com", "dosbox-staging.org", "gog.com", "steampowered.com",
               "steamcommunity.com", "humblebundle.com", "itch.io", "github.com", "microsoft.com",
               "apple.com")


def third_party_links(root, max_bytes=200000):
    """Shortcuts (.url/.lnk/.webloc...) and readme-like files that point to web sites other than
    the official stores: the folder may come from a redistribution site. The agent only REPORTS
    them and asks the user to confirm that the files come from his own copy."""
    found = []
    for f in list_files(root):
        low = f.lower()
        if not low.endswith(LINK_FILES + TEXT_FILES):
            continue
        p = os.path.join(root, f)
        try:
            with open(p, "rb") as fh:
                data = fh.read(max_bytes)
        except OSError:
            continue
        urls = sorted({u.decode("latin-1").rstrip(".,);]") for u in _URL.findall(data)})
        hosts = sorted({re.sub(r"^(?:https?://)?(?:www\.)?", "", u, flags=re.I).split("/")[0].lower() for u in urls})
        other = [h for h in hosts if not any(h == k or h.endswith("." + k) for k in KNOWN_HOSTS)]
        if low.endswith(LINK_FILES) or other:
            found.append({"file": f.replace(os.sep, "/"), "kind": "collegamento" if low.endswith(LINK_FILES) else "testo",
                          "hosts": other or hosts})
    return found


def detect(root, binary=None):
    if not os.path.isdir(root):
        raise NotADirectoryError(root)
    result = inventory(root)
    links = third_party_links(root)
    if links:
        result["third_party_links"] = links
        result["warning"] = ("tra i file ci sono collegamenti a siti di terze parti: chiedi all'utente di "
                             "confermare che i file vengono dalla sua copia (regola «copia propria»)")
    result["strings"] = {e: exe_strings(root, e) for e in result["executables"][:5]}
    sv = scummvm_detect(root, binary)
    result["scummvm"] = sv if sv is not None else "scummvm non installato: installalo per il riconoscimento"
    return result
