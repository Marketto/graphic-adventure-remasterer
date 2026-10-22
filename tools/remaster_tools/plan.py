"""The remaster plan: estimates from the analysis counts, work packages sized to the token budget
of one sub-session, the table shown to the user and the status of the running packages.

Input of `estimate`: a JSON of counts produced by the analysis (phase 1). Every field is
optional (a missing one counts as 0 or as "not present"):

    backgrounds, bg_pixels           number of backgrounds and their total pixels (original size)
    sprite_frames, sprite_pixels     sprite frames and their total pixels (pixels optional)
    text_lines, text_chars           lines and characters of the game text (one language)
    voice_lines, voice_chars         spoken lines and characters of the script to dub
    music_tracks, sfx                music tracks and sound effects
    scenes_by_class                  {"scroll-wide": n, "scroll-narrow": n, "closed-static": n,
                                      "open-static": n, "ui-fixed": n} (widescreen classify)
    manual_pages                     pages of the manual
    translate_languages              languages to translate into (list or number)
    original_voices                  true when the game has speech to restore
    dub_exists                       true when a dub in the user's language already exists
    platforms                        list of target platforms (default: the five of the project)

The coefficients (times, prices, tokens) are in COEFFS, documented one by one; a JSON file can
override any of them (`--coeffs`). They are estimates from the reference project, to be
corrected with the real measurements of the first packages.
"""
import datetime as _dt
import json
import math

COEFFS = {
    # --- times (seconds) -----------------------------------------------------------------
    "apisr_us_per_pixel": 100,        # APISR (RRDB/GRL) on a 2-core CPU, per input pixel, overlaps included
    "bg_avg_pixels": 320 * 200,       # pixels of a background when bg_pixels is missing
    "sprite_avg_pixels": 3000,        # pixels of a sprite frame when sprite_pixels is missing
    "ws_local_s_per_scene": 150,      # LaMa 1x + quilting + recipes + checks, per scene to invent
    "ws_border_s_per_scene": 5,       # closed-static: borders only
    "audio_s_per_track": 90,          # render/clean + group normalization, per music track
    "audio_s_per_sfx": 3,             # resample + clean + normalization, per effect
    "restore_s_per_line": 4,          # restoration of the original speech, per line
    "dub_s_per_line": 6,              # generation + automatic check, per dubbed line
    "ci_min_per_platform": 25,        # minutes of CI per platform build
    "agent_tokens_per_min": 4000,     # how many tokens a sub-session consumes per minute of work
    # --- prices --------------------------------------------------------------------------
    "fal_price_usd": 0.05,            # FLUX.1 Fill pro per image (indicative: check the site)
    "fal_attempts": 2,                # at most 2 attempts per scene
    "fal_accept_first": 0.65,         # share accepted at the first attempt (likely case)
    "eleven_credits_per_char": 0.43,  # ElevenLabs credits per character of the script
    "eleven_retake": 1.15,            # +15% for retakes after the check
    "eleven_usd_per_credit": 0.00022,  # indicative (Creator plan: 22 $ per 100,000 credits)
    # --- tokens of one sub-session -------------------------------------------------------
    "tok_base": 30000,                # overhead of a package: skill, docs, project, report
    "tok_per_bg": 1500,               # one background: commands, check, comparison image
    "tok_per_sprite": 25,             # one sprite frame (batch pipeline, sample checks)
    "tok_per_ws_scene": 5000,         # one scene to invent: variants, galleries, images looked at
    "tok_per_ws_border": 300,         # one scene with borders only
    "tok_per_fal_scene": 2500,        # one fal.ai scene: call, check, gallery
    "tok_per_text_line": 40,          # correction of the text, per line
    "tok_per_translate_char": 1.2,    # translation, per character (read + write + review)
    "tok_per_voice_line": 450,        # dubbing: direction, generation, check, per line
    "tok_per_restore_line": 60,       # restoration of the original speech, per line
    "tok_per_track": 3000,            # music track
    "tok_per_sfx": 150,               # sound effect
    "tok_per_manual_page": 3500,      # manual page: clean, translate, lay out
    "tok_hints": 60000,               # in-game hints
    "tok_fonts_ui": 90000,            # HD fonts with the glyphs + UI/inventory/cursors
    "tok_engine_port": 180000,        # fork + playable from start to end (test driver)
    "tok_engine_layer": 170000,       # Remaster Layer: HD compositor, toggle, 16:9 viewport
    "tok_engine_patch": 140000,       # patchable engine + smooth controls + saves/menus
    "tok_engine_theme": 90000,        # GUI theme in the style of the game
    "tok_framerate": 70000,           # frame interpolation at the target fps
    "tok_mix": 60000,                 # mix levels between the groups, listening tests
    "tok_qa": 170000,                 # independent QA
    "tok_release": 120000,            # builds, patch, installer, checksums
    "package_fill": 0.8,              # a package is filled up to 80% of the budget (margin)
}

