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
  4. secrets: API keys and tokens (ElevenLabs, fal.ai, GitHub, Anthropic, OpenAI, cloud
     keys, private keys, "key = ..." assignments) and personal e-mail addresses.
  5. local, never committed: the game's own texts (catalogues, OCR of manuals...) listed in
     .ipguard/private.local or <.git>/ipguard-private (shared by all worktrees; one path per
     line, never committed) or in IPGUARD_PRIVATE (paths
     separated by ":"), or given with --private-texts: any 6-word sequence of them found here
     is reported. The pre-commit hook uses them automatically.
With --staged the STAGED content is scanned (what will really be committed), not the working
copy; --message <file> scans a commit message (commit-msg hook).

Usage:
  python3 tools/ip_guard.py                       # scan the git-tracked files
  python3 tools/ip_guard.py --staged              # scan what is about to be committed
  python3 tools/ip_guard.py --add "term" [...]    # add terms to the hashed denylist
  python3 tools/ip_guard.py --private-texts ../mio-gioco/text/it.txt
  python3 tools/ip_guard.py --message .git/COMMIT_EDITMSG
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
PRIVATE_LIST = os.path.join(ROOT, ".ipguard", "private.local")
SECRETS = [
    ("chiave privata", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("token GitHub", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("chiave Anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("chiave OpenAI", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}")),
    ("chiave ElevenLabs", re.compile(r"\bsk_[a-f0-9]{40,}\b")),
    ("chiave fal.ai", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{32}\b")),
    ("chiave AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("chiave Google", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("token Slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("segreto assegnato", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|fal_key|elevenlabs_api_key)\b\s*[:=]\s*['\"]?"
        r"(?!\$|<|\{|xxx|\.\.\.|changeme|change-me|example|esempio|tuo|your)[A-Za-z0-9_\-/+=.]{16,}")),
]
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b")
EMAIL_OK = re.compile(r"(?i)@(users\.noreply\.github\.com|noreply\.github\.com|anthropic\.com|example\.(com|org|net)|esempio\.it)$")
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


def _read(rel, staged):
    if staged:
        r = subprocess.run(["git", "show", f":{rel}"], cwd=ROOT, capture_output=True)
        if r.returncode == 0:
            return r.stdout
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return None
    with open(p, "rb") as f:
        return f.read()


def check_text(rel, text, hashes, private_grams=None):
    problems = []
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
        for what, rx in SECRETS:
            if rx.search(line):
                problems.append(f"{rel}:{n}: possibile {what}: i segreti vanno nei segreti dell'ambiente, mai nei file")
        for m in EMAIL.finditer(line):
            if not EMAIL_OK.search(m.group(0)):
                problems.append(f"{rel}:{n}: indirizzo e-mail personale «{m.group(0)}»: usa l'indirizzo noreply")
    return problems


def scan(paths, hashes, allow, private_grams=None, staged=False):
    problems = []
    for rel in paths:
        if rel.startswith(".ipguard/"):
            continue
        data = _read(rel, staged)
        if data is None:
            continue
        allowed = any(rel == a or (a.endswith("/") and rel.startswith(a)) for a in allow)
        ext = os.path.splitext(rel)[1].lower()
        size = len(data)
        if size > MAX_BYTES and not allowed:
            problems.append(f"{rel}: file grande ({size // 1024} KB)")
        if (ext in MEDIA or is_binary(data)) and not allowed:
            problems.append(f"{rel}: file multimediale/binario non ammesso (possibile contenuto di gioco)")
            continue
        problems += check_text(rel, data.decode("utf-8", "replace"), hashes, private_grams)
    return problems


def private_grams_of(path):
    """6-word sequences of a private text file, or of every text file in a folder."""
    grams = set()
    files = [path]
    if os.path.isdir(path):
        files = [os.path.join(d, f) for d, _ds, fs in os.walk(path) for f in fs
                 if f.lower().endswith((".txt", ".tsv", ".md", ".json", ".jsonl", ".csv"))]
    for fp in files:
        with open(fp, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        cols = None
        if fp.lower().endswith(".tsv") and lines and "\t" in lines[0]:
            head = [c.strip().lower() for c in lines[0].split("\t")]
            wanted = [i for i, c in enumerate(head) if c in ("text", "source", "testo", "originale", "original")]
            if wanted:  # catalogue with a header: only the text columns
                cols, lines = wanted, lines[1:]
        for line in lines:
            if line.startswith("#"):
                continue
            if cols is not None:
                parts = line.split("\t")
                chunks = [parts[i] for i in cols if i < len(parts)]
            else:
                chunks = [line.split("\t", 1)[-1]]
            for chunk in chunks:
                words = normalize(chunk).split()
                for i in range(len(words) - 5):
                    grams.add(" ".join(words[i:i + 6]))
    return grams


def private_sources():
    """Private text sources configured locally (never committed)."""
    src = []
    lists = [PRIVATE_LIST]
    r = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 0:  # shared by every worktree of the clone: <.git>/ipguard-private
        lists.append(os.path.join(ROOT, r.stdout.strip(), "ipguard-private"))
    for lp in lists:
        if os.path.exists(lp):
            with open(lp, encoding="utf-8") as f:
                src += [l.strip() for l in f if l.strip() and not l.startswith("#")]
    env = os.environ.get("IPGUARD_PRIVATE")
    if env:
        src += [p for p in env.split(os.pathsep) if p]
    return [os.path.expanduser(p) for p in src]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--add", nargs="+", metavar="TERM", help="aggiungi termini alla denylist (salvati come hash)")
    ap.add_argument("--private-texts", action="append", default=[],
                    help="file o cartella locale con i testi del gioco (mai da committare); ripetibile")
    ap.add_argument("--message", help="file con il messaggio di commit da controllare")
    a = ap.parse_args()
    if a.add:
        os.makedirs(os.path.dirname(DENY), exist_ok=True)
        hashes = load_hashes() | {digest(t) for t in a.add if normalize(t)}
        with open(DENY, "w", encoding="ascii") as f:
            f.write("\n".join(sorted(hashes)) + "\n")
        print(f"denylist: {len(hashes)} hash")
        return 0
    sources = a.private_texts + private_sources()
    missing = [p for p in sources if not os.path.exists(p)]
    for p in missing:
        print(f"avviso: testi privati non trovati: {p}")
    grams = set()
    for p in sources:
        if os.path.exists(p):
            grams |= private_grams_of(p)
    if a.message:
        with open(a.message, encoding="utf-8", errors="replace") as f:
            msg = "\n".join(l for l in f.read().splitlines() if not l.startswith("#"))
        problems = check_text("messaggio di commit", msg, load_hashes(), grams or None)
        for p in problems:
            print(p)
        return 1 if problems else 0
    paths = a.paths or tracked_files(a.staged)
    problems = scan(paths, load_hashes(), load_allow(), grams or None, staged=a.staged)
    for p in problems:
        print(p)
    if problems:
        print(f"\nip_guard: {len(problems)} problemi. Il repository è pubblico: niente contenuti o riferimenti a giochi.")
        return 1
    extra = f", {len(grams)} sequenze di testo privato" if grams else ""
    print(f"ip_guard: ok ({len(paths)} file{extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
