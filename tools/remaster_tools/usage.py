"""Usage census: which assets the game uses, could use (only in commented-out script lines) or never
uses, before any paid or long processing. Also the candidates for an "extended" mode: commented
blocks and branches that wait on a flag nobody sets.

The script syntax is a small profile (JSON), because every engine comments differently:
  {"line_comment": ["#", "//"],          prefixes at the start of a line (after spaces)
   "inline_comment": [";"],              anywhere in the line (rest of the line is a comment)
   "line_blocks": [["[", "]"]],          a line starting with open ... a line starting with close
   "blocks": [["/*", "*/"]],             substring blocks, may span lines
   "extensions": [".scr", ".loc"],       script files to read (empty = every text file)
   "encoding": "cp850",
   "string_quotes": ["\""],             comment markers inside these quotes are text, not comments
   "match_stem": true,                   also count the name without extension (false: exact names only)
   "strict_ext": {"sfx": ".sfx"},        kind -> the name counts only when written with that extension
   "flag_set": "\\b(?:SET|TOGGLE)\\s+(\\w+)",   optional regexes, group 1 = flag name
   "flag_need": "\\b(?:FLAGS|IF)\\s+(\\w+)"}
"""
import csv
import hashlib
import json
import os
import re

DEFAULT_SYNTAX = {"line_comment": ["#", "//"], "inline_comment": [], "line_blocks": [], "blocks": [["/*", "*/"]],
                  "extensions": [], "encoding": "utf-8", "strict_ext": {}, "flag_set": "", "flag_need": "",
                  "string_quotes": ['"'], "match_stem": True}


def _find(rest, token, quotes):
    """Position of token outside quoted strings, -1 if absent."""
    q = None
    for i, ch in enumerate(rest):
        if q:
            if ch == q:
                q = None
        elif ch in quotes:
            q = ch
        elif rest.startswith(token, i):
            return i
    return -1
TOKEN = re.compile(r"[A-Za-z0-9_\-&$.]+")
PRIORITY = {"used": 0, "commented": 1, "unused": 2}
MIN_SFX_SECONDS = 0.5      # generated effects shorter than this come out padded or truncated


def load_syntax(path=None):
    syn = dict(DEFAULT_SYNTAX)
    if path:
        with open(path, encoding="utf-8") as f:
            syn.update(json.load(f))
    return syn


def split_lines(text, syn):
    """Yield (line_number, live_part, commented_part) for every line of a script."""
    lb_open = tuple(o for o, _ in syn["line_blocks"])
    in_line_block = in_block = None
    for n, line in enumerate(text.splitlines(), 1):
        s = line.lstrip()
        if in_line_block is None and in_block is None and lb_open and s.startswith(lb_open):
            op, cl = next((op, cl) for op, cl in syn["line_blocks"] if s.startswith(op))
            if cl not in s[len(op):]:          # opened and closed on the same line: only that line
                in_line_block = cl
            yield n, "", line
            continue
        if in_line_block is not None:
            if s.startswith(in_line_block):
                in_line_block = None
            yield n, "", line
            continue
        live, dead, rest = [], [], line
        while rest:
            if in_block is not None:
                i = rest.find(in_block)
                if i < 0:
                    dead.append(rest)
                    break
                dead.append(rest[:i + len(in_block)])
                rest, in_block = rest[i + len(in_block):], None
                continue
            if syn["line_comment"] and rest.lstrip().startswith(tuple(syn["line_comment"])):
                dead.append(rest)
                break
            qs = tuple(syn.get("string_quotes") or ())
            cut = [(_find(rest, op, qs), op, cl) for op, cl in syn["blocks"]]
            cut += [(_find(rest, c, qs), c, None) for c in syn["inline_comment"]]
            cut = [c for c in cut if c[0] >= 0]
            if not cut:
                live.append(rest)
                break
            i, op, cl = min(cut)
            live.append(rest[:i])
            if cl is None:
                dead.append(rest[i:])
                break
            dead.append(op)
            rest, in_block = rest[i + len(op):], cl
        yield n, "".join(live), "".join(dead)


