// Row 1535 step 3: the browser's `clark.*` preferences are also kept in the data folder (preferences.json, through /api/preferences), so a new port,
// browser or profile, a restore and a new Mac keep them. The browser stays the fast copy. This file is the first thing main.jsx loads and imports
// nothing, so the kept values are in the browser's store before any other part of the page reads it:
//   1. the server puts the kept values in the page (`clark-prefs`); each one is written into the browser's store (the data folder wins);
//   2. the first time the data folder has never taken the browser's values, they are offered once (`import`); a second run changes nothing;
//   3. every later change to a `clark.` key is sent on (`set` and `remove`), a moment after, and again if it failed.
// Every read and write can fail (a blocked store, no server): then the page draws with what it has and says nothing. A published page's reader keys
// (`clark.reader.`) are not taken. Nothing here logs or shows a value.
const NOT_KEPT = "clark.reader.";
const CHUNK = 900 * 1024;           // characters in one request; the server's limit is 2 MiB
export const kept = (k) => typeof k === "string" && k.startsWith("clark.") && !k.startsWith(NOT_KEPT);

const block = (doc, id) => { try { const el = doc.getElementById(id); return el ? JSON.parse(el.textContent) : null; } catch (e) { return null; } };

/** Write the data folder's values into the store (its own text, as it is). Returns how many were written; a blocked store writes none. */
export function hydrate(storage, values) {
  let n = 0;
  for (const [k, v] of Object.entries(values || {})) {
    if (!kept(k) || typeof v !== "string") continue;
    try { if (storage.getItem(k) !== v) { storage.setItem(k, v); n++; } } catch (e) { return n; }
  }
  return n;
}

/** Every kept key the store holds, as {key: text}; {} when the store is blocked. */
export function held(storage) {
  const out = {};
  try {
    for (let i = 0; i < storage.length; i++) {
      const k = storage.key(i);
      if (kept(k)) { const v = storage.getItem(k); if (typeof v === "string") out[k] = v; }
    }
  } catch (e) { return {}; }
  return out;
}

/** The store's values cut into requests of at most CHUNK characters; a value larger than one request is left in the browser. */
export function chunks(values) {
  const out = []; let cur = {}; let size = 0;
  for (const [k, v] of Object.entries(values)) {
    const n = k.length + v.length + 8;
    if (n > CHUNK) continue;
    if (size + n > CHUNK) { out.push(cur); cur = {}; size = 0; }
    cur[k] = v; size += n;
  }
  if (Object.keys(cur).length) out.push(cur);
  return out;
}

/** What to send when the page opens: the first chunk as the one-time import, the rest as ordinary sets; nothing once the folder has imported. */
export function importBodies(storage, doc) {
  if (!doc || doc.imported === true) return [];
  const parts = chunks(held(storage));
  return parts.map((p, i) => (i === 0 ? { import: p } : { set: p }));
}

/** The sender of later changes: `note(key, text|null)` records one; `flush()` sends what is waiting and keeps it if the send failed. */
export function makeSender(post, setTimer) {
  let set = {}; let remove = new Set(); let busy = false; let timer = null;
  const flush = async () => {
    if (busy || (!Object.keys(set).length && !remove.size)) return;
    busy = true;
    const body = {}; const sentSet = set; const sentRemove = remove;
    if (Object.keys(sentSet).length) body.set = sentSet;
    if (sentRemove.size) body.remove = [...sentRemove];
    set = {}; remove = new Set();
    let ok = false;
    try { ok = await post(body); } catch (e) { ok = false; }
    if (!ok) {         // keep it for the next try, unless a newer change came meanwhile
      for (const [k, v] of Object.entries(sentSet)) if (!(k in set) && !remove.has(k)) set[k] = v;
      for (const k of sentRemove) if (!(k in set)) remove.add(k);
    }
    busy = false;
  };
  const note = (key, value) => {
    if (!kept(key)) return;
    if (value === null) { delete set[key]; remove.add(key); } else { remove.delete(key); set[key] = value; }
    if (timer === null) timer = setTimer(() => { timer = null; flush(); }, 400);
  };
  return { note, flush };
}

const sendWith = (doc, fetchFn) => async (body) => {
  const boot = block(doc, "clark-boot");
  if (!boot || !boot.token) return false;
  const r = await fetchFn("/api/preferences", { method: "POST", keepalive: JSON.stringify(body).length < 60000,
    headers: { "X-Clark-Token": boot.token, "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return !!(r && r.ok);
};

/** Settings › Reset all preferences: the data folder's file is emptied, then every kept key is taken out of the browser's store. Returns true when done. */
export async function resetAll(storage = window.localStorage, doc = document, fetchFn = window.fetch.bind(window)) {
  let ok = false;
  try { ok = await sendWith(doc, fetchFn)({ reset: true }); } catch (e) { ok = false; }
  if (!ok) return false;
  for (const k of Object.keys(held(storage))) { try { rawRemove.call(storage, k); } catch (e) { break; } }
  return true;
}

let rawSet = null; let rawRemove = null;
function install(win) {
  const doc = win.document;
  let storage;
  try { storage = win.localStorage; } catch (e) { return; }
  rawSet = win.Storage.prototype.setItem; rawRemove = win.Storage.prototype.removeItem;
  const prefs = block(doc, "clark-prefs");
  if (!prefs) return;                      // a server that keeps none (or a published page): the browser alone
  try { hydrate(storage, prefs.values); } catch (e) { /* the page draws with what it has */ }
  const sender = makeSender(sendWith(doc, win.fetch.bind(win)), (f, ms) => win.setTimeout(f, ms));
  const offer = async () => {           // the token's data block comes after this script: wait until the whole page is parsed
    for (const body of importBodies(storage, prefs)) { try { await sendWith(doc, win.fetch.bind(win))(body); } catch (e) { /* the next start offers them again */ } }
  };
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", offer); else offer();
  win.Storage.prototype.setItem = function (k, v) { const r = rawSet.apply(this, arguments); if (this === storage) sender.note(String(k), String(v)); return r; };
  win.Storage.prototype.removeItem = function (k) { const r = rawRemove.apply(this, arguments); if (this === storage) sender.note(String(k), null); return r; };
  win.addEventListener("pagehide", () => { sender.flush(); });
}

if (typeof window !== "undefined" && typeof document !== "undefined") { try { install(window); } catch (e) { /* never stops the page */ } }
