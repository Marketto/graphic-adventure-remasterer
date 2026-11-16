// Save-game sync for a web/WebView launcher with Dropbox (App folder access), no server.
// Copy into the private game repository, fill APP_KEY there (empty here: without a key the UI hides
// the section), and wire the hooks: readSaves()/writeSaves() over the engine's IndexedDB file system,
// zip()/unzip() (any small zip library) and the UI callbacks. Rules: references/conoscenza/motore/22-launcher-e-salvataggi-cloud.md.
const APP_KEY = "";                       // set only in the private repository
const ZIP_PATH = "/saves.zip";            // single zip of every save, inside the app folder
const LS = { verifier: "cs.verifier", refresh: "cs.refresh", base: "cs.base" };
let accessToken = null;                   // in memory only, never logged

const b64url = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
                set: (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} } };

async function authUrl() {                // PKCE S256 without redirect_uri: the user pastes the code
  const v = b64url(crypto.getRandomValues(new Uint8Array(48)));
  store.set(LS.verifier, v);              // kept until the code is used
  const c = b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(v)));
  return `https://www.dropbox.com/oauth2/authorize?client_id=${APP_KEY}&response_type=code` +
         `&code_challenge=${c}&code_challenge_method=S256&token_access_type=offline`;
}

async function token(body) {
  const r = await fetch("https://api.dropboxapi.com/oauth2/token", { method: "POST", body: new URLSearchParams({ client_id: APP_KEY, ...body }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (j.error === "invalid_grant") forget();          // revoked or expired link: forget it
    throw new Error("token: " + (j.error || r.status));
  }
  accessToken = j.access_token;
  if (j.refresh_token) store.set(LS.refresh, j.refresh_token);
  return accessToken;
}
const link = code => token({ grant_type: "authorization_code", code: code.trim(), code_verifier: store.get(LS.verifier) })
  .then(t => { store.set(LS.verifier, null); return t; });
const ensureToken = () => accessToken ? Promise.resolve(accessToken)
  : store.get(LS.refresh) ? token({ grant_type: "refresh_token", refresh_token: store.get(LS.refresh) }) : Promise.reject(new Error("not linked"));
function forget() { accessToken = null; [LS.refresh, LS.base].forEach(k => store.set(k, null)); }
async function unlink() {
  try { await api("https://api.dropboxapi.com/2/auth/token/revoke", null, undefined, true); } catch (e) {}
  forget();
}

async function api(url, arg, body, retried = false) {
  const t = await ensureToken();
  const h = { Authorization: "Bearer " + t };
  if (arg) h["Dropbox-API-Arg"] = JSON.stringify(arg);
  if (body) h["Content-Type"] = "application/octet-stream";
  const r = await fetch(url, { method: "POST", headers: h, body });
  if (r.status === 401) {
    accessToken = null;
    if (!retried) return api(url, arg, body, true);      // one refresh, then give up
    forget();
    throw new Error("unauthorized");
  }
  return r;
}

// One sync. hooks: {readSaves() -> {path: Uint8Array}, writeSaves(files, remove), zip(files), unzip(bytes),
// hash(bytes) -> string, mtime(side, path), gameRunning() -> bool, confirmOverwrite() -> Promise<bool>}
let running = null;
function sync(h, opts = {}) {             // one sync at a time; while the game runs nothing happens
  if (h.gameRunning()) return Promise.resolve({ skipped: "game running" });
  if (!running) running = doSync(h, opts).finally(() => { running = null; });
  return running;
}

async function doSync(h, { interactive = true } = {}) {
  const local = await h.readSaves();
  const lh = Object.fromEntries(await Promise.all(Object.entries(local).map(async ([p, b]) => [p, await h.hash(b)])));
  const base = JSON.parse(store.get(LS.base) || "{}");
  let remote = {}, rh = {}, rev = null;
  const dl = await api("https://content.dropboxapi.com/2/files/download", { path: ZIP_PATH });
  if (dl.ok) {
    const meta = dl.headers.get("Dropbox-API-Result");    // needs the header exposed by CORS
    if (!meta) throw new Error("download: Dropbox-API-Result missing");
    rev = JSON.parse(meta).rev;
    remote = await h.unzip(new Uint8Array(await dl.arrayBuffer()));
    rh = Object.fromEntries(await Promise.all(Object.entries(remote).map(async ([p, b]) => [p, await h.hash(b)])));
  } else if (dl.status !== 409) throw new Error("download " + dl.status);
  const plan = mergePlan(base, lh, rh, h.mtime);
  const merged = {};
  for (const [p, side] of Object.entries(plan.take)) merged[p] = side === "local" ? local[p] : remote[p];
  const fromRemote = Object.entries(plan.take).filter(([, s]) => s === "remote").map(([p]) => p);
  if (h.gameRunning()) return { skipped: "game started during sync" };   // base untouched: retried later
  if (fromRemote.length || plan.remove.some(p => p in local))
    await h.writeSaves(Object.fromEntries(fromRemote.map(p => [p, remote[p]])), plan.remove.filter(p => p in local));
  const mh = Object.fromEntries(Object.keys(merged).map(p => [p, plan.take[p] === "local" ? lh[p] : rh[p]]));
  if (changeHash(mh) !== changeHash(rh)) {
    const mode = rev ? { ".tag": "update", update: rev } : "add";   // conflict instead of silent overwrite
    let up = await api("https://content.dropboxapi.com/2/files/upload", { path: ZIP_PATH, mode, mute: true }, await h.zip(merged));
    if (up.status === 409 && interactive && await h.confirmOverwrite())
      up = await api("https://content.dropboxapi.com/2/files/upload", { path: ZIP_PATH, mode: "overwrite", mute: true }, await h.zip(merged));
    if (!up.ok) throw new Error("upload " + up.status);
    rev = (await up.json()).rev;
  }
  store.set(LS.base, JSON.stringify(mh));   // only after a complete sync
  return { conflicts: plan.conflicts, downloaded: fromRemote.length, removed: plan.remove.length };
}

// Triggers: at open (the Start button waits at most 15 s), every minute, when the page is hidden.
function schedule(h, onError) {
  const run = () => sync(h).catch(onError);
  setInterval(run, 60000);
  document.addEventListener("visibilitychange", () => document.visibilityState === "hidden" && sync(h, { interactive: false }).catch(onError));
  addEventListener("pagehide", () => sync(h, { interactive: false }).catch(onError));   // never ask while closing
  return Promise.race([run(), new Promise(r => setTimeout(r, 15000))]);
}
