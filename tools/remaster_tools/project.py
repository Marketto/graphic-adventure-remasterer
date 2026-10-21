"""remaster.json: the state of a remaster project (decisions, phase, paths)."""
import datetime as _dt
import json
import os

FILE = "remaster.json"

PHASES = ["intake", "analysis", "engine", "assets", "qa", "release", "done"]

DEFAULT = {
    "schema": 1,
    "phase": "intake",
    "game": {"title": None, "year": None, "developer": None, "publisher": None,
             "platform": None, "version": None, "languages_original": []},
    "engine": {"id": None, "runtime": None, "support": None, "notes": None,
               "base_commit": None},
    "existing_work": [],
    "reuse_existing_work": None,
    "graphics": {"enabled": None, "parts": [], "scale": 3,
                 # stretch 1.0 = square pixels; another value only if the game was made for a
                 # display that stretched its pixels (decided in the analysis, see platforms.py)
                 "pixel_aspect": {"stretch": None, "reason": None},
                 # fill: local methods (LaMa 1x + quilting + recipes); fal_ai: optional paid outpainting
                 "widescreen": {"enabled": None, "aspect": "16:9", "fill": "local", "fal_ai": None},
                 "framerate": {"enabled": None, "target": 60}},
    "ui_theme": {"enabled": True},
    "languages": {"requested": [], "available": {}, "translate": []},
    "audio": {"enabled": None, "music": None, "sfx": None,
              # stage 1: normalization per group; stage 2: levels of the groups in the mix (LUFS)
              "mix": {"voice": -18.0, "sfx": -16.0, "music": -25.0}},
    "extras": {"manual": None, "hints": None},
    # spending cap for the whole project (on top of the quote per batch) and the ledger
    "budget": {"cap_usd": None, "cap_credits": None, "spent": []},
    "voice": {"enabled": None, "provider": "elevenlabs", "license_confirmed": False,
              "languages": []},
    "platforms": ["windows", "linux", "macos", "android", "web"],
    "distribution": {"mode": "recipe", "rights_confirmed": False},
    "toggle_key": "F8",
    "paths": {"game_files": None, "workdir": "."},
    "decisions": [],
}


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


def missing_answers(data):
    """Intake questions still unanswered, in interview order."""
    checks = [
        ("game.title", "nome del gioco"),
        ("engine.support", "compatibilità motore"),
        ("reuse_existing_work", "riuso del lavoro esistente"),
        ("graphics.enabled", "miglioramento grafica"),
        ("languages.requested", "lingue"),
        ("audio.enabled", "miglioramento audio"),
        ("voice.enabled", "doppiaggio"),
        ("extras.manual", "manuale e aiuti in gioco"),
        ("extras.hints", "manuale e aiuti in gioco"),
        ("paths.game_files", "file di gioco"),
    ]
    out = []
    for key, label in checks:
        try:
            v = get_key(data, key)
        except KeyError:
            v = None
        if v is None or v == []:
            if key == "languages.requested" and data["languages"].get("confirmed"):
                continue
            if label not in out:
                out.append(label)
    g = data.get("graphics", {})
    if g.get("enabled") and g.get("widescreen", {}).get("enabled") is None:
        out.insert(out.index("lingue") if "lingue" in out else len(out), "formato 16:9")
    if g.get("widescreen", {}).get("enabled") and g["widescreen"].get("fal_ai") is None:
        out.insert(out.index("lingue") if "lingue" in out else len(out), "fal.ai per le bande 16:9 (opzionale)")
    paid = data.get("voice", {}).get("enabled") or g.get("widescreen", {}).get("fal_ai")
    b = data.get("budget", {})
    if paid and b.get("cap_usd") is None and b.get("cap_credits") is None:
        out.append("tetto di spesa del progetto")
    if data.get("voice", {}).get("enabled") and not data["voice"].get("license_confirmed"):
        out.append("conferma licenza ElevenLabs")
    return out


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
    lang = data["languages"]
    if lang.get("requested"):
        lines.append("Lingue: " + ", ".join(lang["requested"])
                     + (f" (da tradurre: {', '.join(lang['translate'])})" if lang.get("translate") else ""))
    if data["audio"].get("enabled"):
        lines.append("Audio: rimasterizzato")
    if data["voice"].get("enabled"):
        lines.append("Doppiaggio: ElevenLabs" + ("" if data["voice"].get("license_confirmed") else " (licenza da confermare)"))
    lines.append("Piattaforme: " + ", ".join(data.get("platforms", [])))
    lines.append(f"Distribuzione: {data['distribution']['mode']}")
    miss = missing_answers(data)
    if miss:
        lines.append("Da chiedere: " + ", ".join(miss))
    return "\n".join(lines)


def _now():
    return _dt.datetime.now().replace(microsecond=0).isoformat()
