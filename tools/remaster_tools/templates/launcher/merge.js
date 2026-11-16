// Three-way merge of the save files (pure, no browser API: tested with node).
// base, local, remote: {path: hash}. base = hashes at the last successful sync ({} the first time).
// Returns {take: {path: "local"|"remote"}, remove: [paths], conflicts: [paths decided by mtime]}.
// mtime(side, path) -> number, used only when both sides changed (or there is no base).
function mergePlan(base, local, remote, mtime) {
  const take = {}, remove = [], conflicts = [];
  const paths = new Set([...Object.keys(base), ...Object.keys(local), ...Object.keys(remote)]);
  for (const p of paths) {
    const b = base[p], l = local[p], r = remote[p];
    if (l === r) { if (l !== undefined) take[p] = "local"; continue; }
    const lChanged = l !== b, rChanged = r !== b;
    if (lChanged && !rChanged) { if (l === undefined) remove.push(p); else take[p] = "local"; continue; }
    if (rChanged && !lChanged) { if (r === undefined) remove.push(p); else take[p] = "remote"; continue; }
    // both changed, or no base: same name -> the most recent wins (never a duplicate in a free slot)
    conflicts.push(p);
    if (l === undefined) { take[p] = "remote"; continue; }
    if (r === undefined) { take[p] = "local"; continue; }
    take[p] = (mtime("remote", p) > mtime("local", p)) ? "remote" : "local";
  }
  return { take, remove, conflicts };
}

// Files that the engine rewrites at every start must not count as a change.
function changeHash(files, ignore = [/(^|\/)[^/]*\.ini$/]) {
  const keys = Object.keys(files).filter(p => !ignore.some(re => re.test(p))).sort();
  return keys.map(k => k + ":" + files[k]).join("|");
}

if (typeof module !== "undefined") module.exports = { mergePlan, changeHash };
