"""Script catalogue, corrected/translated text files, width and glyph checks.

Text dump of the Remaster Layer (`remaster_dump_text=<file>`): JSON lines
  {"hex": "<raw bytes in the game code page>", "kind": "balloon|answer|label|menu|subtitle|comment",
   "location": "...", "speaker": "...", "box_w": 240}
"""
import csv
import json
import os
import re

from . import font as fontmod
from .keys import text_key

FIELDS = ["key", "lang", "source", "text", "kind", "location", "speaker", "box_w", "status", "note"]

# Italian accents written as apostrophes in many DOS games (e' piu' perche')
_KEEP = {"po", "be", "mo", "to", "va", "fa", "sta", "da", "di", "de"}
_ACUTE = {"perche", "poiche", "affinche", "benche", "giacche", "finche", "cosicche", "nonche", "sicche", "purche", "ne", "se"}
_GRAVE = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù", "E": "È", "A": "À", "O": "Ò"}


def italian_accents(s: str) -> str:
    def fix(m):
        word, vowel = m.group(1), m.group(2)
        w = (word + vowel).lower()
        if w in _KEEP:
            return m.group(0)
        if vowel in "eE" and w in _ACUTE:
            return word + ("é" if vowel == "e" else "É")
        return word + _GRAVE.get(vowel, vowel + "'")
    return re.sub(r"\b([A-Za-z]*)([aeiouAEIOU])'(?=[\s.,!?;:\"\\)]|$)", fix, s)


def read_dump(path, codepage="cp850"):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            raw = bytes.fromhex(d["hex"])
            d["text"] = raw.decode(codepage, errors="replace")
            d["key"] = text_key(raw)
            rows.append(d)
    return rows


def catalog(dump_path, lang, out_path, codepage="cp850"):
    seen = {}
    for d in read_dump(dump_path, codepage):
        if d["key"] in seen:
            continue
        seen[d["key"]] = {"key": d["key"], "lang": lang, "source": d["text"], "text": "",
                          "kind": d.get("kind", ""), "location": d.get("location", ""),
                          "speaker": d.get("speaker", ""), "box_w": d.get("box_w", ""),
                          "status": "todo", "note": ""}
    write_catalog(out_path, list(seen.values()))
    return {"lines": len(seen), "chars": sum(len(r["source"]) for r in seen.values())}


def write_catalog(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_catalog(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def export_lang(catalog_path, out_path, use_source_if_empty=False):
    """Catalogue -> remaster/text/<lang>.tsv ("<key>\\t<text>")."""
    n = 0
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# remaster text: <textKey>\\t<UTF-8 text>\n")
        for r in read_catalog(catalog_path):
            t = r.get("text") or (r["source"] if use_source_if_empty else "")
            if not t:
                continue
            f.write(f"{r['key']}\t{t}\n")
            n += 1
    return {"written": n}


def check(catalog_path, font_dat, codepage="cp850", tolerance=1.10):
    info = fontmod.read(font_dat)
    problems = []
    for r in read_catalog(catalog_path):
        t = r.get("text") or r["source"]
        try:
            b = t.encode(codepage)
        except UnicodeEncodeError as e:
            problems.append({"key": r["key"], "issue": "carattere fuori codepage", "detail": str(e)[:80]})
            continue
        missing = sorted({chr(c) if c > 31 else hex(c) for c in b if info["adv"][c] == 0 and c != 32})
        if missing:
            problems.append({"key": r["key"], "issue": "glifi mancanti", "detail": "".join(missing)})
        box = r.get("box_w")
        if box:
            longest = max((fontmod.text_width(info, line.encode(codepage)) for line in t.split("\\n")), default=0)
            if longest > float(box) * tolerance:
                problems.append({"key": r["key"], "issue": "troppo lungo", "detail": f"{longest:.0f}px > {box}px"})
    return problems


def glyphs(paths):
    used = {}
    for p in paths:
        rows = read_catalog(p) if p.endswith(".tsv") and "key\tlang" in open(p, encoding="utf-8").readline() else None
        texts = [r.get("text") or r["source"] for r in rows] if rows else \
            [l.split("\t", 1)[1] for l in open(p, encoding="utf-8") if "\t" in l and not l.startswith("#")]
        chars = sorted({c for t in texts for c in t if not c.isspace()})
        used[os.path.basename(p)] = "".join(chars)
    return used