def scan_scripts(script_dir, syn):
    """Every script line split into live and commented text: [(file, line, live, commented)]."""
    exts = tuple(e.lower() for e in syn["extensions"])
    rows = []
    for root, _, files in os.walk(script_dir):
        for fn in sorted(files):
            if exts and not fn.lower().endswith(exts):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, encoding=syn["encoding"], errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            if "\0" in text[:4096]:
                continue
            rel = os.path.relpath(p, script_dir)
            rows.extend((rel, n, live, dead) for n, live, dead in split_lines(text, syn))
    return rows


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def list_assets(asset_dir=None, asset_list=None, kinds=None):
    """Assets as dicts {name, stem, ext, kind, path}. kinds: {ext: kind} (default: the extension)."""
    out = []
    if asset_dir:
        for root, _, files in os.walk(asset_dir):
            for fn in sorted(files):
                stem, ext = os.path.splitext(fn)
                e = ext.lower()
                out.append({"name": fn, "stem": stem.lower(), "ext": e,
                            "kind": (kinds or {}).get(e, e.lstrip(".") or "file"),
                            "path": os.path.join(root, fn)})
    if asset_list:
        with open(asset_list, encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t" if asset_list.endswith(".tsv") else ","):
                name = row.get("name") or row.get("asset") or row.get("key")
                if not name:
                    continue
                stem, ext = os.path.splitext(name)
                out.append({"name": name, "stem": stem.lower(), "ext": ext.lower(),
                            "kind": row.get("kind") or ext.lstrip(".").lower() or "file", "path": row.get("path", "")})
    return out


def census(script_dir, asset_dir=None, asset_list=None, syntax=None, loaded_log=None, out_csv=None,
           candidates_tsv=None, kinds=None):
    """Status of every asset: used (named in a live line), commented (only in commented lines: usable by
    re-enabling the line, the "extended" candidates), unused. `loaded_log`: a runtime log (test driver,
    engine debug output) whose tokens prove the asset was really loaded -> verified."""
    syn = load_syntax(syntax) if isinstance(syntax, (str, type(None))) else {**DEFAULT_SYNTAX, **syntax}
    rows = scan_scripts(script_dir, syn)
    live_refs, dead_refs = {}, {}
    for rel, n, live, dead in rows:
        for txt, refs in ((live, live_refs), (dead, dead_refs)):
            for t in TOKEN.findall(txt.lower()):
                t = t.strip(".")
                if t:
                    refs.setdefault(t, []).append(f"{rel}:{n}")
    loaded = set()
    if loaded_log:
        with open(loaded_log, encoding="utf-8", errors="replace") as f:
            loaded = {t.strip(".") for t in TOKEN.findall(f.read().lower())}
    assets = list_assets(asset_dir, asset_list, kinds)
    by_md5 = {}
    res = []
    strict = {k: v.lower() for k, v in syn["strict_ext"].items()}
    for a in assets:
        names = [a["name"].lower()]
        if a["kind"] not in strict and syn.get("match_stem", True):
            names.append(a["stem"])
        else:
            names = [a["stem"] + strict[a["kind"]], a["name"].lower()]
        live = [r for nm in dict.fromkeys(names) for r in live_refs.get(nm, [])]
        dead = [r for nm in dict.fromkeys(names) for r in dead_refs.get(nm, [])]
        status = "used" if live else "commented" if dead else "unused"
        dup = ""
        if a["path"] and os.path.isfile(a["path"]):
            h = _md5(a["path"])
            dup = by_md5.get(h, "")
            by_md5.setdefault(h, a["name"])
        res.append({"name": a["name"], "kind": a["kind"], "status": status,
                    "verified": int(any(nm in loaded for nm in names)),
                    "refs": " ".join((live or dead)[:3]), "duplicate_of": dup})
    if out_csv:
        os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
        with open(out_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["name", "kind", "status", "verified", "refs", "duplicate_of"])
            w.writeheader()
            w.writerows(res)
    cand = candidates(rows, syn, {a["name"].lower() for a in assets} | {a["stem"] for a in assets})
    if candidates_tsv:
        os.makedirs(os.path.dirname(os.path.abspath(candidates_tsv)), exist_ok=True)
        with open(candidates_tsv, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["where", "kind", "assets", "text"])
            for c in cand:
                w.writerow([c["where"], c["kind"], " ".join(c["assets"]), c["text"]])
    summary = {}
    for r in res:
        s = summary.setdefault(r["kind"], {"used": 0, "commented": 0, "unused": 0, "verified": 0, "duplicates": 0})
        s[r["status"]] += 1
        s["verified"] += r["verified"]
        s["duplicates"] += bool(r["duplicate_of"])
    return {"assets": len(res), "per_kind": summary, "extended_candidates": len(cand),
            "dead_flag_branches": sum(1 for c in cand if c["kind"] == "flag-never-set"),
            "csv": out_csv, "candidates": candidates_tsv}


def candidates(rows, syn, asset_names):
    """Commented runs of lines (grouped per file) and live lines that wait on a flag nobody sets."""
    out, cur = [], None
    for rel, n, live, dead in rows:
        if dead.strip() and not live.strip():
            if cur and cur["file"] == rel and cur["end"] == n - 1:
                cur["end"], cur["lines"] = n, cur["lines"] + [dead.strip()]
            else:
                cur = {"file": rel, "start": n, "end": n, "lines": [dead.strip()]}
                out.append(cur)
        else:
            cur = None
    res = []
    for c in out:
        toks = {t.strip(".") for ln in c["lines"] for t in TOKEN.findall(ln.lower())}
        res.append({"where": f"{c['file']}:{c['start']}-{c['end']}", "kind": "commented",
                    "assets": sorted(toks & asset_names), "text": " / ".join(c["lines"])[:200]})
    if syn.get("flag_set") and syn.get("flag_need"):
        fs, fn = re.compile(syn["flag_set"], re.I), re.compile(syn["flag_need"], re.I)
        set_ = {m.group(1).lower() for _, _, live, _ in rows for m in fs.finditer(live)}
        for rel, n, live, _ in rows:
            for m in fn.finditer(live):
                if m.group(1).lower() not in set_:
                    res.append({"where": f"{rel}:{n}", "kind": "flag-never-set", "assets": [],
                                "text": f"{m.group(1)}: {live.strip()[:160]}"})
    return res


def read_census(path):
    with open(path, encoding="utf-8") as f:
        return {r["name"].lower(): r for r in csv.DictReader(f)}


def gate(census_csv, batch_path, allow=("used",), min_sfx_seconds=MIN_SFX_SECONDS):
    """Check a generation batch against the census before spending. Blocks every item whose status is not
    in `allow` (default: only used; add "commented" for the extended mode), unknown or ambiguous names.
    Warns about effects (kind/type "sfx") shorter than the generator minimum and output names written
    twice (same effect at two playback rates needs <name>_<rate>). Batch: a list of items or {"items": [...]}."""
    cen = read_census(census_csv)
    with open(batch_path, encoding="utf-8") as f:
        batch = json.load(f)
    items = batch.get("items") if isinstance(batch, dict) else batch
    if not isinstance(items, list) or not all(isinstance(it, dict) for it in items):
        raise ValueError("lotto: serve una lista di oggetti o {\"items\": [...]}")
    by_stem = {}
    for k in cen:
        by_stem.setdefault(os.path.splitext(k)[0], []).append(k)
    blocked, warnings, seen = [], [], {}
    per = {"used": 0, "commented": 0, "unused": 0, "unknown": 0, "ambiguous": 0}
    for it in items:
        name = str(it.get("asset") or it.get("name") or it.get("key") or "")
        src = name.lower()
        st, status = cen.get(src), None
        if st is None:
            cands = by_stem.get(os.path.splitext(src)[0], [])
            if len(cands) == 1:
                st = cen[cands[0]]
            elif cands:
                status = "ambiguous"
        status = status or (st["status"] if st else "unknown")
        per[status] += 1
        if status not in allow:
            blocked.append({"item": name, "status": status})
        outname = str(it.get("out") or it.get("output") or name)
        if outname in seen:
            warnings.append(f"{outname}: nome d'uscita ripetuto (stesso suono a frequenze diverse? usa <nome>_<freq>)")
        seen[outname] = 1
        d = it.get("duration", it.get("seconds"))
        if d is not None and (it.get("kind") or it.get("type")) == "sfx":
            try:
                if float(d) < min_sfx_seconds:
                    warnings.append(f"{name}: {float(d):.2f} s < {min_sfx_seconds} s: genera {min_sfx_seconds} s e taglia dopo")
            except (TypeError, ValueError):
                warnings.append(f"{name}: durata non numerica ({d!r})")
    return {"ok": not blocked, "per_status": per, "blocked": blocked, "warnings": warnings, "allow": list(allow)}