DEFAULT_PLATFORMS = ["windows", "linux", "macos", "android", "web"]
INVENT = ("open-static", "scroll-narrow")   # classes whose bands are invented


def load_coeffs(path=None):
    c = dict(COEFFS)
    if path:
        with open(path, encoding="utf-8") as f:
            extra = json.load(f)
        unknown = set(extra) - set(COEFFS)
        if unknown:
            raise ValueError(f"coefficienti sconosciuti: {', '.join(sorted(unknown))}")
        c.update(extra)
    return c


def _n(counts, key):
    v = counts.get(key)
    return int(v) if isinstance(v, (int, float)) and v > 0 else 0


def _langs(counts):
    v = counts.get("translate_languages")
    if isinstance(v, list):
        return v
    if isinstance(v, (int, float)) and v > 0:
        return [f"lingua{i + 1}" for i in range(int(v))]
    return []


def _item(id_, emoji, label, agent, units, unit_name, tok_per_unit, tok_flat=0, cpu_s=0.0,
          depends=(), paid=None, usd=0.0, credits=0.0, quote=None, splittable=True):
    return {"id": id_, "emoji": emoji, "label": label, "agent": agent, "units": units,
            "unit_name": unit_name, "tok_per_unit": tok_per_unit, "tok_flat": tok_flat,
            "tokens": int(tok_flat + units * tok_per_unit), "cpu_s": round(cpu_s),
            "depends": list(depends), "paid": paid, "usd": round(usd, 2),
            "credits": round(credits), "quote": quote, "splittable": splittable}


