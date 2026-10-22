"""remaster.json: the state of a remaster project (decisions, phase, paths)."""
import datetime as _dt
import json
import os

FILE = "remaster.json"

PHASES = ["intake", "analysis", "engine", "assets", "qa", "release", "done"]

# Everything that is free is ON by default (the user can remove items from the plan, he does
# not pick them one by one); the paid parts (fal.ai, ElevenLabs) stay None until the analysis
# has counted what they would cost and the user has answered with the quote in front of him.
DEFAULT = {
    "schema": 2,
    "phase": "intake",
    "game": {"title": None, "year": None, "developer": None, "publisher": None,
             "platform": None, "version": None, "languages_original": []},
    "engine": {"id": None, "runtime": None, "support": None, "notes": None,
               "base_commit": None, "patchable": True, "smooth_controls": True,
               # True once the Remaster Layer is hooked into this engine (dump, keys, HD, viewport)
               "layer_hooked": None},
    # the film, series or animated work the game is based on (checked in phase 1, sources cited);
    # characters: the recognisable ones, with the original performer and, per target language,
    # the dubbing voice of the time the game came out. imitate_voice: None = not asked yet,
    # asked only when the dub is chosen. Data only in the private repository of the game.
    "source_work": {"checked": False, "type": None, "title": None, "year": None, "sources": [],
                    "characters": []},
    "existing_work": [],
    "reuse_existing_work": True,
    "graphics": {"enabled": True, "parts": ["backgrounds", "sprites", "fonts", "ui", "cursors"],
                 "scale": 3,
                 # stretch 1.0 = square pixels; another value only if the game was made for a
                 # display that stretched its pixels (decided in the analysis, see platforms.py)
                 # decided_by: "auto" (`widescreen aspect-auto`: table and measured shapes agree),
                 # "ask" (in doubt: asked with the comparison sheet), "user" (answered)
                 "pixel_aspect": {"stretch": None, "reason": None, "decided_by": None},
                 # fill: local methods (LaMa 1x + quilting + recipes); fal_ai: paid outpainting,
                 # asked only after the analysis with the quote (None = not asked yet)
                 "widescreen": {"enabled": True, "aspect": "16:9", "fill": "local", "fal_ai": None},
                 "framerate": {"enabled": True, "target": 60}},
    "ui_theme": {"enabled": True},
    # user: the language of the user (asked in phase 0); translate: None = not decided yet, the
    # default proposal is the user's language when the game does not exist in it
    "languages": {"user": None, "requested": [], "available": {}, "translate": None,
                  "existing_translations": []},
    "audio": {"enabled": True, "music": True, "sfx": True, "restore_original_voices": True,
              # stage 1: normalization per group; stage 2: levels of the groups in the mix (LUFS)
              "mix": {"voice": -18.0, "sfx": -16.0, "music": -25.0}},
    "extras": {"manual": True, "hints": True},
    # spending cap for the whole project (on top of the quote per batch) and the ledger
    "budget": {"cap_usd": None, "cap_credits": None, "spent": []},
    # enabled: decided after the analysis (None = not asked); existing: language → True when the
    # game already has a dub in that language (then ElevenLabs is not proposed for it)
    "voice": {"enabled": None, "provider": "elevenlabs", "license_confirmed": False,
              "languages": [], "existing": {}},
    "platforms": ["windows", "linux", "macos", "android", "web"],
    "distribution": {"mode": "recipe", "rights_confirmed": False},
    "toggle_key": "F8",
    "paths": {"game_files": None, "workdir": "."},
    # analysis: path of the counts (plan estimate input) once phase 1 is done
    "analysis": {"done": False, "counts": None},
    # the plan proposed in phase 1c and the sub-sessions that carry it out
    "plan": {"approved": None, "token_budget": 200000, "token_hard_limit": 250000},
    "work_packages": [],
    "decisions": [],
}

PACKAGE_STATES = ["pending", "running", "done", "failed", "stopped"]


def path(workdir="."):
    return os.path.join(workdir, FILE)


