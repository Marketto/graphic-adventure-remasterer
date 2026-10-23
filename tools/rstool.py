#!/usr/bin/env python3
"""rstool — command line of the graphic-adventure-remasterer pipeline. Every command prints JSON.

Run `rstool.py <group> -h` for the commands of a group:
  project, engine, key, assets, style, gfx, font, widescreen, video, review, text, audio, voice, ui,
  hint, manual, recipe, release, plan
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from remaster_tools import (assets, audio, audio_midi, audio_sf2, controls, detect, extract, falai, font, font_bitmap, gfx, hints, keys,  # noqa: E402
                            manual, plan, platforms, project, rawframe, recipe, release, review, style,
                            regia, text, theme, timing, transcribe, video, voice, voiceref, voiceseg,
                            widescreen)


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _friendly(fn, *args):
    """Expected problems (missing optional dependency, bad input) as a one-line message."""
    try:
        return fn(*args)
    except (RuntimeError, ValueError) as e:
        sys.exit(f"errore: {e}")


def cmd_aspect_auto(a):
    res = platforms.aspect_auto(a.platform, a.w, a.h, a.year, a.art, a.evidence, a.measure, a.sheet)
    if a.record:
        data = need_project(a.workdir)
        platforms.record_aspect(data, res)
        project.save(data, a.workdir)
        res["recorded"] = project.path(a.workdir)
    out(res)


def need_project(workdir):
    data = project.load(workdir)
    if data is None:
        sys.exit("Nessun progetto: esegui prima `rstool.py project init \"<titolo>\"`")
    return data


def cmd_project(a):
    wd = a.workdir
    if a.action == "init":
        out(project.init(a.args[0] if a.args else None, wd, a.force))
    elif a.action == "show":
        data = project.load(wd)
        if data is None:
            out({"project": None})
        else:
            print(project.summary(data))
    elif a.action == "set":
        data = need_project(wd)
        for pair in zip(a.args[0::2], a.args[1::2]):
            project.set_key(data, pair[0], project.parse_value(pair[1]))
        project.apply_defaults(data)
        project.save(data, wd)
        out({"ok": True})
    elif a.action == "get":
        out(project.get_key(need_project(wd), a.args[0]))
    elif a.action == "decide":
        data = need_project(wd)
        project.decide(data, a.args[0], a.args[1] if len(a.args) > 1 else "")
        project.save(data, wd)
        out({"ok": True})
    elif a.action == "phase":
        data = need_project(wd)
        project.set_phase(data, a.args[0])
        project.save(data, wd)
        out({"phase": a.args[0]})
    elif a.action == "missing":
        out(project.missing_answers(need_project(wd)))
    elif a.action == "spend":
        data = need_project(wd)
        if len(a.args) != 2:
            sys.exit("uso: project spend <servizio> <importo> --unit usd|credits --note \"...\"")
        res = project.spend(data, a.args[0], float(a.args[1]), a.unit, a.note)
        project.save(data, wd)
        out(res)


def _paid(a):
    """--paid: auto (choices in remaster.json), none, all, or a list like fal,voice."""
    v = a.paid.strip().lower()
    if v == "none":
        return set()
    if v == "all":
        return {"fal", "voice"}
    if v == "auto":
        data = project.load(a.workdir) or {}
        got = set()
        if (data.get("graphics", {}).get("widescreen") or {}).get("fal_ai"):
            got.add("fal")
        if (data.get("voice") or {}).get("enabled"):
            got.add("voice")
        return got
    got = {x.strip() for x in v.split(",") if x.strip()}
    if got - {"fal", "voice"}:
        sys.exit(f"--paid: valori validi auto, none, all, fal, voice (ricevuto «{a.paid}»)")
    return got


def _plan_packages(a):
    with open(a.counts, encoding="utf-8") as f:
        counts = json.load(f)
    c = plan.load_coeffs(a.coeffs)
    data = project.load(a.workdir)
    budget = a.budget or ((data or {}).get("plan") or {}).get("token_budget") or 200000
    return plan.packages(plan.estimate(counts, c, data), _paid(a), budget, c)


def cmd_plan(a):
    if a.action == "estimate":
        with open(a.counts, encoding="utf-8") as f:
            counts = json.load(f)
        est = plan.estimate(counts, plan.load_coeffs(a.coeffs), project.load(a.workdir))
        if a.record:
            data = need_project(a.workdir)
            project.set_key(data, "analysis.counts", os.path.abspath(a.counts))
            project.set_key(data, "analysis.done", True)
            project.save(data, a.workdir)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(est, f, ensure_ascii=False, indent=2)
        out(est)
    elif a.action == "packages":
        pk = _plan_packages(a)
        if a.register:
            data = need_project(a.workdir)
            project.register_packages(data, pk["packages"], budget=pk["budget"], deferred=pk.get("deferred") or [])
            project.save(data, a.workdir)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(pk, f, ensure_ascii=False, indent=2)
        out(pk)
    elif a.action == "table":
        text = plan.table(_plan_packages(a), a.parallel, group=not a.detail)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                f.write(text)
        print(text, end="")
    elif a.action == "status":
        out(plan.status(need_project(a.workdir), a.stale_min, a.max_attempts))
    elif a.action == "update":
        data = need_project(a.workdir)
        pk = project.update_package(data, a.id, a.status, a.tokens_used, a.note, a.task_id)
        project.save(data, a.workdir)
        out(pk)


def main(argv=None):
    p = argparse.ArgumentParser(prog="rstool", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workdir", default=".", help="cartella del progetto (remaster.json)")
    g = p.add_subparsers(dest="group", required=True)

    s = g.add_parser("project", help="stato del progetto (remaster.json)")
    s.add_argument("action", choices=["init", "show", "set", "get", "decide", "phase", "missing", "spend"],
                   help="spend <servizio> <importo> --unit usd|credits --note ...: registra una spesa e controlla il tetto")
    s.add_argument("args", nargs="*")
    s.add_argument("--force", action="store_true")
    s.add_argument("--unit", choices=["usd", "credits"], default="usd", help="per spend")
    s.add_argument("--note", default="", help="per spend")
    s.set_defaults(fn=cmd_project)

    s = g.add_parser("engine", help="riconoscimento motore e MD5 dei file")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("detect"); x.add_argument("dir"); x.add_argument("--scummvm")
    x.set_defaults(fn=lambda a: out(detect.detect(a.dir, a.scummvm)))
    x = sg.add_parser("extract", help="estrazione senza Layer: esegue l'adattatore del repository privato e valida il dump")
    x.add_argument("--adapter", required=True, help="comando o script (.py) con {game} e {out}, altrimenti riceve --game/--out")
    x.add_argument("--game", default=".", help="cartella dei file del gioco (default: la corrente)")
    x.add_argument("--out", required=True, help="cartella del dump (formato in remaster_tools/extract.py)")
    x.add_argument("--timeout", type=int)
    x.set_defaults(fn=lambda a: out(extract.run_adapter(a.adapter, a.game, a.out, a.timeout)))
    x = sg.add_parser("validate-dump", help="controlla un dump (del Layer o di un adattatore) contro il contratto")
    x.add_argument("dump")
    x.set_defaults(fn=lambda a: out(extract.validate_dump(a.dump)))
    x = sg.add_parser("md5"); x.add_argument("dir"); x.add_argument("--out", required=True); x.add_argument("--version-name", default="default")
    x.set_defaults(fn=lambda a: out(release.game_md5(a.dir, a.out, a.version_name)))
    x = sg.add_parser("reference", help="emulatore o VM di riferimento per la piattaforma dell'originale")
    x.add_argument("--platform", required=True)
    x.set_defaults(fn=lambda a: out(platforms.reference_emulators(a.platform)))
    x = sg.add_parser("timing", help="durata dei passi misurata da una registrazione dello schermo")
    x.add_argument("video"); x.add_argument("--segments", help='JSON [{"name","start","duration"}] in secondi')
    x.add_argument("--crop", help="x,y,w,h dell'area di gioco nel video"); x.add_argument("--out")
    x.set_defaults(fn=cmd_timing)
    x = sg.add_parser("timing-compare", help="confronta le misure dell'originale e del remaster")
    x.add_argument("original"); x.add_argument("remaster"); x.add_argument("--tolerance", type=float, default=0.03)
    x.set_defaults(fn=lambda a: out(timing.compare(_json(a.original), _json(a.remaster), a.tolerance)))
    x = sg.add_parser("controls", help="fluidità di mouse e tasti dal log del driver (inputlog)")
    x.add_argument("log"); x.add_argument("--continuous", nargs="*", default=list(controls.CONTINUOUS),
                                          help="azioni che possono ripetersi a tasto premuto (scorrimento, camminata)")
    x.set_defaults(fn=lambda a: out(controls.analyze(a.log, tuple(a.continuous))))

    s = g.add_parser("key", help="chiavi RAC")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("frame"); x.add_argument("raw")
    x.set_defaults(fn=lambda a: out({"key": rawframe.read_raw(a.raw).key}))
    x = sg.add_parser("text"); x.add_argument("string"); x.add_argument("--codepage", default="cp850")
    x.set_defaults(fn=lambda a: out({"key": keys.text_key(a.string, a.codepage)}))

    s = g.add_parser("assets", help="inventario del dump")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("inventory"); x.add_argument("dump"); x.add_argument("--out", default="analysis/assets.csv")
    x.set_defaults(fn=lambda a: out(assets.inventory(a.dump, a.out)))
    x = sg.add_parser("coverage", help="cosa del dump il pacchetto sostituisce; voci mai richieste dal motore")
    x.add_argument("dump"); x.add_argument("pack"); x.add_argument("--lang")
    x.set_defaults(fn=lambda a: out(assets.coverage(a.dump, a.pack, a.lang)))
    x = sg.add_parser("canary", help="pacchetto di prova con marcatori visibili su testi, fondali, sprite (e voci)")
    x.add_argument("dump"); x.add_argument("--out", required=True); x.add_argument("--lang", required=True)
    x.add_argument("--codepage", default="cp850"); x.add_argument("--scale", type=int, default=3)
    x.add_argument("--voices", type=int, default=0)
    x.set_defaults(fn=lambda a: out(assets.canary(a.dump, a.out, a.lang, a.codepage, a.scale, a.voices)))

    s = g.add_parser("style", help="misure dello stile originale")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("analyze"); x.add_argument("dump"); x.add_argument("--out", default="analysis/style")
    x.set_defaults(fn=lambda a: out({k: v for k, v in style.analyze(a.dump, a.out).items() if k != "backgrounds"}
                                    | {"report": os.path.join(a.out, "style-metrics.json")}))

    s = g.add_parser("gfx", help="grafica HD")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("backends"); x.set_defaults(fn=lambda a: out(gfx.backends()))
    x = sg.add_parser("bg"); x.add_argument("src"); x.add_argument("--out", required=True)
    x.add_argument("--scale", type=int, default=3); x.add_argument("--recipe"); x.add_argument("--seed", type=int, default=1234)
    x.add_argument("--model", help="pesi spandrel (.pth/.safetensors, es. APISR RRDB) o nome modello ncnn; "
                                   "default REMASTER_MODEL_BG")
    x.add_argument("--no-ai", action="store_true"); x.add_argument("--format", choices=["png", "jpg"], default="png")
    x.add_argument("--no-resume", action="store_true", help="rifai anche le scene già fatte con lo stesso modello")
    x.set_defaults(fn=lambda a: out(gfx.batch_backgrounds(a.src, a.out, a.scale, a.recipe, a.seed, not a.no_ai, a.format,
                                                          a.model, not a.no_resume)))
    x = sg.add_parser("sprites", help="pipeline deterministica: upscaler, sagoma smussata, inchiostro, colori di bordo")
    x.add_argument("dump"); x.add_argument("--out", required=True)
    x.add_argument("--scale", type=int, default=3); x.add_argument("--recipe"); x.add_argument("--seed", type=int, default=1234)
    x.add_argument("--model", help="pesi spandrel (es. APISR GRL) o nome modello ncnn; default REMASTER_MODEL_SPR")
    x.add_argument("--no-ink", action="store_true", help="senza la fascia d'inchiostro sul contorno scuro")
    x.add_argument("--format", choices=["png", "jpg"], default="png", help="png (default, con alpha: usala col Layer comune); jpg solo se il motore ricostruisce l'alpha")
    x.add_argument("--ai", action="store_true", help="img2img per fotogramma: sconsigliato sulle animazioni (sfarfallio)")
    x.add_argument("--tag", default="RSPR")
    x.set_defaults(fn=lambda a: out(gfx.batch_sprites(a.dump, a.out, a.scale, a.recipe, a.seed, a.ai, a.tag.encode(),
                                                      a.model, not a.no_ink, a.format)))
    x = sg.add_parser("index"); x.add_argument("dump"); x.add_argument("hd"); x.add_argument("--out", required=True)
    x.add_argument("--scale", type=int, default=3); x.add_argument("--tag", default="RSPR")
    x.set_defaults(fn=lambda a: out(rawframe.build_index_from_dump(a.dump, a.hd, a.out, a.scale, a.tag.encode())))
    x = sg.add_parser("check"); x.add_argument("orig"); x.add_argument("hd")
    x.add_argument("--min-ssim", type=float, default=0.85); x.add_argument("--max-de", type=float, default=6.0)
    x.set_defaults(fn=lambda a: out(gfx.check_dirs(a.orig, a.hd, a.min_ssim, a.max_de)))
    x = sg.add_parser("compare"); x.add_argument("orig"); x.add_argument("hd"); x.add_argument("--out", required=True)
    x.set_defaults(fn=cmd_compare)

    s = g.add_parser("font", help="atlanti font HD")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("build"); x.add_argument("ttf"); x.add_argument("--name", required=True); x.add_argument("--out", default="remaster/fonts")
    x.add_argument("--size", type=int, default=36); x.add_argument("--scale", type=int, default=3)
    x.add_argument("--codepage", default="cp850"); x.add_argument("--outline", type=int, default=0)
    x.set_defaults(fn=cmd_font)
    x = sg.add_parser("from-bitmap", help="HD dei font bitmap originali (3x, angoli vivi)")
    x.add_argument("src", help="dump del font: JSON o cartella di PNG indicizzati <hex>.png")
    x.add_argument("--name", required=True); x.add_argument("--out", default="remaster/fonts")
    x.add_argument("--scale", type=int, default=3); x.add_argument("--codepage", default="cp437")
    x.add_argument("--extra-edition", help="dump dello stesso font da un'altra edizione dell'utente")
    x.add_argument("--compose-accents", action="store_true",
                   help="costruisce le accentate mancanti e rifà le maiuscole accorciate a piena altezza")
    x.add_argument("--texts", nargs="*", default=[], help="testi (TSV) i cui caratteri vanno garantiti")
    x.add_argument("--reserve", default="", help="codici hex usati dal motore, separati da virgola")
    x.add_argument("--slot-codepage", default="cp850")
    x.set_defaults(fn=cmd_font_bitmap)
    x = sg.add_parser("coverage", help="caratteri dei testi coperti da charmap e atlanti")
    x.add_argument("fonts"); x.add_argument("--texts", nargs="+", required=True)
    x.set_defaults(fn=cmd_font_coverage)

    s = g.add_parser("widescreen", help="16:9")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("geometry"); x.add_argument("--w", type=int, required=True); x.add_argument("--h", type=int, required=True)
    x.add_argument("--par", type=float, default=1.0, help="allungamento verticale del pixel: 1.0 quadrati (default); altro solo se deciso con `aspect`")
    x.set_defaults(fn=lambda a: out(widescreen.geometry(a.w, a.h, a.par)))
    x = sg.add_parser("aspect", help="proporzione del pixel: candidata da piattaforma, risoluzione, anno, tipo di arte")
    x.add_argument("--platform", required=True); x.add_argument("--w", type=int, required=True); x.add_argument("--h", type=int, required=True)
    x.add_argument("--year", type=int); x.add_argument("--art", choices=["pixel", "digitized"])
    x.set_defaults(fn=lambda a: out(platforms.pixel_aspect(a.platform, a.w, a.h, a.year, a.art)))
    x = sg.add_parser("aspect-auto", help="proporzione del pixel decisa da sola (tabella + forme rotonde misurate nel dump + misure); chiede solo nei casi dubbi")
    x.add_argument("--platform", required=True); x.add_argument("--w", type=int, required=True); x.add_argument("--h", type=int, required=True)
    x.add_argument("--year", type=int); x.add_argument("--art", choices=["pixel", "digitized"])
    x.add_argument("--evidence", nargs="+", help="cartelle o immagini del dump (fondali, oggetti, icone) dove cercare forme rotonde")
    x.add_argument("--measure", nargs="+", help="JSON salvati da `aspect-measure`")
    x.add_argument("--sheet", default="review/aspect.png", help="foglio di confronto (prodotto solo se si deve chiedere)")
    x.add_argument("--record", action="store_true", help="scrive graphics.pixel_aspect in remaster.json (e la decisione, se automatica)")
    x.set_defaults(fn=cmd_aspect_auto)
    x = sg.add_parser("aspect-sheet", help="stesse scene a pixel quadrati e allungati, affiancate")
    x.add_argument("images", nargs="+"); x.add_argument("--out", default="review/aspect.png")
    x.add_argument("--stretch", type=float, nargs="+", default=[1.0, 1.2])
    x.set_defaults(fn=lambda a: out(platforms.aspect_sheet(a.images, a.out, tuple(a.stretch))))
    x = sg.add_parser("aspect-measure", help="misura larghezza/altezza di una forma rotonda (disco, ruota, luna)")
    x.add_argument("images", nargs="+"); x.add_argument("--compose", help="CxR: ricompone più immagini in griglia (es. 2x2)")
    x.add_argument("--box", help="x,y,w,h attorno alla forma"); x.add_argument("--color", help="#rrggbb della forma")
    x.add_argument("--tolerance", type=int, default=40); x.add_argument("--out", help="immagine con il riquadro misurato")
    x.set_defaults(fn=lambda a: out(platforms.aspect_measure(
        a.images, tuple(int(v) for v in a.compose.lower().split("x")) if a.compose else None,
        tuple(int(v) for v in a.box.split(",")) if a.box else None, a.color, a.tolerance, out_path=a.out)))
    x = sg.add_parser("classify"); x.add_argument("src"); x.add_argument("--screen-w", type=int, required=True)
    x.add_argument("--screen-h", type=int, required=True); x.add_argument("--par", type=float, default=1.0)
    x.add_argument("--out", default="analysis/widescreen-plan.json")
    x.add_argument("--names", help="JSON {scena: nome della stanza} (default: <src>/names.json)")
    x.add_argument("--playfield-h", type=int, help="altezza dell'area di gioco (default: l'altezza più comune dei fondali)")
    x.set_defaults(fn=lambda a: out((lambda pl: {"counts": pl["counts"], "ui_bar": pl["ui_bar"], "plan": a.out})(
        widescreen.classify(a.src, a.screen_w, a.screen_h, a.par, a.out, a.names, a.playfield_h))))
    x = sg.add_parser("extend", help="varianti delle bande: LaMa 1x, LaMa+quilting, ricette, (fal.ai solo se approvato), bordi")
    x.add_argument("plan"); x.add_argument("--hd", required=True); x.add_argument("--out", default="review/widescreen")
    x.add_argument("--scale", type=int, default=3); x.add_argument("--recipe")
    x.add_argument("--lama", help="modello LaMa TorchScript (big-lama.pt): bande dipinte a 1x e poi ingrandite")
    x.add_argument("--no-quilt", action="store_true", help="senza la variante LaMa + quilting")
    x.add_argument("--no-sharpen", action="store_true")
    x.add_argument("--recipes", help='JSON {scena: {"kind": "rows"|"shift", ...}} per le stanze residue')
    x.add_argument("--only", nargs="*", help="solo queste scene")
    x.add_argument("--fal", action="store_true", help="aggiungi la variante fal.ai (a pagamento)")
    x.add_argument("--approved-images", type=int, default=0, help="immagini fal.ai approvate dall'utente per questo lotto")
    x.add_argument("--model", help="upscaler delle bande, lo stesso dei fondali (default REMASTER_MODEL_BG)")
    x.set_defaults(fn=cmd_ws_extend)
    x = sg.add_parser("fal-estimate", help="preventivo gratuito delle bande con fal.ai")
    x.add_argument("--plan", default="analysis/widescreen-plan.json"); x.add_argument("--scenes", type=int)
    x.add_argument("--attempts", type=int, default=2); x.add_argument("--price", type=float, default=falai.PRICE_USD)
    x.set_defaults(fn=cmd_fal_estimate)
    x = sg.add_parser("check", help="band_check e indice di nitidezza di un'immagine 16:9")
    x.add_argument("image"); x.add_argument("--left", type=int, required=True); x.add_argument("--right", type=int, required=True)
    x.set_defaults(fn=cmd_ws_check)
    x = sg.add_parser("apply"); x.add_argument("decisions"); x.add_argument("--plan", default="analysis/widescreen-plan.json")
    x.add_argument("--variants", default="review/widescreen"); x.add_argument("--out", default="remaster/gfx/bg")
    x.set_defaults(fn=lambda a: out(widescreen.apply_decisions(a.plan, a.decisions, a.variants, a.out)))

    s = g.add_parser("video", help="filmati: analisi, upscale fotogramma per fotogramma, ricodifica")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("probe", help="formato, risoluzione, fps, durata, audio (ffprobe) e stima dei tempi su CPU")
    x.add_argument("file"); x.set_defaults(fn=lambda a: out(video.probe(a.file)))
    x = sg.add_parser("upscale", help="fotogrammi 1:1, upscale deterministico con riuso dei fotogrammi identici, "
                                      "ricodifica con l'audio originale")
    x.add_argument("src", help="file video letto da ffmpeg, oppure cartella di PNG numerati (dump del motore)")
    x.add_argument("--out", required=True, help=".mkv / .mp4 (H.264) oppure .ogv (Theora)")
    x.add_argument("--scale", type=int, default=3)
    x.add_argument("--model", help="pesi spandrel o modello ncnn; default REMASTER_MODEL_BG (come i fondali)")
    x.add_argument("--fps", help="obbligatorio per una cartella di PNG (es. 15 o 30000/1001)")
    x.add_argument("--audio", help="file audio separato (cartella di PNG) o sostitutivo")
    x.add_argument("--work", help="cartella di lavoro (default <out>.work): ripartibile")
    x.add_argument("--crf", type=int, default=12); x.add_argument("--pix-fmt", default="yuv420p",
                                                                 choices=["yuv444p", "yuv420p"])
    x.add_argument("--max-frames", type=int, help="solo i primi N fotogrammi (prova)")
    x.add_argument("--clean", action="store_true", help="cancella la cartella di lavoro alla fine")
    x.add_argument("--interpolate", action="store_true", help=argparse.SUPPRESS)
    x.set_defaults(fn=cmd_video_upscale)

    s = g.add_parser("review", help="pagine HTML di revisione")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("gallery"); x.add_argument("--widescreen", required=True); x.add_argument("--variants", default="review/widescreen")
    x.add_argument("--out", default="review/widescreen.html"); x.add_argument("--title", default="Revisione 16:9")
    x.set_defaults(fn=lambda a: out(review.widescreen_gallery(a.widescreen, a.variants, a.out, a.title)))
    x = sg.add_parser("diff", help="regressione visiva: schermate con lo stesso nome in due passate")
    x.add_argument("before"); x.add_argument("after"); x.add_argument("--out", default="review/diff.html")
    x.add_argument("--threshold", type=float, default=0.002)
    x.set_defaults(fn=lambda a: out(review.diff_dirs(a.before, a.after, a.out, a.threshold)))
    x = sg.add_parser("compare"); x.add_argument("orig"); x.add_argument("hd"); x.add_argument("--out", default="review/compare.html")
    x.set_defaults(fn=cmd_review_compare)

    s = g.add_parser("text", help="copione, correzioni, traduzioni")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("catalog"); x.add_argument("dump"); x.add_argument("--lang", required=True); x.add_argument("--out", default="text/catalog.tsv")
    x.add_argument("--codepage", default="cp850")
    x.set_defaults(fn=lambda a: out(text.catalog(a.dump, a.lang, a.out, a.codepage)))
    x = sg.add_parser("export"); x.add_argument("catalog"); x.add_argument("--out", required=True); x.add_argument("--source-if-empty", action="store_true")
    x.set_defaults(fn=lambda a: out(text.export_lang(a.catalog, a.out, a.source_if_empty)))
    x = sg.add_parser("check"); x.add_argument("catalog"); x.add_argument("--font", required=True); x.add_argument("--codepage", default="cp850")
    x.set_defaults(fn=lambda a: out(text.check(a.catalog, a.font, a.codepage)))
    x = sg.add_parser("glyphs"); x.add_argument("files", nargs="+")
    x.set_defaults(fn=lambda a: out(text.glyphs(a.files)))
    x = sg.add_parser("accents"); x.add_argument("string")
    x.set_defaults(fn=lambda a: out({"text": text.italian_accents(a.string)}))

    s = g.add_parser("audio", help="musica ed effetti")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("backends"); x.set_defaults(fn=lambda a: out(audio.backends()))
    x = sg.add_parser("scan"); x.add_argument("dir"); x.set_defaults(fn=lambda a: out(audio.scan(a.dir)))
    x = sg.add_parser("midi-classify", help="brani ed effetti tra i MIDI estratti (durata e numero di note)")
    x.add_argument("dir"); x.add_argument("--min-seconds", type=float, default=20.0); x.add_argument("--min-notes", type=int, default=80)
    x.set_defaults(fn=lambda a: out(audio.midi_classify(a.dir, a.min_seconds, a.min_notes)))
    x = sg.add_parser("render-midi"); x.add_argument("mid"); x.add_argument("--soundfont", required=True); x.add_argument("--out", required=True)
    x.set_defaults(fn=lambda a: out({"written": audio.render_midi(a.mid, a.soundfont, a.out)}))
    x = sg.add_parser("master", help="un file a un livello fisso (per prove); per il gioco usa normalize + mix")
    x.add_argument("src"); x.add_argument("dst"); x.add_argument("--lufs", type=float, default=audio.MIX["music"])
    x.add_argument("--denoise", action="store_true"); x.add_argument("--declip", action="store_true")
    x.set_defaults(fn=lambda a: out({"written": audio.master(a.src, a.dst, a.lufs, denoise=a.denoise, declip=a.declip)}))
    x = sg.add_parser("normalize", help="fase 1: misura un gruppo (music, sfx, voice) e calcola i guadagni di normalizzazione")
    x.add_argument("group"); x.add_argument("paths", nargs="+"); x.add_argument("--out", default="analysis/audio-norm.json")
    x.add_argument("--reference", type=float, default=audio.REFERENCE_LUFS); x.add_argument("--policy", choices=["file", "group"])
    x.add_argument("--root", help="cartella di partenza per i nomi (sottocartelle mantenute)")
    x.add_argument("--declip", nargs="*", default=[], help="nomi (o parti di nomi) delle tracce già saturate nell'originale")
    x.add_argument("--loops", help='JSON {nome: [inizio, lunghezza] in campioni}: punti di loop da conservare')
    x.set_defaults(fn=lambda a: out({k: v for k, v in audio.normalize_group(a.group, a.paths, a.out, a.reference, a.policy,
                                                                          root=a.root, declip=a.declip,
                                                                          loops=_json(a.loops) if a.loops else None).items()
                                     if k != "files"}))
    x = sg.add_parser("mix", help="fase 2: livelli tra i gruppi e codifica unica dei file")
    x.add_argument("plan", nargs="?", default="analysis/audio-norm.json"); x.add_argument("--mix", help="audio/mix.json")
    x.add_argument("--out", default="remaster"); x.add_argument("--groups", nargs="*"); x.add_argument("--dry-run", action="store_true")
    # without --mix: audio.mix of remaster.json, then the defaults
    x.set_defaults(fn=lambda a: out(audio.apply_mix(a.plan, a.out, _mix_source(a), a.groups, a.dry_run)))
    x = sg.add_parser("mix-preview", help="prova d'ascolto: musica + effetto + battuta coi guadagni del mix")
    x.add_argument("--voice"); x.add_argument("--music"); x.add_argument("--sfx"); x.add_argument("--mix")
    x.add_argument("--plan", default="analysis/audio-norm.json"); x.add_argument("--out", default="review/mix.ogg")
    x.add_argument("--duration", type=float, default=12.0)
    x.add_argument("--music-offsets", type=float, nargs="+", default=[0.0], help="varianti della musica in dB, es. 0 -3 3")
    x.set_defaults(fn=lambda a: out(audio.mix_preview(a.out, a.voice, a.music, a.sfx, _mix_source(a), a.plan, a.duration,
                                                      tuple(a.music_offsets))))
    x = sg.add_parser("loudness"); x.add_argument("files", nargs="+")
    x.set_defaults(fn=lambda a: out({f: audio.loudness(f) for f in a.files}))
    x = sg.add_parser("sfx"); x.add_argument("dir"); x.add_argument("--out", default="remaster/sfx"); x.add_argument("--rates")
    x.add_argument("--default-rate", type=int, default=11025); x.add_argument("--raw-format", default="u8")
    x.add_argument("--lossless", action="store_true", help="FLAC da livellare poi con normalize + mix")
    x.set_defaults(fn=lambda a: out(audio.sfx_batch(a.dir, a.out, a.rates, a.default_rate, a.raw_format, lossless=a.lossless)))
    x = sg.add_parser("midi-diagnose", help="musica MIDI dinamica: note e programmi per canale, confronto tra "
                                            "versioni, distribuzione dell'energia per bande")
    x.add_argument("midi", nargs="*", help="uno o più .mid (versioni dello stesso brano per --compare)")
    x.add_argument("--table", help="JSON: tabella di conversione dei programmi del motore (128 voci o {src: gm})")
    x.add_argument("--fixes", help='JSON {gm: gm}: correzioni da provare dopo la tabella')
    x.add_argument("--compare", action="store_true", help="confronta le note per canale col primo MIDI")
    x.add_argument("--audio", nargs="*", default=[], help="rendering o registrazioni dal motore da misurare per bande")
    x.add_argument("--start", type=float, default=0.0); x.add_argument("--duration", type=float, default=30.0)
    x.set_defaults(fn=lambda a: out(_friendly(audio_midi.diagnose, a.midi, a.table, _json(a.fixes) if a.fixes else None,
                                              a.audio, a.compare, a.start, a.duration)))
    x = sg.add_parser("midi-remap", help="riscrive un MIDI come lo suona il motore su un sintetizzatore GM "
                                         "(solo per prove d'ascolto)")
    x.add_argument("src"); x.add_argument("dst"); x.add_argument("--table", required=True)
    x.add_argument("--fixes"); x.add_argument("--keep-sysex", action="store_true")
    x.add_argument("--reverb-send", type=int, help="CC91 su ogni canale all'inizio (mandata del riverbero del motore)")
    x.set_defaults(fn=lambda a: out(_friendly(audio_midi.remap, a.src, a.dst, a.table,
                                              _json(a.fixes) if a.fixes else None, not a.keep_sysex, a.reverb_send)))
    x = sg.add_parser("bands", help="baricentro, energia per bande, ottave gravi e nota dominante di registrazioni")
    x.add_argument("files", nargs="+"); x.add_argument("--start", type=float, default=0.0)
    x.add_argument("--duration", type=float, default=30.0)
    x.set_defaults(fn=lambda a: out([_friendly(audio_midi.bands, f, a.start, a.duration) for f in a.files]))
    x = sg.add_parser("sf2-compose", help="SoundFont composito da ricetta JSON (strategia orchestra)")
    x.add_argument("recipe"); x.add_argument("--out", required=True)
    x.set_defaults(fn=lambda a: out(_friendly(audio_sf2.compose, a.recipe, a.out)))
    x = sg.add_parser("sf2-info", help="versione (sf2/sf3), campioni e preset di un SoundFont")
    x.add_argument("soundfont")
    x.set_defaults(fn=lambda a: out(_friendly(audio_sf2.info, a.soundfont)))
    x = sg.add_parser("restore-speech", help="restauro del parlato ORIGINALE (giochi già parlati): FLAC da livellare poi")
    x.add_argument("dir"); x.add_argument("--out", default="audio/clean/voice")
    x.add_argument("--model", choices=["deepfilternet"], help="modello locale di pulizia della voce, se installato")
    x.set_defaults(fn=lambda a: out(audio.restore_speech_batch(a.dir, a.out, a.model)))

    s = g.add_parser("voice", help="doppiaggio ElevenLabs")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("script"); x.add_argument("catalog"); x.add_argument("--lang", required=True); x.add_argument("--out", required=True)
    x.add_argument("--protagonist", default="")
    x.set_defaults(fn=lambda a: out(voice.script(a.catalog, a.lang, a.out, a.protagonist)))
    x = sg.add_parser("generate"); x.add_argument("script"); x.add_argument("--cast", required=True); x.add_argument("--out", required=True)
    x.add_argument("--lang", required=True); x.add_argument("--limit", type=int); x.add_argument("--dry-run", action="store_true")
    x.add_argument("--mix", help="audio/mix.json (default: audio.mix del progetto)")
    x.add_argument("--direction", help="regia.tsv rivista di `voice direct` (colonna tag, recita)")
    x.set_defaults(fn=lambda a: out(voice.generate(a.script, a.cast, a.out, a.lang, limit=a.limit, dry_run=a.dry_run,
                                                   lufs=audio.load_mix(_mix_source(a))[0]["voice"],
                                                   direction=a.direction,
                                                   project_voice=(project.load(a.workdir) or {}).get("voice"))))
    x = sg.add_parser("direct", help="regia per battuta: scheda di contesto e tag proposto da rivedere")
    x.add_argument("script", help="copione TSV di `voice script`"); x.add_argument("--out", required=True, help="regia.tsv")
    x.add_argument("--context", type=int, default=2, help="battute prima/dopo nella stessa scena")
    x.add_argument("--lang", default="it"); x.add_argument("--rules", help="regole JSON (parole chiave, punteggiatura, cps)")
    x.add_argument("--cast", help="cast.json: le voci con \"register\": \"deep\" non ricevono tag energici")
    x.add_argument("--retag", action="store_true", help="ripropone anche dove il copione ha già un tag")
    x.set_defaults(fn=lambda a: out(regia.direct(a.script, a.out, a.context, a.lang, a.rules, a.cast, not a.retag)))
    x = sg.add_parser("reencode", help="ricodifica dalle MP3 conservate (nessuna spesa), es. dopo un cambio del mix")
    x.add_argument("script"); x.add_argument("--cast", required=True); x.add_argument("--out", required=True)
    x.add_argument("--mix", help="audio/mix.json (default: audio.mix del progetto)")
    x.set_defaults(fn=lambda a: out(voice.reencode(a.script, a.cast, a.out, audio.load_mix(_mix_source(a))[0]["voice"])))
    x = sg.add_parser("check"); x.add_argument("script"); x.add_argument("dir")
    x.set_defaults(fn=lambda a: out(voice.check(a.script, a.dir)))
    x = sg.add_parser("estimate", help="stima gratuita dei crediti: testi unici e lunghezza nella lingua di arrivo")
    x.add_argument("source", help="text.jsonl del dump o catalogo .tsv")
    x.add_argument("--dedupe", action=argparse.BooleanOptionalAction, default=True, help="ogni testo una volta (default)")
    x.add_argument("--expand", type=float, default=1.0, help="lunghezza della lingua di arrivo (it su en ≈ 1.12)")
    x.add_argument("--retake", type=float, default=1.15); x.add_argument("--codepage", default="cp850")
    x.set_defaults(fn=lambda a: out(voice.estimate(a.source, a.dedupe, a.expand, a.retake, a.codepage)))
    x = sg.add_parser("transcribe", help="trascrizione locale e gratuita delle battute (faster-whisper o whisper.cpp)")
    x.add_argument("dir"); x.add_argument("--lang", required=True); x.add_argument("--out", default="qa/trascrizioni.json")
    x.add_argument("--model", default="small", help="faster-whisper: tiny/base/small/medium; whisper.cpp: file ggml")
    x.add_argument("--backend", choices=["faster-whisper", "whisper.cpp"])
    x.set_defaults(fn=lambda a: out(transcribe.transcribe_dir(a.dir, a.out, a.lang, a.model, a.backend)))
    x = sg.add_parser("transcripts", help="confronta le trascrizioni automatiche ({chiave: testo}) col copione")
    x.add_argument("script"); x.add_argument("transcripts")
    x.set_defaults(fn=lambda a: out(voice.check_transcripts(a.script, a.transcripts)))
    x = sg.add_parser("segments", help="tratti di file lunghi: trascrizione locale e gruppi di parlanti (TSV)")
    x.add_argument("audio", nargs="+", help="file audio lunghi (trailer, clip) o cartelle")
    x.add_argument("--lang", default="it"); x.add_argument("--out", required=True, help="segmenti.tsv")
    x.add_argument("--model", default="small", help="modello faster-whisper (small, medium...)")
    x.add_argument("--speakers", type=int, help="numero di parlanti, se noto (più affidabile della soglia)")
    x.add_argument("--threshold", type=float, help="soglia di distanza per i gruppi (default del tipo di impronta)")
    x.add_argument("--prints", choices=("auto", "resemblyzer", "simple"), default="auto",
                   help="impronte vocali: resemblyzer se installato, altrimenti semplici")
    x.set_defaults(fn=lambda a: out(_friendly(voiceseg.segments, a.audio, a.out, a.lang, a.model, a.speakers,
                                              a.threshold, a.prints)))
    x = sg.add_parser("reference", help="misure del parlato di riferimento (solo numeri; i frammenti restano locali)")
    x.add_argument("audio", nargs="*", help="frammenti puliti del personaggio (file o cartelle)")
    x.add_argument("--out", required=True); x.add_argument("--start", type=float); x.add_argument("--end", type=float)
    x.add_argument("--segments", help="TSV di `voice segments`: misura i tratti senza tagliare i file")
    x.add_argument("--group", help="gruppo (o gruppi, separati da virgola) del TSV da misurare")
    x.add_argument("--select", help="righe del TSV da misurare, per id: 3,5-7")
    x.add_argument("--gender", help="genere del personaggio (male, female) per il controllo dell'altezza")
    x.add_argument("--age", help="età del personaggio (young, middle_aged, old, child)")
    x.add_argument("--delete-after", action="store_true", help="cancella l'audio misurato dopo la misura")
    x.set_defaults(fn=lambda a: out(_friendly(voiceref.reference, a.audio, a.out, a.start, a.end, a.delete_after,
                                              a.segments, a.group, a.select, a.gender, a.age)))
    x = sg.add_parser("measure", help="misura le anteprime delle voci candidate una volta sola (riusabili)")
    x.add_argument("candidates", help="file o cartella di anteprime, o voices.json (voice_id, name, file o preview_url)")
    x.add_argument("--out", required=True, help="misure.json (le voci già misurate non si rimisurano)")
    x.add_argument("--cache", help="dove scaricare le anteprime (default: previews/ accanto a --out)")
    x.set_defaults(fn=lambda a: out(_friendly(voiceref.measure, a.candidates, a.out, a.cache)))
    x = sg.add_parser("match", help="ordina le voci esistenti della libreria per somiglianza al riferimento")
    x.add_argument("ref")
    x.add_argument("--candidates", help="cartella di anteprime audio o voices.json (voice_id, name, file o preview_url)")
    x.add_argument("--measured", help="misure.json di `voice measure` (niente nuove misure)")
    x.add_argument("--gender", help="genere del personaggio, se il riferimento non lo dichiara")
    x.add_argument("--age", help="età del personaggio, se il riferimento non la dichiara")
    x.add_argument("--strict", action="store_true", help="escludi le candidate con genere o età dichiarati diversi")
    x.add_argument("--top", type=int, default=5); x.add_argument("--out", required=True)
    x.add_argument("--cache", help="dove scaricare le anteprime (default: previews/ accanto a --out)")
    x.set_defaults(fn=lambda a: out(_friendly(voiceref.match, a.ref, a.candidates, a.top, a.out, a.cache,
                                              a.measured, a.gender, a.age, a.strict)))

    s = g.add_parser("ui", help="interfaccia del motore nello stile del gioco")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("palette", help="ruoli di colore proposti da uno screenshot dell'interfaccia originale")
    x.add_argument("screenshot"); x.add_argument("--out", default="analysis/ui-palette.json")
    x.set_defaults(fn=cmd_ui_palette)
    x = sg.add_parser("theme", help="tema GUI di ScummVM ricolorato (stesso commit del fork)")
    x.add_argument("--base", required=True, help="<scummvm>/gui/themes/scummremastered")
    x.add_argument("--roles", required=True); x.add_argument("--name", required=True)
    x.add_argument("--out", required=True); x.add_argument("--font"); x.add_argument("--logo")
    x.set_defaults(fn=lambda a: out(theme.build(a.base, _json(a.roles), a.out, a.name, a.font, a.logo)))

    s = g.add_parser("hint", help="aiuti in gioco (hint/<lingua>.txt)")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("check"); x.add_argument("files", nargs="+"); x.add_argument("--vocab")
    x.set_defaults(fn=lambda a: out(hints.validate(a.files, a.vocab)))

    s = g.add_parser("manual", help="manuale di gioco (manual/<lingua>.md)")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("check"); x.add_argument("md"); x.add_argument("--codepage")
    x.set_defaults(fn=lambda a: out(manual.check(a.md, a.codepage)))
    x = sg.add_parser("ocr", help="testo di un PDF (manuale, guida agli indizi); OCR se il PDF è solo immagini")
    x.add_argument("pdf"); x.add_argument("--out", required=True); x.add_argument("--dpi", type=int, default=250)
    x.add_argument("--lang", default="eng", help="lingue di tesseract, es. eng o ita+eng")
    x.set_defaults(fn=lambda a: out(manual.ocr(a.pdf, a.out, a.dpi, a.lang)))
    x = sg.add_parser("html"); x.add_argument("md"); x.add_argument("--out", required=True)
    x.add_argument("--colors", help="JSON {bg, panel, text, accent} o i ruoli di `ui palette`"); x.add_argument("--lang", default="it")
    x.set_defaults(fn=lambda a: out(manual.to_html(a.md, a.out, colors=_json(a.colors) if a.colors else None, lang=a.lang)))

    s = g.add_parser("recipe", help="ricette riproducibili")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("run"); x.add_argument("recipe"); x.add_argument("--game", required=True); x.add_argument("--out", required=True)
    x.add_argument("--engine"); x.add_argument("--work"); x.add_argument("--only", nargs="*"); x.add_argument("--dry-run", action="store_true")
    x.set_defaults(fn=lambda a: out(recipe.run(a.recipe, a.game, a.out, a.engine, a.work, a.only, a.dry_run)))

    s = g.add_parser("release", help="pacchetto distribuibile")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("package"); x.add_argument("--out", default="release"); x.add_argument("--game-md5", required=True)
    x.add_argument("--patches"); x.add_argument("--engines"); x.add_argument("--remaster"); x.add_argument("--recipes")
    x.add_argument("--licenses"); x.add_argument("--version", default="1.0.0")
    x.set_defaults(fn=lambda a: out({"package": release.package(need_project(a.workdir), a.out, a.game_md5, a.patches, a.engines,
                                                                a.remaster, a.recipes, a.licenses, a.version)}))
    x = sg.add_parser("budget", help="peso del pacchetto e memoria per desktop, Android, web")
    x.add_argument("remaster"); x.add_argument("--targets", nargs="+", default=list(release.TARGETS),
                                               choices=list(release.TARGETS))
    x.set_defaults(fn=lambda a: out(release.budget(a.remaster, tuple(a.targets))))
    x = sg.add_parser("verify"); x.add_argument("root"); x.add_argument("--game-md5")
    x.set_defaults(fn=lambda a: out(release.verify(a.root, a.game_md5)))

    s = g.add_parser("plan", help="piano: stime, pacchetti di lavoro per sotto-sessioni, tabella, stato")
    sg = s.add_subparsers(dest="action", required=True)
    for name, hlp in (("estimate", "tempi, costi e token dai conteggi dell'analisi"),
                      ("packages", "pacchetti sotto il budget di token, dipendenze e gruppi paralleli"),
                      ("table", "tabella markdown con emoji, tempi, costi, token e totali")):
        x = sg.add_parser(name, help=hlp)
        x.add_argument("counts", help="JSON dei conteggi dell'analisi")
        x.add_argument("--coeffs", help="JSON che sovrascrive i coefficienti di plan.COEFFS")
        x.add_argument("--out")
        if name == "estimate":
            x.add_argument("--record", action="store_true", help="segna l'analisi come fatta in remaster.json")
        else:
            x.add_argument("--paid", default="auto", help="auto (dal progetto), none, all, fal, voice, fal,voice")
            x.add_argument("--budget", type=int, help="token per sotto-sessione (default dal progetto, 200000)")
        if name == "packages":
            x.add_argument("--register", action="store_true", help="scrive i pacchetti in remaster.json")
        if name == "table":
            x.add_argument("--parallel", type=int, default=3, help="sotto-sessioni contemporanee")
            x.add_argument("--detail", action="store_true", help="una riga per lotto (default: lotti raggruppati)")
        x.set_defaults(fn=cmd_plan)
    x = sg.add_parser("status", help="pacchetti in corso, fermi, falliti, da riavviare o fermare")
    x.add_argument("--stale-min", type=int, default=30, help="minuti senza avanzamento = fermo")
    x.add_argument("--max-attempts", type=int, default=3)
    x.set_defaults(fn=cmd_plan)
    x = sg.add_parser("update", help="aggiorna un pacchetto nel registro (stato, token usati, nota)")
    x.add_argument("id")
    x.add_argument("--status", choices=project.PACKAGE_STATES)
    x.add_argument("--tokens-used", type=int)
    x.add_argument("--note")
    x.add_argument("--task-id")
    x.set_defaults(fn=cmd_plan)

    a = p.parse_args(argv)
    return a.fn(a)


def cmd_compare(a):
    from PIL import Image
    from remaster_tools import imaging
    orig = rawframe.read_raw(a.orig).rgb() if a.orig.endswith(".raw") else Image.open(a.orig)
    hd = Image.open(a.hd)
    img = imaging.side_by_side(orig, hd)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    img.save(a.out)
    out({"written": a.out, **gfx.check_pair(orig.convert("RGB"), hd)})


def cmd_font(a):
    os.makedirs(a.out, exist_ok=True)
    out(font.build(a.ttf, os.path.join(a.out, a.name), a.size, a.scale, a.codepage, a.outline))


def cmd_font_bitmap(a):
    chars = "".join(text.glyphs(a.texts).values()) if a.texts else ""
    r = font_bitmap.from_bitmap(a.src, a.out, a.name, a.scale, a.codepage, a.extra_edition,
                                a.compose_accents, chars, [c for c in a.reserve.split(",") if c],
                                a.slot_codepage)
    out(r)
    if r["verify_mismatch"]:
        sys.exit(1)


def cmd_font_coverage(a):
    r = font_bitmap.coverage(a.fonts, a.texts)
    out(r)
    if not r["ok"]:
        sys.exit(1)


def _json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _mix_source(a):
    """--mix file, else audio.mix of remaster.json, else the defaults of audio.MIX."""
    if getattr(a, "mix", None):
        return a.mix
    data = project.load(a.workdir)
    return (data or {}).get("audio", {}).get("mix") or None


def cmd_ui_palette(a):
    roles = theme.propose_palette(a.screenshot)
    out({"roles": roles, "file": theme.save_roles(roles, a.out)})


def cmd_ws_extend(a):
    rec = gfx.load_recipe(a.recipe, "background_extension") if a.recipe else None
    paid = None
    if a.fal:
        data = project.load(a.workdir)
        if data is None:
            sys.exit("fal.ai richiede il progetto (remaster.json, --workdir) con graphics.widescreen.fal_ai = true")
        try:
            chosen = project.get_key(data, "graphics.widescreen.fal_ai")
        except KeyError:
            chosen = None
        if chosen is not True:
            sys.exit("fal.ai non scelto nell'intervista (graphics.widescreen.fal_ai): chiedi all'utente prima")
        if not os.environ.get("FAL_KEY"):
            sys.exit("FAL_KEY non impostata (va nei segreti, mai in chat)")
        if a.approved_images <= 0:
            sys.exit("serve --approved-images N: il numero di immagini approvate dall'utente dopo il preventivo "
                     "(`widescreen fal-estimate`)")
        os.makedirs(a.out, exist_ok=True)
        budget = falai.Budget(a.approved_images, os.path.join(a.out, "fal-spesa.jsonl"))
        paid = falai.fill_function(budget)
    plan = widescreen.make_extensions(a.plan, a.hd, a.out, a.scale, rec, lama=a.lama, quilting=not a.no_quilt,
                                      sharpen=not a.no_sharpen, paid_fill=paid,
                                      recipes=_json(a.recipes) if a.recipes else None, only=a.only,
                                      model=a.model)
    res = {"scenes_with_variants": sum(1 for s in plan["scenes"] if s.get("variants")), "variants_dir": a.out}
    if paid is not None:
        res["fal_images_used"] = budget.used
    out(res)


def cmd_video_upscale(a):
    if a.interpolate:
        sys.exit("--interpolate non è implementato: l'interpolazione (RIFE) cambia il ritmo dell'animatore; "
                 "va proposta su 2-3 filmati di prova e approvata (skills/hd-graphics)")
    out(video.upscale(a.src, a.out, a.scale, a.model, a.fps, a.audio, a.work, a.crf, a.pix_fmt, a.max_frames,
                      keep_work=not a.clean, log=lambda m: print(m, file=sys.stderr)))


def cmd_fal_estimate(a):
    n = a.scenes
    if n is None:
        n = widescreen.count_inventable(_json(a.plan))
    out(falai.estimate(n, a.attempts, a.price))


def cmd_ws_check(a):
    from PIL import Image
    im = Image.open(a.image)
    from remaster_tools import bands
    out({"band_check": bands.band_check(im, a.left, a.right), "sharpness": bands.sharpness_index(im, a.left, a.right)})


def cmd_timing(a):
    segs = _json(a.segments) if a.segments else None
    crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
    res = timing.measure(a.video, segs, crop)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
    out(res)


def cmd_review_compare(a):
    pairs = []
    for name in sorted(os.listdir(a.orig)):
        scene, ext = os.path.splitext(name)
        if ext.lower() not in (".raw", ".png"):
            continue
        if ext.lower() == ".png" and os.path.exists(os.path.join(a.orig, scene + ".raw")):
            continue
        for e in (".png", ".jpg"):
            hp = os.path.join(a.hd, scene + e)
            if os.path.exists(hp):
                pairs.append((scene, os.path.join(a.orig, name), hp))
                break
    out(review.compare_gallery(pairs, a.out))


if __name__ == "__main__":
    sys.exit(main())