def estimate(counts, coeffs=None):
    """Work items with units, tokens, CPU time and cost. Free items always; paid items
    (fal.ai, ElevenLabs) are listed with their quote and marked `paid`."""
    c = coeffs or COEFFS
    items = []
    E = lambda *a, **k: items.append(_item(*a, **k))  # noqa: E731
    E("engine-port", "🛠️", "Motore: fork e gioco completabile", "build-engineer", 0, "", 0,
      c["tok_engine_port"], splittable=False)
    E("engine-layer", "🧩", "Remaster Layer: HD, toggle, viewport 16:9", "build-engineer", 0, "", 0,
      c["tok_engine_layer"], depends=["engine-port"], splittable=False)
    E("engine-patch", "🎮", "Motore patchabile, controlli fluidi, salvataggi e menu", "build-engineer",
      0, "", 0, c["tok_engine_patch"], depends=["engine-port"], splittable=False)
    E("engine-theme", "🎨", "Tema GUI nello stile del gioco", "build-engineer", 0, "", 0,
      c["tok_engine_theme"], depends=["engine-patch"], splittable=False)
    E("framerate", "🎞️", "Framerate a 60 fps", "build-engineer", 0, "", 0, c["tok_framerate"],
      depends=["engine-layer"], splittable=False)

    nbg = _n(counts, "backgrounds")
    bgpx = _n(counts, "bg_pixels") or nbg * c["bg_avg_pixels"]
    if nbg:
        E("bg", "🖼️", "Fondali HD", "graphics-artist", nbg, "fondali", c["tok_per_bg"], c["tok_base"],
          cpu_s=bgpx * c["apisr_us_per_pixel"] / 1e6)
    nspr = _n(counts, "sprite_frames")
    sprpx = _n(counts, "sprite_pixels") or nspr * c["sprite_avg_pixels"]
    if nspr:
        E("sprites", "🧍", "Sprite e animazioni HD", "graphics-artist", nspr, "fotogrammi",
          c["tok_per_sprite"], c["tok_base"], cpu_s=sprpx * c["apisr_us_per_pixel"] / 1e6)
    E("fonts-ui", "🔤", "Font HD, interfaccia, inventario, cursori", "graphics-artist", 0, "", 0,
      c["tok_fonts_ui"], splittable=False)

    sc = counts.get("scenes_by_class") or {}
    inv = sum(int(sc.get(k, 0) or 0) for k in INVENT)
    closed = int(sc.get("closed-static", 0) or 0)
    if inv or closed:
        E("ws-local", "↔️", "16:9 con metodi locali (bande inventate + bordi)", "widescreen-planner",
          inv, "scene da inventare", c["tok_per_ws_scene"], c["tok_base"] + closed * c["tok_per_ws_border"],
          cpu_s=inv * c["ws_local_s_per_scene"] + closed * c["ws_border_s_per_scene"],
          depends=["bg"] if nbg else [])
    if inv:
        worst = inv * c["fal_attempts"]
        likely = round(inv * (c["fal_accept_first"] + (1 - c["fal_accept_first"]) * c["fal_attempts"]))
        E("ws-fal", "💸", "16:9 con fal.ai sulle scene dove il locale non convince", "widescreen-planner",
          inv, "scene", c["tok_per_fal_scene"], c["tok_base"], depends=["ws-local"], paid="fal",
          usd=worst * c["fal_price_usd"],
          quote={"scenes": inv, "attempts": c["fal_attempts"], "price_usd": c["fal_price_usd"],
                 "max_images": worst, "max_usd": round(worst * c["fal_price_usd"], 2),
                 "likely_images": likely, "likely_usd": round(likely * c["fal_price_usd"], 2)})

    lines, chars = _n(counts, "text_lines"), _n(counts, "text_chars")
    if lines or chars:
        E("text", "📝", "Testi: correzione e chiavi", "localizer", lines, "righe", c["tok_per_text_line"],
          c["tok_base"])
    for lang in _langs(counts):
        E(f"translate-{lang}", "🌍", f"Traduzione in {lang}", "localizer", chars, "caratteri",
          c["tok_per_translate_char"], c["tok_base"], depends=["text"] if (lines or chars) else [])

    tracks, sfx = _n(counts, "music_tracks"), _n(counts, "sfx")
    if tracks or sfx:
        E("audio", "🔊", "Musica ed effetti: rimaster e normalizzazione per gruppo", "audio-engineer",
          tracks, "brani", c["tok_per_track"], c["tok_base"] + sfx * c["tok_per_sfx"],
          cpu_s=tracks * c["audio_s_per_track"] + sfx * c["audio_s_per_sfx"])
    vlines, vchars = _n(counts, "voice_lines"), _n(counts, "voice_chars")
    if counts.get("original_voices") and vlines:
        E("voice-restore", "🗣️", "Restauro delle voci originali", "audio-engineer", vlines, "battute",
          c["tok_per_restore_line"], c["tok_base"], cpu_s=vlines * c["restore_s_per_line"])
    if vlines and not counts.get("dub_exists"):
        cred = vchars * c["eleven_credits_per_char"] * c["eleven_retake"]
        dep = ["text"] + [f"translate-{x}" for x in _langs(counts)]
        E("dub", "🎙️", "Doppiaggio ElevenLabs (per capitolo)", "voice-director", vlines, "battute",
          c["tok_per_voice_line"], c["tok_base"], cpu_s=vlines * c["dub_s_per_line"],
          depends=[d for d in dep if any(i["id"] == d for i in items)], paid="voice",
          credits=cred, usd=cred * c["eleven_usd_per_credit"],
          quote={"chars": vchars, "credits_per_char": c["eleven_credits_per_char"],
                 "retake": c["eleven_retake"], "credits": round(cred),
                 "usd_indicative": round(cred * c["eleven_usd_per_credit"], 2)})
    mix_dep = [d for d in ("audio", "voice-restore", "dub") if any(i["id"] == d for i in items)]
    if mix_dep:
        E("mix", "🎚️", "Mix tra i gruppi (prove d'ascolto)", "audio-engineer", 0, "", 0, c["tok_mix"],
          depends=mix_dep, splittable=False)

    pages = _n(counts, "manual_pages")
    if pages:
        E("manual", "📖", "Manuale nel remaster", "localizer", pages, "pagine", c["tok_per_manual_page"],
          c["tok_base"])
    E("hints", "💡", "Aiuti in gioco (tasto H)", "localizer", 0, "", 0, c["tok_hints"],
      depends=["text"] if (lines or chars) else [], splittable=False)

    plats = counts.get("platforms") or DEFAULT_PLATFORMS
    ci_min = len(plats) * c["ci_min_per_platform"]
    E("qa", "🧪", "QA indipendente", "qa-tester", 0, "", 0, c["tok_qa"],
      depends=[i["id"] for i in items], splittable=False)
    # the CI builds the platforms in parallel (matrix): elapsed time = one platform
    E("release", "📦", f"Build ({', '.join(plats)}; ~{ci_min} min di CI) e patch", "build-engineer", 0, "", 0,
      c["tok_release"], cpu_s=c["ci_min_per_platform"] * 60, depends=["qa"], splittable=False)
    items[-1]["ci_minutes"] = ci_min
    return {"items": items, "coeffs": c}