def load(workdir="."):
    p = path(workdir)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(data, workdir="."):
    os.makedirs(workdir, exist_ok=True)
    p = path(workdir)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, p)


def init(title=None, workdir=".", force=False):
    if load(workdir) is not None and not force:
        raise FileExistsError(f"{path(workdir)} esiste già (usa --force per ricrearlo)")
    data = json.loads(json.dumps(DEFAULT))
    data["game"]["title"] = title
    data["paths"]["workdir"] = os.path.abspath(workdir)
    data["created"] = _now()
    save(data, workdir)
    return data


def parse_value(raw: str):
    """JSON when it parses (true, 3, ["it"], {...}), plain string otherwise."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def set_key(data, dotted: str, value):
    node = data
    parts = dotted.split(".")
    for p in parts[:-1]:
        if not isinstance(node.get(p), dict):
            node[p] = {}
        node = node[p]
    node[parts[-1]] = value
    return data


def get_key(data, dotted: str):
    node = data
    for p in dotted.split("."):
        if not isinstance(node, dict) or p not in node:
            raise KeyError(dotted)
        node = node[p]
    return node


def decide(data, what: str, why: str = ""):
    data.setdefault("decisions", []).append({"date": _now(), "decision": what, "why": why})
    return data


def spend(data, service: str, amount: float, unit: str = "usd", note: str = ""):
    """Record money or credits actually spent; returns the totals and whether a cap is passed."""
    unit = (unit or "").strip().lower()
    if unit not in ("usd", "credits"):
        raise ValueError(f"unità «{unit}» non valida: usd o credits")
    if amount < 0:
        raise ValueError("importo negativo")
    b = data.setdefault("budget", {"cap_usd": None, "cap_credits": None, "spent": []})
    b.setdefault("spent", []).append({"date": _now(), "service": service, "amount": float(amount),
                                      "unit": unit, "note": note})
    usd = sum(e["amount"] for e in b["spent"] if e["unit"] == "usd")
    cred = sum(e["amount"] for e in b["spent"] if e["unit"] == "credits")
    over = []
    if b.get("cap_usd") is not None and usd > b["cap_usd"]:
        over.append(f"speso {usd:.2f} $ oltre il tetto di {b['cap_usd']} $")
    if b.get("cap_credits") is not None and cred > b["cap_credits"]:
        over.append(f"usati {cred:.0f} crediti oltre il tetto di {b['cap_credits']}")
    return {"usd": round(usd, 2), "credits": round(cred), "over_cap": over}


def set_phase(data, phase: str):
    if phase not in PHASES:
        raise ValueError(f"fase sconosciuta: {phase} (valide: {', '.join(PHASES)})")
    data["phase"] = phase
    return decide(data, f"fase → {phase}")


_FAN = ("amatorial", "fan", "non ufficial", "unofficial", "community")
_OTHER_ED = ("floppy", "altra edizione", "other edition", "altra versione", "other version", "edizione diversa",
             "solo nella versione", "only in the")
_NO_VOICE = ("solo testi", "text only", "doppiaggio assente", "senza voci", "no voice", "no dub")


def language_status(value):
    """What `languages.available[lang]` really offers for the USER'S edition.

    The value is either a dict {"text": "official"|"fan"|None, "voice": bool,
    "edition": "same"|"other", "user_owns": bool} or a free description (then read with
    keywords: "amatoriale"/"fan" → fan text, "floppy"/"altra edizione" → official text only in
    another edition). Returns {"text", "voice", "edition", "user_owns", "usable"}, where usable
    means an official text in the user's own edition (nothing to translate)."""
    if isinstance(value, dict):
        st = {"text": value.get("text"), "voice": bool(value.get("voice")),
              "edition": value.get("edition") or "same", "user_owns": value.get("user_owns")}
    elif isinstance(value, str) and value.strip():
        v = value.lower()
        official = "ufficial" in v.replace("non ufficial", "") or "official" in v.replace("unofficial", "")
        fan = any(k in v for k in _FAN)
        st = {"text": "official" if official else ("fan" if fan else None),
              "voice": any(k in v for k in ("voc", "voice", "doppia", "dub", "parlat"))
              and not any(k in v for k in _NO_VOICE),
              "edition": "other" if any(k in v for k in _OTHER_ED) else "same", "user_owns": None}
    elif value:
        st = {"text": "official", "voice": False, "edition": "same", "user_owns": None}
    else:
        st = {"text": None, "voice": False, "edition": "same", "user_owns": None}
    st["usable"] = st["text"] == "official" and st["edition"] == "same"
    return st


