"""Usage census, generation gate, speaker audit, deletion guard, roadmap (invented examples)."""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from remaster_tools import project, usage, voice  # noqa: E402
import guard_deletions  # noqa: E402

SYN = {"line_comment": ["#"], "line_blocks": [["[", "]"]], "blocks": [["/*", "*/"]],
       "strict_ext": {"sfx": ".sfx"}, "flag_set": r"\bSET\s+(\w+)", "flag_need": r"\bIF\s+(\w+)"}


def _game(tmp):
    scr = tmp / "scripts"
    scr.mkdir()
    (scr / "harbour.scr").write_text(
        "ZONE crate\n  SOUND creak.sfx\n  ANIM gull\n# SOUND foghorn.sfx\n[\nZONE oldboat\n  SOUND bell.sfx\n]\n"
        "ZONE pier /* SOUND splash.sfx */ ANIM wave\nSAY \"Ahoy // matey\" rope.sfx\nIF MET_KEEPER\n  SAY keeper_hint\nSET OPENED\n", encoding="utf-8")
    ast = tmp / "assets"
    ast.mkdir()
    for n in ("creak.sfx", "foghorn.sfx", "bell.sfx", "splash.sfx", "never.sfx", "gull.ani", "wave.ani", "waves.ani", "rope.sfx"):
        (ast / n).write_bytes(n.encode())
    (ast / "copy.ani").write_bytes(b"gull.ani")
    return scr, ast


def test_census_states_and_candidates(tmp_path):
    scr, ast = _game(tmp_path)
    (tmp_path / "syn.json").write_text(json.dumps(SYN))
    log = tmp_path / "run.log"
    log.write_text("load creak.sfx\nanim gull\n")
    res = usage.census(str(scr), str(ast), syntax=str(tmp_path / "syn.json"), loaded_log=str(log),
                       out_csv=str(tmp_path / "u.csv"), candidates_tsv=str(tmp_path / "c.tsv"))
    st = {r["name"]: r for r in csv.DictReader(open(tmp_path / "u.csv", encoding="utf-8"))}
    assert st["creak.sfx"]["status"] == "used" and st["creak.sfx"]["verified"] == "1"
    assert st["foghorn.sfx"]["status"] == "commented"          # line comment
    assert st["bell.sfx"]["status"] == "commented"             # line block
    assert st["splash.sfx"]["status"] == "commented"           # inline block
    assert st["never.sfx"]["status"] == "unused"
    assert st["wave.ani"]["status"] == "used"
    assert st["rope.sfx"]["status"] == "used"                  # "//" inside a string is not a comment
    assert st["waves.ani"]["status"] == "unused"               # whole tokens only, no substring match
    assert st["gull.ani"]["duplicate_of"] == "copy.ani"        # same bytes, first one wins
    assert res["dead_flag_branches"] == 1                      # MET_KEEPER is required but never set
    cand = open(tmp_path / "c.tsv", encoding="utf-8").read()
    assert "bell.sfx" in cand and "MET_KEEPER" in cand


def test_gate_blocks_unused_and_warns(tmp_path):
    scr, ast = _game(tmp_path)
    usage.census(str(scr), str(ast), syntax=SYN, out_csv=str(tmp_path / "u.csv"))
    batch = tmp_path / "b.json"
    batch.write_text(json.dumps({"items": [
        {"name": "creak.sfx", "kind": "sfx", "duration": 0.2, "out": "creak_11025"},
        {"name": "creak.sfx", "kind": "sfx", "duration": 0.8, "out": "creak_11025"},
        {"name": "bell.sfx", "duration": 1.0}, {"name": "never.sfx", "duration": 1.0}]}))
    r = usage.gate(str(tmp_path / "u.csv"), str(batch))
    assert not r["ok"] and {b["item"] for b in r["blocked"]} == {"bell.sfx", "never.sfx"}
    assert any("0.20 s" in w for w in r["warnings"]) and any("ripetuto" in w for w in r["warnings"])
    r2 = usage.gate(str(tmp_path / "u.csv"), str(batch), allow=("used", "commented"))
    assert [b["item"] for b in r2["blocked"]] == ["never.sfx"]


