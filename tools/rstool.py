#!/usr/bin/env python3
"""rstool — command line of the Remaster Studio pipeline. Every command prints JSON.

Run `rstool.py <group> -h` for the commands of a group:
  project, engine, key, assets, style, gfx, font, widescreen, review, text, audio, voice, recipe, release
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from remaster_tools import (assets, audio, detect, font, gfx, keys, project, rawframe,  # noqa: E402
                            recipe, release, review, style, text, voice, widescreen)


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
    x.add_argument("--par", type=float, default=1.0, help="1.0 pixel quadrati (default), 1.2 con correzione 4:3")
    x.set_defaults(fn=lambda a: out(widescreen.geometry(a.w, a.h, a.par)))
    x = sg.add_parser("classify"); x.add_argument("src"); x.add_argument("--screen-w", type=int, required=True)
    x.add_argument("--screen-h", type=int, required=True); x.add_argument("--par", type=float, default=1.0)
    x.add_argument("--out", default="analysis/widescreen-plan.json")
    x.set_defaults(fn=lambda a: out({"counts": widescreen.classify(a.src, a.screen_w, a.screen_h, a.par, a.out)["counts"], "plan": a.out}))
    x = sg.add_parser("extend"); x.add_argument("plan"); x.add_argument("--hd", required=True); x.add_argument("--out", default="review/widescreen")
    x.add_argument("--scale", type=int, default=3); x.add_argument("--recipe")
    x.add_argument("--lama", help="modello LaMa TorchScript (big-lama.pt): bande dipinte a 1x e poi ingrandite")
    x.set_defaults(fn=cmd_ws_extend)
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
    x = sg.add_parser("master", help="livello fisso: musica -25 LUFS (default), voci -18, effetti al massimo -16")
    x.add_argument("src"); x.add_argument("dst"); x.add_argument("--lufs", type=float, default=audio.LEVELS["music"])
    x.add_argument("--denoise", action="store_true"); x.add_argument("--declip", action="store_true")
    x.set_defaults(fn=lambda a: out({"written": audio.master(a.src, a.dst, a.lufs, denoise=a.denoise, declip=a.declip)}))
    x = sg.add_parser("loudness"); x.add_argument("files", nargs="+")
    x.set_defaults(fn=lambda a: out({f: audio.loudness(f) for f in a.files}))
    x = sg.add_parser("sfx"); x.add_argument("dir"); x.add_argument("--out", default="remaster/sfx"); x.add_argument("--rates")
    x.add_argument("--default-rate", type=int, default=11025); x.add_argument("--raw-format", default="u8")
    x.set_defaults(fn=lambda a: out(audio.sfx_batch(a.dir, a.out, a.rates, a.default_rate, a.raw_format)))

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


def cmd_ws_extend(a):
    rec = gfx.load_recipe(a.recipe, "background_extension") if a.recipe else None
    plan = widescreen.make_extensions(a.plan, a.hd, a.out, a.scale, rec, lama=a.lama)
    out({"scenes_with_variants": sum(1 for s in plan["scenes"] if s.get("variants")), "variants_dir": a.out})


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
