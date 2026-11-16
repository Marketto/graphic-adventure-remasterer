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


SYNC = os.path.join(os.path.dirname(MERGE), "cloud-sync.js")


@pytest.mark.skipif(not shutil.which("node"), reason="node non installato")
def test_sync_never_touches_base_while_playing():
    src = open(MERGE).read() + "\n" + open(SYNC).read()
    js = src + """
const mem = {"cs.refresh": "r", "cs.base": JSON.stringify({"s1": "old"})};
globalThis.localStorage = {getItem: k => mem[k] ?? null, setItem: (k, v) => { mem[k] = v; }, removeItem: k => { delete mem[k]; }};
let calls = 0, playing = false;
globalThis.fetch = async (url) => {
  calls++;
  if (url.includes("oauth2/token")) return {ok: true, json: async () => ({access_token: "t"})};
  if (url.includes("download")) { playing = true;              // the game starts while downloading
    return {ok: true, status: 200, headers: {get: () => JSON.stringify({rev: "1"})}, arrayBuffer: async () => new ArrayBuffer(0)}; }
  if (url.includes("revoke")) return {ok: false, status: 401};
  throw new Error("unexpected " + url);
};
const h = {readSaves: async () => ({"s1": new Uint8Array([1])}), writeSaves: async () => { throw new Error("written"); },
  zip: async () => new Uint8Array(), unzip: async () => ({"s1": new Uint8Array([2])}), hash: async b => String(b[0]),
  mtime: () => 0, gameRunning: () => playing, confirmOverwrite: async () => false};
(async () => {
  const r1 = await sync(h);                                    // starts, game begins mid-way: nothing saved
  const r2 = await sync(h);                                    // game running: not even started
  const base = mem["cs.base"], before = calls;
  await unlink();                                              // 401 on revoke: no endless retry
  console.log(JSON.stringify({r1, r2, base, revokeCalls: calls - before, linked: "cs.refresh" in mem}));
})();"""
    res = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    assert res["r1"]["skipped"] and res["r2"]["skipped"] == "game running"
    assert res["base"] == json.dumps({"s1": "old"}, separators=(",", ":"))
    assert res["revokeCalls"] <= 2 and not res["linked"]