def test_speaker_audit(tmp_path):
    sc = tmp_path / "script.tsv"
    with open(sc, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["key", "speaker", "text", "shown", "players"], delimiter="\t")
        w.writeheader()
        w.writerow({"key": "aa000001", "speaker": "KEEPER", "text": "Closed.", "shown": "SAILOR", "players": ""})
        w.writerow({"key": "aa000002", "speaker": "ANNA", "text": "Anyone home?", "shown": "", "players": "*"})
        w.writerow({"key": "aa000003", "speaker": "WIFE", "text": "Who is it?", "shown": "", "players": ""})
    cast = tmp_path / "cast.json"
    cast.write_text(json.dumps({"KEEPER": {"gender": "m", "voice_gender": "m"},
                                "ANNA": {"gender": "f", "voice_gender": "f"},
                                "WIFE": {"gender": "f", "voice_gender": "m", "age": "old", "voice_age": "child"}}))
    vd = tmp_path / "voice"
    vd.mkdir()
    (vd / "aa000002_BEN.ogg").write_bytes(b"")
    r = voice.speaker_audit(str(sc), str(cast), str(vd), ["ANNA", "BEN", "CARL"])
    assert r["portrait_differs"][0]["shown"] == "SAILOR"
    assert {m["problem"] for m in r["voice_mismatch"]} == {"genere f con voce m", "età old con voce child"}
    assert r["copies_needed"] == 2 and r["copies_missing"] == ["aa000002_CARL"] and not r["ok"]


def test_guard_deletions_limits():
    sizes = {"a.txt": 10, "big.bin": 2_000_000, "pic.png": 200_000, "assets/x.txt": 5}
    found = guard_deletions.problems(list(sizes), sizes.get, lambda p: p.endswith(".png"), protected=("assets/",))
    assert any("big.bin" in f for f in found) and any("pic.png" in f for f in found)
    assert any("assets/x.txt" in f for f in found) and not any(f.startswith("a.txt") for f in found)
    many = [f"f{i}" for i in range(25)]
    assert guard_deletions.problems(many, lambda p: 1, lambda p: False)[0].startswith("25 file")


def test_roadmap_order_and_emoji():
    md = project.roadmap({"work_packages": [{"id": "a", "label": "Fondali", "status": "done"},
                                            {"id": "b", "label": "Voci", "status": "running", "progress": "38%"}]})
    lines = [l for l in md.splitlines() if l.startswith("| ") and "Voce" not in l]
    assert lines[0].startswith("| Voci | 🟡 | 38%") and lines[1].startswith("| Fondali | ✅")


def test_choice_page(tmp_path):
    from remaster_tools import review
    (tmp_path / "a.png").write_bytes(b"")
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"title": "Prova", "items": [{"id": "porta", "label": "Porta", "variants": [
        {"name": "originale", "file": "a.png"}, {"name": "B", "file": "b.ogg", "caption": "più cupo"}]}]}))
    r = review.choice_page(str(spec), str(tmp_path / "out" / "p.html"))
    page = (tmp_path / "out" / "p.html").read_text(encoding="utf-8")
    assert r["items"] == 1 and 'src="../a.png"' in page and "<audio" in page and 'value="altro"' in page


def test_effect_mask(tmp_path):
    from PIL import Image
    from remaster_tools import gfx
    im = Image.new("P", (4, 2), 0)
    im.putpalette([i for i in range(256) for _ in range(3)])
    im.putpixel((1, 0), 200)
    im.putpixel((2, 1), 12)
    im.save(tmp_path / "bg.png")
    r = gfx.effect_mask(str(tmp_path / "bg.png"), "190-210,12", str(tmp_path / "m.png"), scale=2)
    m = Image.open(tmp_path / "m.png")
    assert m.size == (8, 4) and m.getpixel((2, 0)) == 255 and m.getpixel((0, 0)) == 0 and r["coverage"] == 0.25


def test_install_hooks(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    r = project.install_hooks(str(tmp_path))
    assert (tmp_path / ".githooks" / "guard_deletions.py").exists() and (tmp_path / ".claude" / "settings.json").exists()
    assert subprocess.run(["git", "-C", str(tmp_path), "config", "core.hooksPath"], capture_output=True,
                          text=True).stdout.strip() == ".githooks" and len(r["installed"]) == 4
