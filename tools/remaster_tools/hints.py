"""In-game hints (key H): file format, parser and validator.

File `hint/<lang>.txt`, UTF-8, objectives in game order, grouped by part:

    @parte 1
    obiettivo: Entrare in biblioteca
    fatto: LF:atrio:porta_aperta | obj:chiave_usata
    situazione: Sei nell'atrio, la porta della biblioteca è chiusa.
    indizio: Il custode ha sempre qualcosa in tasca.
    soluzione: Parla col custode, chiedigli della chiave, usala sulla porta.

The engine shows the first objective of the current part whose `fatto` is false.
Conditions: terms separated by spaces are AND; `|` is OR and binds tighter (`A | B C` means
(A or B) and C); `!` negates a term. Terms:
    <flag>                 global flag of the part
    LF:<scene>:<flag>      local flag of a scene (kept per scene, also in saves)
    obj:<item>             item in the current character's inventory
    <counter>><n>  <counter><<n>  <counter>=<n>
    room:<scene>           current scene (not monotone: use only together with other terms)
    seen:<scene>           scene already visited
    sempre / mai
Conditions must be MONOTONE: once true they stay true, otherwise the hint goes back.
"""
import json
import os
import re

FIELDS = ("obiettivo", "fatto", "situazione", "indizio", "soluzione")
TERM = re.compile(r"^(sempre|mai|LF:[^:\s]+:[^:\s]+|obj:\S+|room:\S+|seen:\S+|[A-Za-z_][\w.]*[<>=]-?\d+|[A-Za-z_][\w.]*)$")


def parse(path_or_text):
    text = path_or_text
    if "\n" not in path_or_text and os.path.exists(path_or_text):
        with open(path_or_text, encoding="utf-8") as f:
            text = f.read()
    parts, problems = {}, []
    part, cur = None, None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@parte"):
            part = line.split(None, 1)[1].strip() if " " in line else ""
            parts.setdefault(part, [])
            cur = None
            continue
        if ":" not in line:
            problems.append(f"riga {n}: manca «campo:»")
            continue
        key, val = line.split(":", 1)
        key, val = key.strip().lower(), val.strip()
        if key not in FIELDS:
            problems.append(f"riga {n}: campo sconosciuto «{key}»")
            continue
        if part is None:
            problems.append(f"riga {n}: obiettivo fuori da una sezione @parte")
            part = ""
            parts.setdefault(part, [])
        if key == "obiettivo":
            cur = {"line": n, "obiettivo": val}
            parts[part].append(cur)
        elif cur is None:
            problems.append(f"riga {n}: «{key}» prima di «obiettivo»")
        else:
            if key in cur:
                problems.append(f"riga {n}: «{key}» ripetuto nell'obiettivo «{cur['obiettivo']}»")
            cur[key] = val
    return parts, problems


def parse_condition(cond):
    """-> list of AND groups, each a list of (negated, term) alternatives."""
    groups = []
    tokens = cond.replace("|", " | ").split()
    cur = []
    expect_alt = False
    for tok in tokens:
        if tok == "|":
            if not cur or expect_alt:
                raise ValueError("«|» senza termine prima")
            expect_alt = True
            continue
        neg = tok.startswith("!")
        term = tok[1:] if neg else tok
        if not TERM.match(term):
            raise ValueError(f"termine non valido «{tok}»")
        if expect_alt:
            cur.append((neg, term))
            expect_alt = False
        else:
            if cur:
                groups.append(cur)
            cur = [(neg, term)]
    if expect_alt:
        raise ValueError("«|» senza termine dopo")
    if cur:
        groups.append(cur)
    if not groups:
        raise ValueError("condizione vuota")
    return groups


def _vocab_check(term, vocab):
    if not vocab:
        return None
    if term in ("sempre", "mai"):
        return None
    if term.startswith("LF:"):
        _lf, scene, flag = term.split(":")
        if vocab.get("scenes") and scene not in vocab["scenes"]:
            return f"scena sconosciuta «{scene}»"
        local = vocab.get("local_flags", {}).get(scene)
        if local is not None and flag not in local:
            return f"flag locale sconosciuto «{flag}» in «{scene}»"
        return None
    for prefix, key in (("obj:", "items"), ("room:", "scenes"), ("seen:", "scenes")):
        if term.startswith(prefix):
            name = term[len(prefix):]
            return None if not vocab.get(key) or name in vocab[key] else f"{key[:-1]} sconosciuto «{name}»"
    m = re.match(r"^([A-Za-z_][\w.]*)[<>=]-?\d+$", term)
    if m:
        return None if not vocab.get("counters") or m.group(1) in vocab["counters"] else f"contatore sconosciuto «{m.group(1)}»"
    return None if not vocab.get("flags") or term in vocab["flags"] else f"flag sconosciuto «{term}»"


def validate(paths, vocab_path=None):
    """Checks every file; with several languages also that they share objectives and conditions.
    vocab (optional, from the engine dump): {"flags", "items", "scenes", "counters", "local_flags": {scene: []}}"""
    vocab = None
    if vocab_path:
        with open(vocab_path, encoding="utf-8") as f:
            vocab = json.load(f)
    report, ref = {}, None
    for p in paths:
        parts, problems = parse(p)
        warnings = []
        for part, objs in parts.items():
            if not objs:
                warnings.append(f"parte {part}: nessun obiettivo")
            for o in objs:
                where = f"riga {o['line']} «{o['obiettivo']}»"
                for f in FIELDS[1:]:
                    if not o.get(f):
                        problems.append(f"{where}: manca «{f}»")
                if o.get("fatto"):
                    try:
                        groups = parse_condition(o["fatto"])
                    except ValueError as e:
                        problems.append(f"{where}: {e}")
                        groups = []
                    for g in groups:
                        for neg, term in g:
                            bad = _vocab_check(term, vocab)
                            if bad:
                                problems.append(f"{where}: {bad}")
                        if len(g) == 1 and not g[0][0] and g[0][1].startswith("obj:"):
                            warnings.append(f"{where}: «{g[0][1]}» da solo non è monotono se l'oggetto poi si "
                                            "consuma: mettilo in OR con ciò che si ottiene dopo")
                        if any(neg for neg, _t in g):
                            warnings.append(f"{where}: una negazione non è monotona di solito: controlla")
                        if all(t.startswith("room:") for _n, t in g):
                            warnings.append(f"{where}: «room:» da solo non è monotono")
                if o.get("indizio") and o.get("soluzione") and o["indizio"].strip() == o["soluzione"].strip():
                    warnings.append(f"{where}: indizio uguale alla soluzione")
        shape = {part: [o.get("fatto", "") for o in objs] for part, objs in parts.items()}
        if ref is None:
            ref = (p, shape)
        elif shape != ref[1]:
            problems.append(f"obiettivi o condizioni diversi da {ref[0]}: le lingue devono avere gli stessi "
                            "obiettivi, nello stesso ordine, con le stesse condizioni (si traduce solo il testo)")
        report[p] = {"parts": {k: len(v) for k, v in parts.items()}, "problems": problems, "warnings": warnings}
    return {"ok": all(not r["problems"] for r in report.values()), "files": report}
