// The published file's extra Work items parts (#69; BRD FR-90a): search, and the client's remembered choices, as plain functions with
// no clock and no network. The filters themselves are the editor's (filters.js, switched to the published rules with setPublished),
// and Group by is the editor's too (logic/board.js). Everything here works on the rows the file holds, so an option, a count or a
// remembered choice is only ever built from rows the client may see. It mirrors src/clark/client_filters.py (the reference model).
import { fieldList, dueBuckets, valueOf, initial, setFilter, MODES, TYPES } from "./filters.js";
import { GROUPS } from "./logic/board.js";

export const STORAGE_PREFIX = "clark.work.";           // the published page's own key: the editor's is "clark.work.v1" and is never read here
export const STORAGE_VERSION = 1;
export const DEFAULT_GROUP = "workstream";

/** What the search reads, by id: the id, the words, the owner, the latest update, the client message and the use case, case-folded. */
export function searchIndex(data) {
  const map = {};
  const add = (r, words, who) => { map[r.id] = [r.id, words, who, r.latest_update, r.client_message, r.use_case].filter(Boolean).join(" ").toLowerCase(); };
  for (const r of (data && data.actions) || []) add(r, r.description, r.owner);
  for (const r of (data && data.raid) || []) add(r, r.description, r.owner);
  for (const r of (data && data.decisions) || []) add(r, r.decision, r.made_by);
  return map;
}

/** The rows whose text holds every word typed (case does not matter); no words keeps every row. */
export function searchRows(rows, index, q) {
  const words = String(q == null ? "" : q).toLowerCase().split(/\s+/).filter(Boolean);
  return words.length ? rows.filter((r) => words.every((w) => (index[r.id] || "").includes(w))) : rows;
}

const isStr = (x) => typeof x === "string";
const isObj = (x) => !!x && typeof x === "object" && !Array.isArray(x);

/** A stored choice made safe: only known keys and values, and only values some row in the file has now (so a stale choice can never
 *  empty the list with no chip to clear). Never throws, whatever it is given. Gives {mode, type, filters, not, group}. */
export function normalise(st, rows, today) {
  const out = { ...initial(), group: DEFAULT_GROUP };
  if (!isObj(st)) return out;
  if (isStr(st.type) && TYPES.some((t) => t[0] === st.type)) out.type = st.type;
  if (isStr(st.mode) && MODES.some((m) => m[0] === st.mode)) out.mode = st.mode;
  if (isStr(st.group) && GROUPS.some((g) => g.id === st.group)) out.group = st.group;
  const filters = isObj(st.filters) ? st.filters : {}, not = isObj(st.not) ? st.not : {};
  let s = { mode: out.mode, type: out.type, filters: {}, not: {} };
  for (const f of fieldList()) {
    const vals = Array.isArray(filters[f]) ? filters[f] : [];
    const has = new Set(f === "due" ? dueBuckets().map((d) => d[0]) : rows.map((r) => valueOf(r, f, today)));
    const keep = vals.filter((v) => isStr(v) && has.has(v));
    if (keep.length) s = setFilter(s, f, keep, not[f] === true);
  }
  return { ...s, group: out.group };
}

export function storageKey(code) { return STORAGE_PREFIX + code; }

/** The text to keep: Open / Closed / All, type, filters and Group by. The search words are not kept. */
export function remember(st, group) {
  return JSON.stringify({ v: STORAGE_VERSION, type: st.type, mode: st.mode, filters: st.filters, not: st.not, group });
}

/** The choices from kept text, made safe by normalise; anything unreadable or from another version gives null. */
export function recall(text, rows, today) {
  let p;
  try { p = JSON.parse(text); } catch (e) { return null; }
  return isObj(p) && p.v === STORAGE_VERSION ? normalise(p, rows, today) : null;
}

// localStorage can be blocked (a private window, a policy) or full: both are silent, and the page works without it.
export function save(code, text) { try { window.localStorage.setItem(storageKey(code), text); } catch (e) { /* not kept */ } }
export function load(code) { try { return window.localStorage.getItem(storageKey(code)); } catch (e) { return null; } }