def _select(items, paid):
    """Keep the free items and the paid ones chosen (`paid`: set of "fal", "voice")."""
    keep = [i for i in items if not i["paid"] or i["paid"] in paid]
    ids = {i["id"] for i in keep}
    for i in keep:
        i["depends"] = [d for d in i["depends"] if d in ids]
    return keep


def packages(est, paid=(), budget=200000, coeffs=None):
    """Split the items into packages that fit one sub-session (budget × package_fill tokens),
    with dependencies and parallel groups (group n starts when the groups before are done)."""
    c = coeffs or est.get("coeffs") or COEFFS
    target = budget * c["package_fill"]
    items = _select(json.loads(json.dumps(est["items"])), set(paid))
    out, by_item = [], {}
    for it in items:
        n = 1
        if it["splittable"] and it["units"] and it["tokens"] > target:
            room = max(target - it["tok_flat"], it["tok_per_unit"])
            per = max(1, int(room // it["tok_per_unit"]))
            n = math.ceil(it["units"] / per)
        by_item[it["id"]] = []
        for k in range(n):
            u = it["units"] // n + (1 if k < it["units"] % n else 0) if it["units"] else 0
            share = (u / it["units"]) if it["units"] else 1.0
            pid = it["id"] if n == 1 else f"{it['id']}-{k + 1}"
            tok = int(it["tok_flat"] + u * it["tok_per_unit"]) if it["units"] else it["tokens"]
            out.append({"id": pid, "item": it["id"], "emoji": it["emoji"],
                        "label": it["label"] + (f" ({k + 1}/{n}: {u} {it['unit_name']})" if n > 1
                                                else (f" ({u} {it['unit_name']})" if u else "")),
                        "agent": it["agent"], "units": u, "tokens": tok,
                        "cpu_s": round(it["cpu_s"] * share), "usd": round(it["usd"] * share, 2),
                        "credits": round(it["credits"] * share), "paid": it["paid"],
                        "item_depends": it["depends"],
                        "minutes": round(it["cpu_s"] * share / 60 + tok / c["agent_tokens_per_min"])})
            by_item[it["id"]].append(pid)
    for p in out:
        p["depends"] = [x for d in p.pop("item_depends") for x in by_item.get(d, [])]
    # groups: longest chain of dependencies
    level = {}
    for p in out:  # items are in dependency order
        level[p["id"]] = 1 + max((level[d] for d in p["depends"]), default=0)
        p["group"] = level[p["id"]]
    over = [p["id"] for p in out if p["tokens"] > budget]
    return {"budget": budget, "target": int(target), "packages": out, "over_budget": over}


def wall_minutes(pk, parallel=3):
    """Elapsed minutes running each group with at most `parallel` sub-sessions at a time."""
    total = 0
    for g in sorted({p["group"] for p in pk["packages"]}):
        lanes = [0] * max(1, parallel)
        for m in sorted((p["minutes"] for p in pk["packages"] if p["group"] == g), reverse=True):
            lanes[lanes.index(min(lanes))] += m
        total += max(lanes)
    return total


def _hm(minutes):
    h, m = divmod(int(round(minutes)), 60)
    return f"{h} h {m:02d}" if h else f"{m} min"


def _usd(v):
    return f"{v:.2f}".replace(".", ",") + " $"


def _int(v):
    return f"{int(round(v)):,}".replace(",", ".")


def _k(tokens):
    return f"{tokens / 1000:.0f}k"


def table(pk, parallel=3):
    """Markdown table of the plan: free and paid packages separated, totals at the end."""
    head = "| | Cosa | Agente | Dopo / gruppo | Tempo | Costo | Token |\n|---|---|---|---|---|---|---|"

    def row(p):
        cost = "gratis"
        if p["paid"] == "fal":
            cost = f"≤ {_usd(p['usd'])}"
        elif p["paid"] == "voice":
            cost = f"~{_int(p['credits'])} crediti (~{_usd(p['usd'])})"
        dep = ", ".join(p["depends"]) if len(p["depends"]) <= 3 else f"{len(p['depends'])} pacchetti"
        return (f"| {p['emoji']} | {p['label']} | {p['agent']} | {dep or '—'} · G{p['group']} | "
                f"{_hm(p['minutes'])} | {cost} | {_k(p['tokens'])} |")
    free = [p for p in pk["packages"] if not p["paid"]]
    paid = [p for p in pk["packages"] if p["paid"]]
    parts = ["**Gratuito (incluso di default)**", "", head] + [row(p) for p in free]
    if paid:
        parts += ["", "**A pagamento (scelto dopo il preventivo)**", "", head] + [row(p) for p in paid]
    seq = sum(p["minutes"] for p in pk["packages"])
    usd = sum(p["usd"] for p in paid)
    cred = sum(p["credits"] for p in paid)
    tok = sum(p["tokens"] for p in pk["packages"])
    parts += ["", f"**Totale**: {len(pk['packages'])} pacchetti · tempo ~{_hm(wall_minutes(pk, parallel))} "
              f"con {parallel} in parallelo ({_hm(seq)} in sequenza) · costo ≤ {_usd(usd)}"
              + (f" (di cui ~{_int(cred)} crediti ElevenLabs)" if cred else "")
              + f" · ~{_k(tok)} token · budget per sotto-sessione {_k(pk['budget'])} "
              f"(riempimento fino a {_k(pk['target'])})"]
    if pk.get("over_budget"):
        parts.append(f"⚠️ oltre il budget: {', '.join(pk['over_budget'])} (da spezzare a mano)")
    return "\n".join(parts) + "\n"


def _parse(ts):
    return _dt.datetime.fromisoformat(ts) if ts else None


def status(data, stale_min=30, max_attempts=3, now=None):
    """State of the work packages in remaster.json and what to do with the troubled ones.

    stale: running with no progress for `stale_min` minutes; over budget: tokens used beyond the
    hard limit (or 25% beyond the estimate, a warning). A troubled package is restarted with
    corrected instructions while attempts < max_attempts, otherwise stopped and reported."""
    now = now or _dt.datetime.now().replace(microsecond=0)
    pl = data.get("plan") or {}
    hard = pl.get("token_hard_limit", 250000)
    wp = data.get("work_packages") or []
    st = {p["id"]: p.get("status") for p in wp}
    res = {"running": [], "stale": [], "failed": [], "over_budget": [], "warn_tokens": [],
           "ready": [], "done": [], "to_restart": [], "to_stop": [], "pending": []}
    for p in wp:
        s = p.get("status", "pending")
        if s == "done":
            res["done"].append(p["id"])
            continue
        if s == "pending":
            (res["ready"] if all(st.get(d) == "done" for d in p.get("depends", [])) else res["pending"]).append(p["id"])
            continue
        trouble = None
        if s == "running":
            res["running"].append(p["id"])
            last = _parse(p.get("last_progress") or p.get("started"))
            if last and (now - last).total_seconds() / 60 > stale_min:
                res["stale"].append(p["id"])
                trouble = "fermo"
            used = p.get("tokens_used") or 0
            if used > hard:
                res["over_budget"].append(p["id"])
                trouble = "oltre il limite di token"
            elif p.get("tokens_est") and used > 1.25 * p["tokens_est"]:
                res["warn_tokens"].append(p["id"])
        elif s == "failed":
            res["failed"].append(p["id"])
            trouble = "fallito"
        if trouble:
            if p.get("attempts", 0) < max_attempts and trouble != "oltre il limite di token":
                res["to_restart"].append({"id": p["id"], "why": trouble, "attempts": p.get("attempts", 0)})
            else:
                res["to_stop"].append({"id": p["id"], "why": trouble, "attempts": p.get("attempts", 0)})
    res["summary"] = (f"{len(res['done'])}/{len(wp)} fatti, {len(res['running'])} in corso, "
                      f"{len(res['ready'])} pronti, {len(res['stale'])} fermi, {len(res['failed'])} falliti")
    return res
