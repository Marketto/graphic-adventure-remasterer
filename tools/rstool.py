#!/usr/bin/env python3
"""rstool — command line of the Remaster Studio pipeline. Every command prints JSON.

Run `rstool.py <group> -h` for the commands of a group:
  project, engine, key, assets, style, gfx, font, widescreen, review, text, audio, voice, ui, hint,
  manual, recipe, release
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from remaster_tools import (assets, audio, controls, detect, falai, font, gfx, hints, keys,  # noqa: E402
                            manual, platforms, project, rawframe, recipe, release, review, style,
                            text, theme, timing, voice, widescreen)


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


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


def main(argv=None):
    p = argparse.ArgumentParser(prog="rstool", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workdir", default=".", help="cartella del progetto (remaster.json)")
    g = p.add_subparsers(dest="group", required=True)

    s = g.add_parser("project", help="stato del progetto (remaster.json)")
    s.add_argument("action", choices=["init", "show", "set", "get", "decide", "phase", "missing"])
    s.add_argument("args", nargs="*")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_project)

    s = g.add_parser("engine", help="riconoscimento motore e MD5 dei file")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("detect"); x.add_argument("dir"); x.add_argument("--scummvm")
    x.set_defaults(fn=lambda a: out(detect.detect(a.dir, a.scummvm)))
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
    x.add_argument("log")
    x.set_defaults(fn=lambda a: out(controls.analyze(a.log)))

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
    x.add_argument("--no-ai", action="store_true"); x.add_argument("--format", choices=["png", "jpg"], default="png")
    x.set_defaults(fn=lambda a: out(gfx.batch_backgrounds(a.src, a.out, a.scale, a.recipe, a.seed, not a.no_ai, a.format)))
    x = sg.add_parser("sprites"); x.add_argument("dump"); x.add_argument("--out", required=True)
    x.add_argument("--scale", type=int, default=3); x.add_argument("--recipe"); x.add_argument("--seed", type=int, default=1234)
    x.add_argument("--ai", action="store_true", help="img2img per fotogramma: sconsigliato sulle animazioni (sfarfallio)")
    x.add_argument("--tag", default="RSPR")
    x.set_defaults(fn=lambda a: out(gfx.batch_sprites(a.dump, a.out, a.scale, a.recipe, a.seed, a.ai, a.tag.encode())))
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

    s = g.add_parser("widescreen", help="16:9")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("geometry"); x.add_argument("--w", type=int, required=True); x.add_argument("--h", type=int, required=True)
    x.add_argument("--par", type=float, default=1.0, help="allungamento verticale del pixel: 1.0 quadrati (default); altro solo se deciso con `aspect`")
    x.set_defaults(fn=lambda a: out(widescreen.geometry(a.w, a.h, a.par)))
    x = sg.add_parser("aspect", help="proporzione del pixel: candidata da piattaforma, risoluzione, anno, tipo di arte")
    x.add_argument("--platform", required=True); x.add_argument("--w", type=int, required=True); x.add_argument("--h", type=int, required=True)
    x.add_argument("--year", type=int); x.add_argument("--art", choices=["pixel", "digitized"])
    x.set_defaults(fn=lambda a: out(platforms.pixel_aspect(a.platform, a.w, a.h, a.year, a.art)))
    x = sg.add_parser("aspect-sheet", help="stesse scene a pixel quadrati e allungati, affiancate")
    x.add_argument("images", nargs="+"); x.add_argument("--out", default="review/aspect.png")
    x.add_argument("--stretch", type=float, nargs="+", default=[1.0, 1.2])
    x.set_defaults(fn=lambda a: out(platforms.aspect_sheet(a.images, a.out, tuple(a.stretch))))
    x = sg.add_parser("classify"); x.add_argument("src"); x.add_argument("--screen-w", type=int, required=True)
    x.add_argument("--screen-h", type=int, required=True); x.add_argument("--par", type=float, default=1.0)
    x.add_argument("--out", default="analysis/widescreen-plan.json")
    x.set_defaults(fn=lambda a: out({"counts": widescreen.classify(a.src, a.screen_w, a.screen_h, a.par, a.out)["counts"], "plan": a.out}))
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

    s = g.add_parser("review", help="pagine HTML di revisione")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("gallery"); x.add_argument("--widescreen", required=True); x.add_argument("--variants", default="review/widescreen")
    x.add_argument("--out", default="review/widescreen.html"); x.add_argument("--title", default="Revisione 16:9")
    x.set_defaults(fn=lambda a: out(review.widescreen_gallery(a.widescreen, a.variants, a.out, a.title)))
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
    x.set_defaults(fn=lambda a: out({k: v for k, v in audio.normalize_group(a.group, a.paths, a.out, a.reference, a.policy,
                                                                          root=a.root).items() if k != "files"}))
    x = sg.add_parser("mix", help="fase 2: livelli tra i gruppi e codifica unica dei file")
    x.add_argument("plan", nargs="?", default="analysis/audio-norm.json"); x.add_argument("--mix", help="audio/mix.json")
    x.add_argument("--out", default="remaster"); x.add_argument("--groups", nargs="*"); x.add_argument("--dry-run", action="store_true")
    x.set_defaults(fn=lambda a: out(audio.apply_mix(a.plan, a.out, a.mix, a.groups, a.dry_run)))
    x = sg.add_parser("mix-preview", help="prova d'ascolto: musica + effetto + battuta coi guadagni del mix")
    x.add_argument("--voice"); x.add_argument("--music"); x.add_argument("--sfx"); x.add_argument("--mix")
    x.add_argument("--plan", default="analysis/audio-norm.json"); x.add_argument("--out", default="review/mix.ogg")
    x.add_argument("--duration", type=float, default=12.0)
    x.add_argument("--music-offsets", type=float, nargs="+", default=[0.0], help="varianti della musica in dB, es. 0 -3 3")
    x.set_defaults(fn=lambda a: out(audio.mix_preview(a.out, a.voice, a.music, a.sfx, a.mix, a.plan, a.duration,
                                                      tuple(a.music_offsets))))
    x = sg.add_parser("loudness"); x.add_argument("files", nargs="+")
    x.set_defaults(fn=lambda a: out({f: audio.loudness(f) for f in a.files}))
    x = sg.add_parser("sfx"); x.add_argument("dir"); x.add_argument("--out", default="remaster/sfx"); x.add_argument("--rates")
    x.add_argument("--default-rate", type=int, default=11025); x.add_argument("--raw-format", default="u8")
    x.add_argument("--lossless", action="store_true", help="FLAC da livellare poi con normalize + mix")
    x.set_defaults(fn=lambda a: out(audio.sfx_batch(a.dir, a.out, a.rates, a.default_rate, a.raw_format, lossless=a.lossless)))

    s = g.add_parser("voice", help="doppiaggio ElevenLabs")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("script"); x.add_argument("catalog"); x.add_argument("--lang", required=True); x.add_argument("--out", required=True)
    x.add_argument("--protagonist", default="")
    x.set_defaults(fn=lambda a: out(voice.script(a.catalog, a.lang, a.out, a.protagonist)))
    x = sg.add_parser("generate"); x.add_argument("script"); x.add_argument("--cast", required=True); x.add_argument("--out", required=True)
    x.add_argument("--lang", required=True); x.add_argument("--limit", type=int); x.add_argument("--dry-run", action="store_true")
    x.set_defaults(fn=lambda a: out(voice.generate(a.script, a.cast, a.out, a.lang, limit=a.limit, dry_run=a.dry_run)))
    x = sg.add_parser("check"); x.add_argument("script"); x.add_argument("dir")
    x.set_defaults(fn=lambda a: out(voice.check(a.script, a.dir)))
    x = sg.add_parser("transcripts", help="confronta le trascrizioni automatiche ({chiave: testo}) col copione")
    x.add_argument("script"); x.add_argument("transcripts")
    x.set_defaults(fn=lambda a: out(voice.check_transcripts(a.script, a.transcripts)))

    s = g.add_parser("ui", help="interfaccia del motore nello stile del gioco")
    sg = s.add_subparsers(dest="action", required=True)
    x = sg.add_parser("palette", help="ruoli di colore proposti da uno screenshot dell'interfaccia originale")
    x.add_argument("screenshot"); x.add_argument("--out", default="analysis/ui-palette.json")
    x.set_defaults(fn=lambda a: out({"roles": theme.propose_palette(a.screenshot),
                                     "file": theme.save_roles(theme.propose_palette(a.screenshot), a.out)}))
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
    x = sg.add_parser("verify"); x.add_argument("root"); x.add_argument("--game-md5")
    x.set_defaults(fn=lambda a: out(release.verify(a.root, a.game_md5)))

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


def _json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_ws_extend(a):
    rec = gfx.load_recipe(a.recipe, "background_extension") if a.recipe else None
    paid = None
    if a.fal:
        data = project.load(a.workdir)
        try:
            chosen = project.get_key(data, "graphics.widescreen.fal_ai") if data is not None else None
        except KeyError:
            chosen = None
        if data is not None and chosen is not True:
            sys.exit("fal.ai non scelto nell'intervista (graphics.widescreen.fal_ai): chiedi all'utente prima")
        if a.approved_images <= 0:
            sys.exit("serve --approved-images N: il numero di immagini approvate dall'utente dopo il preventivo "
                     "(`widescreen fal-estimate`)")
        os.makedirs(a.out, exist_ok=True)
        budget = falai.Budget(a.approved_images, os.path.join(a.out, "fal-spesa.jsonl"))
        paid = falai.fill_function(budget)
    plan = widescreen.make_extensions(a.plan, a.hd, a.out, a.scale, rec, lama=a.lama, quilting=not a.no_quilt,
                                      sharpen=not a.no_sharpen, paid_fill=paid,
                                      recipes=_json(a.recipes) if a.recipes else None, only=a.only)
    res = {"scenes_with_variants": sum(1 for s in plan["scenes"] if s.get("variants")), "variants_dir": a.out}
    if paid is not None:
        res["fal_images_used"] = budget.used
    out(res)


def cmd_fal_estimate(a):
    n = a.scenes
    if n is None:
        plan = _json(a.plan)
        n = sum(1 for s in plan["scenes"] if s["class"] in ("open-static", "scroll-narrow"))
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