def translation_plan(data):
    """{lang: "translate" | "import"} for the languages to bring into the game.

    `languages.translate` (when decided) wins; otherwise the user's language when the game does
    not really exist in it for his edition. "import": the official text exists in ANOTHER edition
    (e.g. a text-only release): import it from the user's copy of that edition and align it, then
    translate only the lines missing there. Fan translations are reused only with permission
    (`existing_work`), so they still count as "translate"."""
    lang = data.get("languages", {}) or {}
    avail = lang.get("available") or {}
    original = set(data.get("game", {}).get("languages_original") or [])
    wanted = lang.get("translate")
    if wanted is None:
        user = lang.get("user")
        wanted = [user] if user and user not in original and not language_status(avail.get(user)).get("usable") else []
    out = {}
    for code in wanted or []:
        st = language_status(avail.get(code))
        if st["usable"]:
            continue
        out[code] = "import" if (st["text"] == "official" and st["edition"] == "other"
                                 and st["user_owns"] is not False) else "translate"
    return out


def user_needs_translation(data):
    """True when the user's language is known and the game does not really exist in it for his
    edition (an official text only in another edition or a fan translation do not count)."""
    lang = data.get("languages", {})
    user = lang.get("user")
    if not user:
        return False
    if user in set(data.get("game", {}).get("languages_original") or []):
        return False
    return not language_status((lang.get("available") or {}).get(user))["usable"]


def needs_dub_question(data):
    """ElevenLabs is proposed only when the user's language has no dub already."""
    user = data.get("languages", {}).get("user")
    return not (data.get("voice", {}).get("existing") or {}).get(user)


def apply_defaults(data):
    """Fill the proposals that follow from other answers (never overrides a choice)."""
    lang = data.setdefault("languages", {})
    if lang.get("translate") is None and lang.get("user") and data["game"].get("languages_original"):
        lang["translate"] = [lang["user"]] if user_needs_translation(data) else []
    if lang.get("user") and not lang.get("requested"):
        lang["requested"] = [lang["user"]]
    return data


def missing_answers(data):
    """What must still be asked, at the right moment.

    Phase 0 asks only title, game files and the user's language (platforms and distribution
    have defaults). The paid choices (fal.ai, ElevenLabs, spending cap, licence) are asked only
    once the analysis has produced the counts (`analysis.counts`), so that every question comes
    with its estimated cost; then the plan approval."""
    out = []
    for key, label in (("game.title", "nome del gioco"), ("paths.game_files", "file di gioco"),
                       ("languages.user", "lingua dell'utente")):
        try:
            v = get_key(data, key)
        except KeyError:
            v = None
        if v in (None, "", []):
            out.append(label)
    if out:
        return out
    an = data.get("analysis") or {}
    if not (an.get("done") and an.get("counts")):
        return ["analisi (fase 1) e stime"]
    out += ["opera d'origine: " + p for p in source_work_problems(data)]
    g = data.get("graphics", {})
    out += pixel_aspect_question(data)
    ws = g.get("widescreen", {})
    if g.get("enabled") and ws.get("enabled") and ws.get("fal_ai") is None:
        out.append("fal.ai per le bande 16:9 (con preventivo)")
    v = data.get("voice", {})
    if v.get("enabled") is None and needs_dub_question(data):
        out.append("doppiaggio ElevenLabs (con preventivo)")
    out += paid_followups(data)
    ask = voice_likeness_to_ask(data)
    if ask:
        out.append("voce simile all'opera d'origine per: " + ", ".join(ask))
    if not out and not (data.get("plan") or {}).get("approved"):
        out.append("approvazione del piano")
    return out


