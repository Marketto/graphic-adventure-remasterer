"""The remaster plan: estimates from the analysis counts, work packages sized to the token budget
of one sub-session, the table shown to the user and the status of the running packages.

Input of `estimate`: a JSON of counts produced by the analysis (phase 1). Every field is
optional (a missing one counts as 0 or as "not present"):

    backgrounds, bg_pixels           number of backgrounds and their total pixels (original size)
    sprite_frames, sprite_pixels     sprite frames and their total pixels (pixels optional)
    text_lines, text_chars           lines and characters of the game text (one language)
    voice_lines, voice_chars         spoken lines and characters of the script to dub
    music_tracks, sfx                music tracks and sound effects
    voice_chars_unique               characters of the UNIQUE spoken texts (preferred: clips repeat lines)
    voice_clips                      original speech clips (> 0: the game is spoken, restore them)
    lipsync                          true when the original clips carry lip-sync data
    scenes_by_class                  {"scroll-wide": n, "scroll-narrow": n, "scroll-narrow-open": n,
                                      "closed-static": n, "open-static": n, "ui-fixed": n, "skip": n}
                                     (widescreen classify; only open sides are invented)
    screen, playfield_h              screen [w, h] and height of the play area (bar below if lower)
    pixel_aspect                     vertical stretch decided (or proposed) for the pixels
    layer_hooked                     true when the Remaster Layer already works with this engine
    manual_pages                     pages of the manual
    translate_languages              languages to translate into (list or number); without it the
                                     project (remaster.json: languages.translate/available) decides
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
    "eleven_expand": 1.12,            # the target language is longer than the source (it ≈ +10-15% on en)
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
    "tok_engine_hook": 150000,        # hook the Layer into an engine it does not know yet (dump, keys)
    "tok_pixel_aspect": 60000,        # vertical scale of the Layer for non-square pixels
    "tok_ui_bar": 50000,              # interface bar below the play area widened to 16:9
    "tok_lipsync": 60000,             # lip-sync data for the new voices (from the audio) or fallback
    "tok_per_import_line": 12,        # official text of another edition: import and align, per line
    "import_residual_share": 0.15,    # share of the text missing in the other edition (to translate)
    "package_fill": 0.8,              # a package is filled up to 80% of the budget (margin)
}

DEFAULT_PLATFORMS = ["windows", "linux", "macos", "android", "web"]


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


def _langs(counts, project=None):
    """{lang: "translate"|"import"}: from the counts (`translate_languages`) or, when absent,
    from the project (languages.translate and the real availability for the user's edition)."""
    v = counts.get("translate_languages")
    if isinstance(v, list):
        return {x: "translate" for x in v}
    if isinstance(v, (int, float)) and v > 0:
        return {f"lingua{i + 1}": "translate" for i in range(int(v))}
    if project:
        from . import project as _project
        return _project.translation_plan(project)
    return {}


def _scenes(counts):
    """(scenes to invent, scenes with borders only). Only OPEN sides are invented: open-static
    plus the scroll-narrow with open sides (`scroll-narrow-open`; an old plan without it counts
    every scroll-narrow as open)."""
    sc = counts.get("scenes_by_class") or {}
    g = lambda k: int(sc.get(k, 0) or 0)  # noqa: E731
    narrow = g("scroll-narrow")
    narrow_open = min(narrow, g("scroll-narrow-open")) if "scroll-narrow-open" in sc else narrow
    return g("open-static") + narrow_open, g("closed-static") + narrow - narrow_open


def _stretch(counts, project):
    v = counts.get("pixel_aspect")
    if isinstance(v, dict):
        v = v.get("stretch")
    if v is None and project:
        v = ((project.get("graphics") or {}).get("pixel_aspect") or {}).get("stretch")
    try:
        return float(v) if v is not None else 1.0
    except (TypeError, ValueError):
        return 1.0


def _playfield(counts):
    scr = counts.get("screen") or []
    pf = counts.get("playfield_h")
    if pf is None and isinstance(counts.get("playfield_typical"), list):
        pf = counts["playfield_typical"][1]
    return (int(scr[1]) if len(scr) == 2 else None), (int(pf) if pf else None)


def _item(id_, emoji, label, agent, units, unit_name, tok_per_unit, tok_flat=0, cpu_s=0.0,
          depends=(), paid=None, usd=0.0, credits=0.0, quote=None, splittable=True, requires=None):
    return {"id": id_, "emoji": emoji, "label": label, "agent": agent, "units": units,
            "unit_name": unit_name, "tok_per_unit": tok_per_unit, "tok_flat": tok_flat,
            "tokens": int(tok_flat + units * tok_per_unit), "cpu_s": round(cpu_s),
            "depends": list(depends), "paid": paid, "usd": round(usd, 2),
            "credits": round(credits), "quote": quote, "splittable": splittable, "requires": requires}


def estimate(counts, coeffs=None, project=None):
    """Work items with units, tokens, CPU time and cost. Free items always; paid items
    (fal.ai, ElevenLabs) are listed with their quote and marked `paid`. `project` (the data of
    remaster.json, optional) completes what the counts do not say: languages, pixel aspect,
    Layer already hooked, 16:9 enabled, dub languages."""
    c = coeffs or COEFFS
    project = project or {}
    items = []
    E = lambda *a, **k: items.append(_item(*a, **k))  # noqa: E731
    E("engine-port", "🛠️", "Motore: fork e gioco completabile", "build-engineer", 0, "", 0,
      c["tok_engine_port"], splittable=False)
    hooked = counts.get("layer_hooked")
    if hooked is None:
        hooked = (project.get("engine") or {}).get("layer_hooked")
    if not hooked:
        E("engine-hook", "🪝", "Aggancio del Remaster Layer al motore (dump, chiavi, ganci HD)", "build-engineer",
          0, "", 0, c["tok_engine_hook"], depends=["engine-port"], splittable=False)
    E("engine-layer", "🧩", "Remaster Layer: HD, toggle, viewport 16:9", "build-engineer", 0, "", 0,
      c["tok_engine_layer"], depends=["engine-hook" if not hooked else "engine-port"], splittable=False)
    stretch = _stretch(counts, project)
    if abs(stretch - 1.0) > 1e-3:
        E("pixel-aspect", "📐", f"Scala verticale per pixel non quadrati (allungamento {stretch:g})",
          "build-engineer", 0, "", 0, c["tok_pixel_aspect"], depends=["engine-layer"], splittable=False)
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

    ws_on = ((project.get("graphics") or {}).get("widescreen") or {}).get("enabled", True) is not False
    inv, closed = _scenes(counts) if ws_on else (0, 0)
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
    screen_h, pf_h = _playfield(counts)
    if ws_on and screen_h and pf_h and pf_h < screen_h:
        E("ui-bar", "▭", f"Barra dell'interfaccia ({screen_h - pf_h} px sotto l'area di gioco) allargata a 16:9",
          "graphics-artist", 0, "", 0, c["tok_ui_bar"], depends=["engine-layer", "fonts-ui"], splittable=False)

    lines, chars = _n(counts, "text_lines"), _n(counts, "text_chars")
    if lines or chars:
        E("text", "📝", "Testi: correzione e chiavi", "localizer", lines, "righe", c["tok_per_text_line"],
          c["tok_base"])
    langs = _langs(counts, project)
    tdep = ["text"] if (lines or chars) else []
    for lang, mode in langs.items():
        if mode == "import":
            E(f"text-import-{lang}", "📥", f"Testo ufficiale in {lang} da un'altra edizione dell'utente: "
              "importazione e allineamento", "localizer", lines, "righe", c["tok_per_import_line"], c["tok_base"],
              depends=tdep)
            E(f"translate-{lang}", "🌍", f"Traduzione in {lang} delle righe assenti nell'altra edizione", "localizer",
              round(chars * c["import_residual_share"]), "caratteri", c["tok_per_translate_char"], c["tok_base"],
              depends=[f"text-import-{lang}"])
        else:
            E(f"translate-{lang}", "🌍", f"Traduzione in {lang}", "localizer", chars, "caratteri",
              c["tok_per_translate_char"], c["tok_base"], depends=tdep)

    sfx_v = counts.get("sfx")
    tracks = _n(counts, "music_tracks")
    sfx = (sum(int(x) for x in sfx_v.values() if isinstance(x, (int, float))) if isinstance(sfx_v, dict)
           else _n(counts, "sfx"))
    if tracks or sfx:
        E("audio", "🔊", "Musica ed effetti: rimaster e normalizzazione per gruppo", "audio-engineer",
          tracks, "brani", c["tok_per_track"], c["tok_base"] + sfx * c["tok_per_sfx"],
          cpu_s=tracks * c["audio_s_per_track"] + sfx * c["audio_s_per_sfx"])
    vlines = _n(counts, "voice_lines")
    vchars = _n(counts, "voice_chars_unique") or _n(counts, "voice_chars")
    clips = _n(counts, "voice_clips")
    if (counts.get("original_voices") or clips) and (vlines or clips) and \
            (project.get("audio") or {}).get("restore_original_voices", True) is not False:
        n = clips or vlines
        E("voice-restore", "🗣️", "Restauro delle voci originali", "audio-engineer", n, "clip",
          c["tok_per_restore_line"], c["tok_base"], cpu_s=n * c["restore_s_per_line"])
    vproj = project.get("voice") or {}
    dub_langs = list(vproj.get("languages") or []) or list(langs) or \
        ([project["languages"]["user"]] if (project.get("languages") or {}).get("user") else [])
    existing = vproj.get("existing") or {}
    dub_exists = counts.get("dub_exists") or (dub_langs and all(existing.get(x) for x in dub_langs))
    if vlines and not dub_exists:
        original = set((project.get("game") or {}).get("languages_original") or [])
        expand = c["eleven_expand"] if (langs or (original and any(x not in original for x in dub_langs))) else 1.0
        chars_t = vchars * expand
        cred = chars_t * c["eleven_credits_per_char"] * c["eleven_retake"]
        dep = ["text"] + [f"translate-{x}" for x in langs] + [f"text-import-{x}" for x in langs]
        E("dub", "🎙️", "Doppiaggio ElevenLabs (per capitolo)", "voice-director", vlines, "battute",
          c["tok_per_voice_line"], c["tok_base"], cpu_s=vlines * c["dub_s_per_line"],
          depends=[d for d in dep if any(i["id"] == d for i in items)], paid="voice",
          credits=cred, usd=cred * c["eleven_usd_per_credit"],
          quote={"chars": vchars, "unique_texts": bool(_n(counts, "voice_chars_unique")),
                 "expand": expand, "chars_target": round(chars_t),
                 "credits_per_char": c["eleven_credits_per_char"],
                 "retake": c["eleven_retake"], "credits": round(cred),
                 "usd_indicative": round(cred * c["eleven_usd_per_credit"], 2)})
        if counts.get("lipsync"):
            E("lipsync", "👄", "Sincronia labiale per le voci nuove (dati dall'audio o bocca dall'ampiezza)",
              "build-engineer", 0, "", 0, c["tok_lipsync"], depends=["dub", "engine-layer"], splittable=False,
              requires="voice")
    mix_dep = [d for d in ("audio", "voice-restore", "dub", "lipsync") if any(i["id"] == d for i in items)]
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
    """Keep the free items and the paid ones chosen (`paid`: set of "fal", "voice"); a free item
    that only makes sense with a paid one (`requires`, e.g. lip-sync for the new voices) follows it."""
    keep = [i for i in items if (not i["paid"] or i["paid"] in paid)
            and (not i.get("requires") or i["requires"] in paid)]
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
                                                else (f" ({_int(u)} {it['unit_name']})" if u else "")),
                        "agent": it["agent"], "units": u, "unit_name": it["unit_name"], "tokens": tok,
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


