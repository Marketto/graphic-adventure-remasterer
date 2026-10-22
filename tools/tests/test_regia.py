"""Per-line direction (voice direct) and per-character model of the generator, invented data."""
import csv
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from remaster_tools import regia, voice  # noqa: E402

ROWS = [
    ("s1", "ugo", "Buongiorno, signora Pina.", "mercato", "balloon", "", ""),
    ("s2", "pina", "Ma certo, come no.", "mercato", "balloon", "", ""),
    ("s3", "ugo", "Davvero non ha più mele?", "mercato", "balloon", "", ""),
    ("s4", "pina", "Le ho finite tutte!", "mercato", "balloon", "", ""),
    ("s5", "bruno", "Fermi tutti!", "mercato", "balloon", "", ""),
    ("s6", "ugo", "Che giornata...", "molo", "balloon", "[tired]", ""),
]


def _script(tmp_path, extra_col=None):
    p = tmp_path / "copione.tsv"
    cols = ["key", "speaker", "text", "context", "kind", "tag", "recita"] + ([extra_col[0]] if extra_col else [])
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(cols)
        for i, r in enumerate(ROWS):
            w.writerow(list(r) + ([extra_col[1][i]] if extra_col else []))
    return p


def _read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return {r["key"]: r for r in csv.DictReader(f, delimiter="\t")}


def test_direct_context_and_tags(tmp_path):
    cast = tmp_path / "cast.json"
    cast.write_text(json.dumps({"ugo": {"voice_id": "a"}, "pina": {"voice_id": "b"},
                                "bruno": {"voice_id": "c", "register": "deep"}}))
    script = _script(tmp_path, ("limit_s", ["", "", "", "", "", "0.5"]))
    st = regia.direct(str(script), str(tmp_path / "regia.tsv"), context=1, lang="it", cast_path=str(cast))
    d = _read(tmp_path / "regia.tsv")
    # context: one line before/after in the same scene, with who speaks; scenes never mix
    assert d["s3"]["before"] == "pina: Ma certo, come no."
    assert d["s3"]["after"] == "pina: Le ho finite tutte!"
    assert d["s3"]["listener"] == "pina"
    assert d["s5"]["after"] == "" and d["s6"]["before"] == ""
    # heuristics: keyword before punctuation, question, exclamation
    assert d["s2"]["tag"] == "[sarcastic]"
    assert d["s3"]["tag"] == "[curious]"
    assert d["s4"]["tag"] == "[excited]"
    assert d["s1"]["tag"] == ""
    # deep voice: no energetic tag, the reason says why
    assert d["s5"]["tag"] == "" and "voce grave" in d["s5"]["why"]
    # a tag already written by the director is kept; duration over the on-screen limit is flagged
    assert d["s6"]["tag"] == "[tired]" and d["s6"]["over_limit"] == "sì"
    assert st["kept"] == 1 and st["over_limit"] == 1 and st["lines"] == 6


def test_rules_file_per_language(tmp_path):
    rules = tmp_path / "regole.json"
    rules.write_text(json.dumps({"it": {"keywords": {"[warm]": ["buongiorno"]}}}))
    regia.direct(str(_script(tmp_path)), str(tmp_path / "r.tsv"), lang="it", rules_path=str(rules))
    assert _read(tmp_path / "r.tsv")["s1"]["tag"] == "[warm]"


def test_generate_reads_direction_and_models(tmp_path):
    script = _script(tmp_path)
    regia.direct(str(script), str(tmp_path / "regia.tsv"))
    cast = tmp_path / "cast.json"
    cast.write_text(json.dumps({k: {"voice_id": k} for k in ("ugo", "pina", "bruno")}))
    pv = {"model_main": "eleven_v4", "model_secondary": "eleven_flash_v2_5",
          "cast": {"bruno": {"secondary": True}}}
    r = voice.generate(str(script), str(cast), str(tmp_path / "out"), "it", dry_run=True,
                       direction=str(tmp_path / "regia.tsv"), project_voice=pv)
    assert r["models"] == {"bruno": "eleven_flash_v2_5", "pina": "eleven_v4", "ugo": "eleven_v4"}
    # tags count only for the models that act them: bruno's line is sent without tag
    plain = voice.generate(str(script), str(cast), str(tmp_path / "out"), "it", dry_run=True, project_voice=pv)
    assert r["characters"] > plain["characters"]
    # a main character can never get a "flat" model
    with pytest.raises(ValueError):
        voice.model_for("ugo", {}, {"model_main": "eleven_multilingual_v2"})
    assert voice.model_for("ugo", {"model": "eleven_v3"}, {}) == "eleven_v3"


def test_generate_refuses_more_than_one_tag(tmp_path):
    script = _script(tmp_path)
    regia.direct(str(script), str(tmp_path / "regia.tsv"))
    rows = list(_read(tmp_path / "regia.tsv").values())
    rows[0]["tag"] = "[warm] [cheerful]"
    with open(tmp_path / "regia.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=regia.COLUMNS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    cast = tmp_path / "cast.json"
    cast.write_text(json.dumps({k: {"voice_id": k} for k in ("ugo", "pina", "bruno")}))
    with pytest.raises(ValueError, match="un tag"):
        voice.generate(str(script), str(cast), str(tmp_path / "out"), "it", dry_run=True,
                       direction=str(tmp_path / "regia.tsv"))
