#!/usr/bin/env python3
"""ip_guard.py — keeps this public repository free of game content and of references to
proprietary works.

Checks every tracked text file (or the given paths):
  1. denylisted terms: game titles, characters, places, developers, proprietary engines...
     The denylist is stored as SHA-256 hashes of normalized terms (.ipguard/denylist.sha256),
     so the list itself discloses nothing. Terms of 1 to 5 words are matched as whole words.
  2. game media and data: images, audio, video, archives, disc images, executables and
     unknown binaries are refused, except paths listed in .ipguard/allow.txt.
  3. large files (> 2 MB).
  4. optional, local only: --private-texts <file> with the game's own texts (one per line, or
     "<key>\\t<text>"): any 6-word sequence of them found here is reported. Never commit that file.

Usage:
  python3 tools/ip_guard.py                       # scan the git-tracked files
  python3 tools/ip_guard.py --staged              # scan what is about to be committed
  python3 tools/ip_guard.py --add "term" [...]    # add terms to the hashed denylist
  python3 tools/ip_guard.py --private-texts ../mio-gioco/text/it.txt
Exit code 1 when something is found.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DENY = os.path.join(ROOT, ".ipguard", "denylist.sha256")
ALLOW = os.path.join(ROOT, ".ipguard", "allow.txt")
MAX_WORDS = 5
MAX_BYTES = 2 * 1024 * 1024
MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tga", ".pcx", ".lbm", ".ico",
         ".wav", ".ogg", ".mp3", ".flac", ".voc", ".mid", ".midi", ".xmi", ".mod", ".s3m", ".xm",
         ".mp4", ".avi", ".mkv", ".webm", ".flc", ".fli", ".smk", ".san",
         ".zip", ".7z", ".rar", ".gz", ".tar", ".iso", ".img", ".bin", ".cue", ".ccd", ".sub",
         ".exe", ".com", ".dll", ".ovl", ".dat", ".pak", ".res", ".raw", ".sfx", ".fnt", ".pth", ".pt"}


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", t))


def digest(term: str) -> str:
    return hashlib.sha256(normalize(term).encode()).hexdigest()


def load_hashes():
    if not os.path.exists(DENY):
        return set()
    with open(DENY, encoding="ascii") as f:
        return {l.strip() for l in f if re.fullmatch(r"[0-9a-f]{64}", l.strip())}


def load_allow():
    if not os.path.exists(ALLOW):
        return []
    with open(ALLOW, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def tracked_files(staged=False):
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged else ["git", "ls-files"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l]


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8192]


def scan(paths, hashes, allow, private_grams=None):
    problems = []
    for rel in paths:
        if rel.startswith(".ipguard/"):
            continue
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        allowed = any(rel == a or (a.endswith("/") and rel.startswith(a)) for a in allow)
        ext = os.path.splitext(rel)[1].lower()
        size = os.path.getsize(p)
        if size > MAX_BYTES and not allowed:
            problems.append(f"{rel}: file grande ({size // 1024} KB)")
        with open(p, "rb") as f:
            data = f.read()
        if (ext in MEDIA or is_binary(data)) and not allowed:
            problems.append(f"{rel}: file multimediale/binario non ammesso (possibile contenuto di gioco)")
            continue
        text = data.decode("utf-8", "replace")
        for n, line in enumerate(text.splitlines(), 1):
            words = normalize(line).split()
            for i in range(len(words)):
                for k in range(1, MAX_WORDS + 1):
                    if i + k > len(words):
                        break
                    if hashlib.sha256(" ".join(words[i:i + k]).encode()).hexdigest() in hashes:
                        problems.append(f"{rel}:{n}: termine vietato: «{' '.join(words[i:i + k])}»")
            if private_grams:
                for i in range(len(words) - 5):
                    g = " ".join(words[i:i + 6])
                    if g in private_grams:
                        problems.append(f"{rel}:{n}: testo del gioco: «{g}»")
    return problems


def private_grams_of(path):
    grams = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            words = normalize(line.split("\t", 1)[-1]).split()
            for i in range(len(words) - 5):
                grams.add(" ".join(words[i:i + 6]))
    return grams


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--add", nargs="+", metavar="TERM", help="aggiungi termini alla denylist (salvati come hash)")
    ap.add_argument("--private-texts", help="file locale con i testi del gioco (mai da committare)")
    a = ap.parse_args()
    if a.add:
        os.makedirs(os.path.dirname(DENY), exist_ok=True)
        hashes = load_hashes() | {digest(t) for t in a.add if normalize(t)}
        with open(DENY, "w", encoding="ascii") as f:
            f.write("\n".join(sorted(hashes)) + "\n")
        print(f"denylist: {len(hashes)} hash")
        return 0
    paths = a.paths or tracked_files(a.staged)
    grams = private_grams_of(a.private_texts) if a.private_texts else None
    problems = scan(paths, load_hashes(), load_allow(), grams)
    for p in problems:
        print(p)
    if problems:
        print(f"\nip_guard: {len(problems)} problemi. Il repository è pubblico: niente contenuti o riferimenti a giochi.")
        return 1
    print(f"ip_guard: ok ({len(paths)} file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