def _grouped(packages):
    """One row per work item: the lots of a split item (e.g. 20 dubbing lots) become one row
    with the number of lots, the sums and the dependencies of the item."""
    rows, by = [], {}
    item_of = {p["id"]: p["item"] for p in packages}
    for p in packages:
        r = by.get(p["item"])
        if r is None:
            r = by[p["item"]] = dict(p, lots=1, label=p["label"].split(" (")[0] if p["id"] != p["item"] else p["label"],
                                     depends=[], groups=[p["group"]])
            rows.append(r)
        else:
            r["lots"] += 1
            r["units"] += p["units"]
            for k in ("tokens", "minutes", "cpu_s", "credits"):
                r[k] += p[k]
            r["usd"] = round(r["usd"] + p["usd"], 2)
            r["groups"].append(p["group"])
        for d in p["depends"]:
            if item_of[d] != p["item"] and item_of[d] not in r["depends"]:
                r["depends"].append(item_of[d])
    for r in rows:
        if r["lots"] > 1:
            r["label"] += f" ({r['lots']} lotti, {_int(r['units'])} {r['unit_name']})" if r.get("unit_name") \
                else f" ({r['lots']} lotti)"
        g = sorted(set(r.pop("groups")))
        r["group"] = g[0] if len(g) == 1 else f"{g[0]}-{g[-1]}"
    return rows


def table(pk, parallel=3, group=True):
    """Markdown table of the plan: free and paid packages separated, totals at the end.
    `group`: the lots of the same item (dubbing by chapter, sprites, translation) in one row."""
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
    shown = _grouped(pk["packages"]) if group else pk["packages"]
    free = [p for p in shown if not p["paid"]]
    paid = [p for p in shown if p["paid"]]
    parts = ["**Gratuito (incluso di default)**", "", head] + [row(p) for p in free]
    if paid:
        parts += ["", "**A pagamento (scelto dopo il preventivo)**", "", head] + [row(p) for p in paid]
    seq = sum(p["minutes"] for p in pk["packages"])
    usd = sum(p["usd"] for p in pk["packages"] if p["paid"])
    cred = sum(p["credits"] for p in pk["packages"] if p["paid"])
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
