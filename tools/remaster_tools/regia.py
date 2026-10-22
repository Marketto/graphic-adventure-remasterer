"""Per-line direction of the dub: a context sheet for every line and a proposed audio tag.

The tone of a line comes from its text and its context (scene, lines before and after, who is
spoken to, the character's sheet), never from a fixed tag per character. The heuristics here
only propose a starting point from punctuation and keywords; the voice director reviews the
`tag` column, then `voice generate --direction regia.tsv` reads it.

Rules (JSON, per language, merged over the defaults):
  {"it": {"cps": 14.0,
          "punctuation": [{"re": "\\\\?\\\\s*$", "tag": "[curious]", "why": "domanda"}],
          "keywords": {"[sad]": ["purtroppo", "mi dispiace"]},
          "energetic": ["[excited]", "[shouting]"]}}
"""
import csv
import json
import os
import re

# conservative defaults: at most one sober tag per line, none when nothing stands out
DEFAULT_RULES = {
    "*": {
        "cps": 14.0,   # characters per second of a natural delivery (estimate of the duration)
        "punctuation": [
            {"re": r"!{2,}\s*$", "tag": "[shouting]", "why": "punti esclamativi multipli"},
            {"re": r"\?!|!\?", "tag": "[surprised]", "why": "domanda esclamativa"},
            {"re": r"(\.\.\.|…)\s*$", "tag": "[hesitant]", "why": "puntini in chiusura"},
            {"re": r"^\s*(\.\.\.|…)", "tag": "[thoughtful]", "why": "puntini in apertura"},
            {"re": r"!\s*$", "tag": "[excited]", "why": "esclamazione"},
            {"re": r"\?\s*$", "tag": "[curious]", "why": "domanda"},
        ],
        "keywords": {},
        # tags that raise energy or register: avoided for deep voices unless the director wants them
        "energetic": ["[shouting]", "[excited]", "[surprised]", "[laughs]", "[cheerful]"],
    },
    "it": {
        "keywords": {
            "[sad]": ["purtroppo", "mi dispiace", "peccato", "addio"],
            "[sarcastic]": ["ma certo", "come no", "ovviamente", "che sorpresa"],
            "[whispers]": [],
            "[laughs]": ["ah ah", "ahah", "eh eh"],
            "[angry]": ["basta", "maledizione", "accidenti"],
        },
    },
    "en": {
        "keywords": {
            "[sad]": ["unfortunately", "i'm sorry", "too bad", "goodbye"],
            "[sarcastic]": ["oh sure", "of course", "obviously", "what a surprise"],
            "[laughs]": ["ha ha", "haha"],
            "[angry]": ["enough", "damn"],
        },
    },
}

TAG_RE = re.compile(r"\[[^\]]*\]")
COLUMNS = ["key", "speaker", "scene", "kind", "text", "before", "after", "listener",
           "est_s", "limit_s", "over_limit", "tag", "why", "recita"]


def load_rules(lang, path=None):
    """Defaults for every language, then the language, then the user's file (same layout)."""
    layers = [DEFAULT_RULES["*"], DEFAULT_RULES.get(lang, {})]
    if path:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        layers += [user.get("*", {}), user.get(lang, {})]
    rules = {"cps": 14.0, "punctuation": [], "keywords": {}, "energetic": []}
    for layer in layers:
        for k, v in layer.items():
            if k == "keywords":
                rules["keywords"].update(v)
            else:
                rules[k] = v
    return rules


def count_tags(tag):
    return len(TAG_RE.findall(tag or ""))


def propose(text, rules, deep=False):
    """(tag, why) for one line: keywords first (they say more than punctuation), then punctuation.
    deep: the speaker has a deep voice, energetic tags are not proposed."""
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    candidates = []
    for tag, words in rules["keywords"].items():
        for w in words:
            if re.search(r"(?<!\w)" + re.escape(w.lower()) + r"(?!\w)", low):
                candidates.append((tag, f"parola chiave «{w}»"))
                break
    for p in rules["punctuation"]:
        if re.search(p["re"], text):
            candidates.append((p["tag"], p.get("why", "punteggiatura")))
    skipped = None
    for tag, why in candidates:
        if deep and tag in rules["energetic"]:
            skipped = skipped or tag
            continue
        return tag, why
    if skipped:
        return "", f"{skipped} evitato (voce grave): decidi dal contesto"
    return "", ""


def _limit(row):
    for k in ("limit_s", "max_s", "durata_max"):
        try:
            return float(row.get(k) or "")
        except ValueError:
            continue
    return None


def _line(r):
    return f"{r['speaker']}: {r['text']}"


def direct(script_path, out_path, context=2, lang="it", rules_path=None, cast_path=None, keep_tags=True):
    """Context sheet + proposed tag for every line of the dubbing script (TSV of `voice script`).

    context: lines before/after in the same scene (any speaker). cast_path: cast.json, whose
    entries with "register": "deep" (or "grave": true) never get energetic tags proposed.
    keep_tags: a tag already written in the script (by the director) is kept and not replaced."""
    rules = load_rules(lang, rules_path)
    deep = set()
    if cast_path:
        with open(cast_path, encoding="utf-8") as f:
            cast = json.load(f)
        cast = cast.get("voci", cast)
        deep = {k for k, c in cast.items() if isinstance(c, dict)
                and (c.get("grave") or str(c.get("register", c.get("registro", ""))).lower() in ("deep", "grave"))}
    with open(script_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    out, stats = [], {"lines": 0, "proposed": 0, "kept": 0, "empty": 0, "over_limit": 0, "multi_tag": []}
    for i, r in enumerate(rows):
        scene = r.get("context", "")
        same = [j for j in range(len(rows)) if rows[j].get("context", "") == scene]
        pos = same.index(i)
        before = [rows[j] for j in same[max(0, pos - context):pos]] if context else []
        after = [rows[j] for j in same[pos + 1:pos + 1 + context]] if context else []
        listener = next((x["speaker"] for x in reversed(before) if x["speaker"] != r["speaker"]), None) \
            or next((x["speaker"] for x in after if x["speaker"] != r["speaker"]), "")
        said = r.get("recita") or r["text"]
        est = round(len(said) / rules["cps"], 1)
        lim = _limit(r)
        over = lim is not None and est > lim
        old = (r.get("tag") or "").strip()
        if old and keep_tags:
            tag, why = old, "regia esistente"
            stats["kept"] += 1
        else:
            tag, why = propose(said, rules, r["speaker"] in deep)
            stats["proposed" if tag else "empty"] += 1
        if count_tags(tag) > 1:
            stats["multi_tag"].append(r["key"])
            why = (why + "; " if why else "") + "più di un tag: tienine uno"
        stats["lines"] += 1
        stats["over_limit"] += over
        out.append({"key": r["key"], "speaker": r["speaker"], "scene": scene, "kind": r.get("kind", ""),
                    "text": r["text"], "before": " | ".join(_line(x) for x in before),
                    "after": " | ".join(_line(x) for x in after), "listener": listener,
                    "est_s": est, "limit_s": "" if lim is None else lim, "over_limit": "sì" if over else "",
                    "tag": tag, "why": why, "recita": r.get("recita", "")})
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter="\t")
        w.writeheader()
        w.writerows(out)
    stats["out"] = out_path
    return stats


def read_direction(path):
    """{key: {"tag", "recita"}} from a reviewed regia.tsv (empty recita = keep the script's)."""
    with open(path, encoding="utf-8", newline="") as f:
        return {r["key"]: {"tag": (r.get("tag") or "").strip(), "recita": (r.get("recita") or "").strip()}
                for r in csv.DictReader(f, delimiter="\t")}