def pixel_aspect_question(data):
    """The pixel aspect is decided automatically (`widescreen aspect-auto`); it is asked only
    when the automatic check left a doubt (decided_by "ask"), with the comparison sheet."""
    pa = (data.get("graphics") or {}).get("pixel_aspect") or {}
    if pa.get("decided_by") != "ask" or pa.get("stretch") is not None:
        return []
    doubt = next((r[len("dubbi: "):] for r in pa.get("reasons") or [] if r.startswith("dubbi: ")), "")
    q = f"proporzione dei pixel (proposta {pa.get('proposed')}"
    if pa.get("sheet"):
        q += f", foglio {pa['sheet']}"
    return [q + (f"; dubbi: {doubt})" if doubt else ")")]


SOURCE_TYPES = ("film", "series", "animation", "comic", "book", "other")


def new_character(name, performer=None, voices=None, sources=None):
    """A recognisable character of the source work. voices: {lang: {"name", "year", "sources"}}
    (the original language holds the performer, the others the dubbing voice of the time)."""
    return {"name": name, "performer": performer, "voices": voices or {}, "sources": sources or [],
            "imitate_voice": None}


def source_work_problems(data):
    """What is missing in `source_work` once it has been checked (sources above all)."""
    sw = data.get("source_work") or {}
    if not sw.get("checked") or not sw.get("title"):
        return []
    out = []
    if sw.get("type") not in SOURCE_TYPES:
        out.append(f"tipo dell'opera d'origine non valido ({', '.join(SOURCE_TYPES)})")
    if not sw.get("sources"):
        out.append("opera d'origine senza fonti")
    v = data.get("voice") or {}
    langs = set(v.get("languages") or [])
    if not langs and v.get("enabled"):
        user = (data.get("languages") or {}).get("user")
        langs = {user} if user else set()

    def found(val):
        # a placeholder ("da verificare", "?", "") means the period voice was not found yet
        name = val.get("name") if isinstance(val, dict) else val
        return bool(name) and not str(name).strip().lower().startswith(("da verificare", "?", "sconosciut", "n/d"))
    for c in sw.get("characters") or []:
        if not c.get("sources"):
            out.append(f"{c.get('name')}: senza fonti")
        voices = c.get("voices") or {}
        for lg in sorted(langs):
            if not found(voices.get(lg)):
                out.append(f"{c.get('name')}: voce dell'epoca in «{lg}» non trovata o da verificare")
    return out


def voice_likeness_to_ask(data):
    """Recognisable characters still without the "similar voice" answer — only when the dub has
    been chosen (voice.enabled true)."""
    if not (data.get("voice") or {}).get("enabled"):
        return []
    sw = data.get("source_work") or {}
    return [c.get("name") or "?" for c in sw.get("characters") or [] if c.get("imitate_voice") is None]


def paid_followups(data):
    """Spending cap and licence, needed as soon as a paid service is chosen."""
    out = []
    paid = data.get("voice", {}).get("enabled") or data.get("graphics", {}).get("widescreen", {}).get("fal_ai")
    b = data.get("budget", {})
    if paid and b.get("cap_usd") is None and b.get("cap_credits") is None:
        out.append("tetto di spesa del progetto")
    if data.get("voice", {}).get("enabled") and not data["voice"].get("license_confirmed"):
        out.append("conferma licenza ElevenLabs")
    return out


def register_packages(data, packages, budget=None, hard_limit=None):
    """Write the planned work packages in the registry, keeping the state of the ones already
    there (same id)."""
    reg = {p["id"]: p for p in data.setdefault("work_packages", [])}
    for pk in packages:
        cur = reg.get(pk["id"])
        if cur is None:
            reg[pk["id"]] = {"id": pk["id"], "label": pk.get("label"), "agent": pk.get("agent"),
                             "depends": pk.get("depends", []), "group": pk.get("group"),
                             "status": "pending", "tokens_est": pk.get("tokens"),
                             "tokens_used": 0, "started": None, "last_progress": None,
                             "attempts": 0, "task_id": None, "note": ""}
        else:
            cur.update({k: pk.get(k2) for k, k2 in (("label", "label"), ("agent", "agent"),
                                                    ("depends", "depends"), ("group", "group"),
                                                    ("tokens_est", "tokens")) if pk.get(k2) is not None})
    data["work_packages"] = list(reg.values())
    pl = data.setdefault("plan", {})
    if budget:
        pl["token_budget"] = budget
    if hard_limit:
        pl["token_hard_limit"] = hard_limit
    return data


