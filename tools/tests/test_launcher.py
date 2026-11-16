"""Three-way merge of the launcher save sync (node), invented file names."""
import json
import os
import shutil
import subprocess

import pytest

MERGE = os.path.join(os.path.dirname(__file__), "..", "remaster_tools", "templates", "launcher", "merge.js")


@pytest.mark.skipif(not shutil.which("node"), reason="node non installato")
def test_merge_plan():
    js = f"""const {{mergePlan, changeHash}} = require({json.dumps(os.path.abspath(MERGE))});
const base = {{"s1": "a", "s2": "b", "s3": "c", "s4": "d"}};
const local = {{"s1": "a2", "s2": "b", "s4": "d2", "s5": "e", "x.ini": "1"}};
const remote = {{"s1": "a", "s2": "b2", "s3": "c", "s4": "d3", "s6": "f", "x.ini": "2"}};
const t = {{local: 1, remote: 2}};
const r = mergePlan(base, local, remote, (side) => t[side]);
console.log(JSON.stringify({{r, h: changeHash({{"a.sav": 1, "cfg.ini": 2}}) === changeHash({{"a.sav": 1}})}}));"""
    res = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    r = res["r"]
    assert r["take"]["s1"] == "local" and r["take"]["s2"] == "remote"   # changed on one side only
    assert r["remove"] == ["s3"]                                         # deleted locally, untouched remotely
    assert r["take"]["s4"] == "remote" and "s4" in r["conflicts"]       # both changed: most recent wins
    assert r["take"]["s5"] == "local" and r["take"]["s6"] == "remote"
    assert res["h"]                                                      # config rewritten at start is ignored
