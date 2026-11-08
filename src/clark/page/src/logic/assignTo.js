// Row 985: recent names and search of the people register for the Assign-to picker, as plain functions with no DOM. The register is
// the people clark holds (GET /api/people); the project's names are the owners already on its work items. Recents live in the
// browser only (never in the file, Excel or a publish), one short list per project; with the storage refused there are none.
import { recall, remember } from "./remember.js";

export const RECENT_MAX = 5;       // the names kept and shown under Recent
export const SHOWN = 8;            // the most a search draws
const NAME_MAX = 200;              // the longest owner (itemEdit.js)
const QUERY_MAX = 200;
const HIDDEN = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Cn}\p{Zl}\p{Zp}]/u;

const text = (v) => (typeof v === "string" ? v : "");
const squash = (v) => text(v).normalize("NFKC").split(/\s+/).filter(Boolean).join(" ");
const same = (v) => squash(v).toLowerCase();                          // who a name is: case and spacing do not matter
const fold = (v) => squash(v).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();   // what is searched: accents do not matter either

// A name that can be an owner: some text, at most NAME_MAX characters, no hidden character, and not TBC.
function usable(v) {
  const s = squash(v);
  return !!s && s.toLowerCase() !== "tbc" && Array.from(s).length <= NAME_MAX && !HIDDEN.test(text(v).replace(/\s/g, " "));
}

const live = (register) => (Array.isArray(register) ? register : []).filter((p) => p && typeof p === "object" && !p.archived && usable(p.name));
const aliasesOf = (p) => text(p.aliases).split(";").map(squash).filter(Boolean);

// 0 a word of the name starts with it, 1 the name contains it, 2 an alias, email or role does, -1 no match
function rank(fields, q) {
  const name = fold(fields.name);
  if (name.startsWith(q) || name.split(" ").some((w) => w.startsWith(q))) return 0;
  if (name.includes(q)) return 1;
  return fields.more.some((f) => fold(f).includes(q)) ? 2 : -1;
}

/** People that match the typed text, best first, at most `limit`: [{name, id, listed}]. The register's live people (name, alias,
 *  email, role), then this project's names that are not on the register. Blank text finds nothing. */
export function searchPeople(register, projectNames, typed, limit = SHOWN) {
  const raw = text(typed);
  if (raw.length > QUERY_MAX * 4) return [];                          // no name is that long: nothing to find
  const q = fold(raw);
  if (!q || q.length > QUERY_MAX) return [];
  const found = [];
  const taken = new Set();
  live(register).forEach((p, i) => {
    const r = rank({ name: p.name, more: [...aliasesOf(p), text(p.email), text(p.role)] }, q);
    if (r < 0) return;
    found.push({ r, i, hit: { name: squash(p.name), id: text(p.id), listed: true } });
  });
  found.sort((a, b) => a.r - b.r || a.i - b.i);
  const out = found.map((f) => f.hit);
  for (const p of live(register)) { taken.add(same(p.name)); aliasesOf(p).forEach((a) => taken.add(same(a))); }
  for (const hit of out) taken.add(same(hit.name));
  for (const n of Array.isArray(projectNames) ? projectNames : []) {
    if (!usable(n) || taken.has(same(n)) || rank({ name: n, more: [] }, q) < 0) continue;
    taken.add(same(n));
    out.push({ name: squash(n), id: "", listed: false });
  }
  return out.slice(0, Math.max(0, limit));
}

/** The recent list with `name` first, once, at most RECENT_MAX long. A name that can't be an owner (blank, TBC, hidden characters,
 *  over 200 characters, not text) leaves the list as it was. */
export function addRecent(list, name) {
  const old = (Array.isArray(list) ? list : []).filter(usable).map(squash);
  const first = usable(name) ? [squash(name)] : [];
  const seen = new Set();
  return [...first, ...old].filter((n) => !seen.has(same(n)) && seen.add(same(n))).slice(0, RECENT_MAX);
}

/** The recent names to show: only people still on the register (shown by the register's name, an alias read as the person) or
 *  named in this project now; each once, in the order kept, at most RECENT_MAX. */
export function shownRecents(recents, register, projectNames) {
  const people = live(register);
  const here = new Map((Array.isArray(projectNames) ? projectNames : []).filter(usable).map((n) => [same(n), squash(n)]));
  const out = [], seen = new Set();
  for (const n of Array.isArray(recents) ? recents : []) {
    if (!usable(n)) continue;
    const k = same(n);
    const p = people.find((q) => same(q.name) === k || aliasesOf(q).some((a) => same(a) === k));
    if (!p && !here.has(k)) continue;                                 // gone from the register and not on this project: dropped
    const shown = p ? squash(p.name) : here.get(k);
    if (!shown || seen.has(same(shown))) continue;
    seen.add(same(shown));
    out.push(shown);
    if (out.length === RECENT_MAX) break;
  }
  return out;
}

const keyFor = (project) => `assignRecent.${encodeURIComponent(text(project))}`;

/** The names kept in this browser for a project, newest first; [] when none, damaged, or the storage is refused. */
export function loadRecents(project) {
  const v = recall(keyFor(project), []);
  return addRecentAll(v);
}
const addRecentAll = (v) => (Array.isArray(v) ? v.filter(usable).map(squash).slice(0, RECENT_MAX) : []);

/** Keep `name` as the project's newest recent. Returns the list now kept (nothing is kept when the storage is refused). */
export function noteAssigned(project, name) {
  const next = addRecent(loadRecents(project), name);
  remember(keyFor(project), next);
  return next;
}

export const PEOPLE_SHOWN = 5;     // the names the picker draws under People before anyone types

/** What the picker draws before anyone types: {recent, people, more}. `recent` is shownRecents; `people` the first PEOPLE_SHOWN of
 *  the register's live people and this project's other names, alphabetical, not already under Recent; `more` how many are left. */
export function browse(recents, register, projectNames) {
  const recent = shownRecents(recents, register, projectNames);
  const seen = new Set(recent.map(same));
  const all = [];
  for (const p of live(register)) all.push(squash(p.name));
  const onRegister = new Set(live(register).flatMap((p) => [same(p.name), ...aliasesOf(p).map(same)]));
  for (const n of Array.isArray(projectNames) ? projectNames : []) if (usable(n) && !onRegister.has(same(n))) all.push(squash(n));
  const distinct = [];
  for (const n of all) if (!seen.has(same(n))) { seen.add(same(n)); distinct.push(n); }
  distinct.sort((a, b) => a.localeCompare(b, "en-GB"));
  return { recent, people: distinct.slice(0, PEOPLE_SHOWN), more: Math.max(0, distinct.length - PEOPLE_SHOWN) };
}

/** Whether two names are the same person's name as far as the picker is concerned (case and spacing do not matter). */
export const sameName = (a, b) => same(a) === same(b);