def update_package(data, pid, status=None, tokens_used=None, note=None, task_id=None, now=None):
    """Update one package: `running` starts an attempt, every update counts as progress."""
    now = now or _now()
    for p in data.get("work_packages", []):
        if p["id"] == pid:
            break
    else:
        raise KeyError(f"pacchetto sconosciuto: {pid}")
    if status:
        if status not in PACKAGE_STATES:
            raise ValueError(f"stato «{status}» non valido: {', '.join(PACKAGE_STATES)}")
        if status == "running" and p["status"] != "running":
            p["attempts"] = p.get("attempts", 0) + 1
            p["started"] = now
            p["tokens_used"] = 0
        p["status"] = status
    if tokens_used is not None:
        p["tokens_used"] = int(tokens_used)
    if note is not None:
        p["note"] = note
    if task_id is not None:
        p["task_id"] = task_id
    p["last_progress"] = now
    return p


def summary(data):
    g = data["game"]
    lines = [f"Gioco: {g.get('title') or '?'} ({g.get('year') or '?'}, {g.get('platform') or '?'})",
             f"Fase: {data['phase']}",
             f"Motore: {data['engine'].get('id') or '?'} — supporto {data['engine'].get('support') or '?'}"]
    gr = data["graphics"]
    if gr.get("enabled"):
        lines.append("Grafica: " + (", ".join(gr.get("parts") or []) or "sì")
                     + (" · 16:9" if gr["widescreen"].get("enabled") else "")
                     + (f" · {gr['framerate'].get('target')} fps" if gr["framerate"].get("enabled") else ""))
    pa = gr.get("pixel_aspect") or {}
    if pa.get("stretch") is not None:
        how = {"auto": "decisa da sola", "user": "scelta dall'utente"}.get(pa.get("decided_by"), "")
        proof = (pa.get("reasons") or [""])[-1] if pa.get("decided_by") == "auto" else (pa.get("reason") or "")
        lines.append(f"Proporzione dei pixel: {pa['stretch']:g}" + (f" ({how})" if how else "")
                     + (f" — {proof}" if proof else ""))
    lang = data["languages"]
    if lang.get("user"):
        lines.append(f"Lingua dell'utente: {lang['user']}")
    if lang.get("requested"):
        lines.append("Lingue: " + ", ".join(lang["requested"])
                     + (f" (da tradurre: {', '.join(lang['translate'])})" if lang.get("translate") else ""))
    wp = data.get("work_packages") or []
    if wp:
        done = sum(1 for p in wp if p.get("status") == "done")
        run = sum(1 for p in wp if p.get("status") == "running")
        lines.append(f"Pacchetti di lavoro: {done}/{len(wp)} fatti, {run} in corso")
    if data["audio"].get("enabled"):
        lines.append("Audio: rimasterizzato")
    if data["voice"].get("enabled"):
        lines.append("Doppiaggio: ElevenLabs" + ("" if data["voice"].get("license_confirmed") else " (licenza da confermare)"))
    sw = data.get("source_work") or {}
    if sw.get("title"):
        lines.append(f"Opera d'origine: {sw['title']} ({sw.get('type') or '?'}, {sw.get('year') or '?'})"
                     f" · personaggi riconoscibili: {len(sw.get('characters') or [])}")
    elif sw.get("checked"):
        lines.append("Opera d'origine: nessuna")
    lines.append("Piattaforme: " + ", ".join(data.get("platforms", [])))
    lines.append(f"Distribuzione: {data['distribution']['mode']}")
    miss = missing_answers(data)
    if miss:
        lines.append("Da chiedere: " + ", ".join(miss))
    return "\n".join(lines)


def _now():
    return _dt.datetime.now().replace(microsecond=0).isoformat()
