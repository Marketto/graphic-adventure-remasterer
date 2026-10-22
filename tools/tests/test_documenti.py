"""Skills, agents and docs must cite only commands, options and files that really exist, so
that the instructions and the tools do not drift apart."""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import rstool  # noqa: E402

DOCS = (glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")) + glob.glob(os.path.join(ROOT, "agents", "*.md"))
        + glob.glob(os.path.join(ROOT, "commands", "*.md"))
        + [p for p in glob.glob(os.path.join(ROOT, "references", "**", "*.md"), recursive=True)
           if "templates" not in p]
        + [os.path.join(ROOT, f) for f in ("README.md", "CLAUDE.md", "engine/scummvm-remaster-layer/INTEGRAZIONE.md")])
# paths of the PRIVATE game repository that the notes mention as examples
PRIVATE = ("engine/patches", "engine/SCUMMVM_COMMIT", "tools/test/")


def parser_tree():
    captured = {}
    orig = argparse.ArgumentParser.parse_args

    def grab(self, *a, **k):
        captured["p"] = self
        raise SystemExit
    argparse.ArgumentParser.parse_args = grab
    try:
        rstool.main([])
    except SystemExit:
        pass
    finally:
        argparse.ArgumentParser.parse_args = orig
    top = next(a for a in captured["p"]._actions if isinstance(a, argparse._SubParsersAction))
    tree = {}
    for g, gp in top.choices.items():
        subs = [a for a in gp._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            tree[g] = None  # positional action (project): not checked
            continue
        tree[g] = {c: {o for a in cp._actions for o in a.option_strings} for c, cp in subs[0].choices.items()}
    return tree


def test_cited_rstool_commands_and_options_exist():
    tree = parser_tree()
    bad = []
    for f in DOCS:
        text = open(f, encoding="utf-8").read()
        for m in re.finditer(r"rstool\.py(?:\s+--workdir\s+\S+)?\s+([a-z][a-z0-9-]*)\s+([a-z][a-z0-9-]*)([^`\n]*)", text):
            g, c, rest = m.groups()
            rel = os.path.relpath(f, ROOT)
            if g not in tree:
                bad.append(f"{rel}: gruppo inesistente «{g}»")
                continue
            if tree[g] is None:
                continue
            if c not in tree[g]:
                bad.append(f"{rel}: comando inesistente «{g} {c}»")
                continue
            for o in re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", rest):
                if o not in tree[g][c] and o != "--help":
                    bad.append(f"{rel}: opzione inesistente «{g} {c} {o}»")
    assert not bad, "\n".join(sorted(set(bad)))


def test_cited_suite_files_exist():
    bad = []
    pat = re.compile(r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)|`((?:references|tools|skills|agents|engine|ci|app|commands)/[\w./-]+)`)")
    for f in DOCS:
        for m in pat.finditer(open(f, encoding="utf-8").read()):
            p = (m.group(1) or m.group(2)).rstrip(".")
            if any(p.startswith(x) for x in PRIVATE):
                continue
            if not os.path.exists(os.path.join(ROOT, p)):
                bad.append(f"{os.path.relpath(f, ROOT)}: {p}")
    assert not bad, "\n".join(sorted(set(bad)))


def test_every_skill_has_frontmatter_and_is_listed():
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    for f in glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")):
        head = open(f, encoding="utf-8").read().split("---")
        name = os.path.basename(os.path.dirname(f))
        assert f"name: {name}" in head[1] and "description:" in head[1], f
        assert len(re.search(r"description: (.*)", head[1]).group(1)) <= 1024, f
    n = len(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))) - 1
    assert f"orchestratore + {n} skill" in readme


def test_example_recipe_steps_parse():
    """Every rstool step of the example recipe is a valid command line."""
    import json
    with open(os.path.join(ROOT, "references", "recipe.example.json"), encoding="utf-8") as f:
        recipe = json.load(f)
    tree = parser_tree()
    for step in recipe["steps"]:
        if "rstool" in step:
            g, c = step["rstool"][:2]
            assert g in tree and c in tree[g], step["name"]
            for o in [x for x in step["rstool"] if x.startswith("--")]:
                assert o in tree[g][c], (step["name"], o)
