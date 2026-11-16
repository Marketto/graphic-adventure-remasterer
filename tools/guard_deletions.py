#!/usr/bin/env python3
"""Refuse a commit that deletes many files or large/binary ones (files vanished from outside the
session end up staged by `git add -A`). Standalone: also copied into the private game repository.

  python3 guard_deletions.py            # checks the staged deletions; exit 1 if blocked
  ALLOW_DELETIONS=1 git commit ...      # deliberate deletion (say so to the user first); never --no-verify
Limits (environment): GUARD_MAX_FILES=20, GUARD_MAX_BYTES=1000000, GUARD_MAX_BINARY=100000,
GUARD_PROTECTED="assets/" (comma-separated path prefixes that are never deleted silently).
"""
import os
import subprocess
import sys


def _git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def staged_deletions():
    # --no-renames: a mass move counts as deletions too
    return [p for p in _git("diff", "--cached", "--no-renames", "--name-only", "--diff-filter=D", "-z").split("\0") if p]


def problems(paths, size_of, is_binary, max_files=20, max_bytes=1_000_000, max_binary=100_000, protected=()):
    out = []
    if len(paths) > max_files:
        out.append(f"{len(paths)} file cancellati (limite {max_files})")
    for p in paths:
        n = size_of(p)
        if any(p.startswith(pr) for pr in protected):
            out.append(f"{p}: cartella protetta")
        elif n >= max_bytes:
            out.append(f"{p}: {n} byte")
        elif n >= max_binary and is_binary(p):
            out.append(f"{p}: binario di {n} byte")
    return out


def main():
    if os.environ.get("ALLOW_DELETIONS") == "1" or os.environ.get("CONSENTI_CANCELLAZIONI") == "1":
        return 0
    env = os.environ.get
    try:
        paths = staged_deletions()
    except RuntimeError as e:
        print(f"guard_deletions: {e}")
        return 1
    if not paths:
        return 0

    def size_of(p):
        try:
            return int(_git("cat-file", "-s", f"HEAD:{p}").strip() or 0)
        except (RuntimeError, ValueError):
            return 0

    def is_binary(p):
        data = subprocess.run(["git", "show", f"HEAD:{p}"], capture_output=True).stdout[:8192]
        return b"\0" in data

    prot = tuple(x for x in env("GUARD_PROTECTED", "assets/").split(",") if x)
    found = problems(paths, size_of, is_binary, int(env("GUARD_MAX_FILES", 20)), int(env("GUARD_MAX_BYTES", 1_000_000)),
                     int(env("GUARD_MAX_BINARY", 100_000)), prot)
    if found:
        print("Cancellazioni bloccate (file spariti da fuori? ripristinali con `git restore --staged --worktree`):")
        for f in found:
            print("  " + f)
        print("Se la cancellazione è voluta, dillo all'utente e ripeti con ALLOW_DELETIONS=1.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
