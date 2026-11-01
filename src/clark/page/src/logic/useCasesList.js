// The Use cases page's list (the editor's page, one level above the dashboard's summary): every live use case of the project, selected
// for the dashboard or not, with what is linked to it, and the rules for narrowing and ordering the list. Plain JS and no page
// store, so the page and the tests share it. The eye (use_cases.client_visible) is the dashboard's own switch: a use case is
// "on the dashboard" when it is set, and a published file only ever holds the ones that were.
import { isOpen, plural } from "../workItems.js";
import { recall, remember } from "./remember.js";

export const STATUS_WORDS = ["On track", "Flag", "High risk", "Done"];        // the schema's four, in the order the Status filter lists them
const WORST_FIRST = ["High risk", "Flag", "On track", "Done"];                 // Done is finished: it sorts last
export const ON_WORDS = "On the dashboard";
export const OFF_WORDS = "Not on the dashboard";
export const SORTS = [["ref", "Reference"], ["status", "Status"], ["open", "Open work items"]];
const KEY = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;                                // what the address carries as a use case key (router.js)

/** On the dashboard: the eye is on. A row with no such field (a published file's) was selected, or it would not be there. */
export const isOn = (u) => u.client_visible !== 0 && u.client_visible !== false;

/** The live (not archived) use cases of the data, in the order the data gives them. */
export const liveOf = (d) => ((d && d.use_cases) || []).filter((u) => !u.archived);

/** The key a use case has in the address: its reference as written ("1.2") when that is one clean word nobody else has, else its id. */
export function ucKey(d, u) {
  const live = liveOf(d), ref = String(u.ref || "");
  const clean = KEY.test(ref) && !live.some((x) => x !== u && (x.ref === ref || x.id === ref));
  return clean ? ref : u.id;
}

/** The live use case an address key names (an id first, then a reference), or undefined. */
export function ucFor(d, key) {
  const live = liveOf(d);
  return live.find((u) => u.id === key) || live.find((u) => u.ref === key);
}

// How a reference is written where a person reads it, short form then the number: the one place that does, so no other file spells the short form.
export const REF_PREFIX = "UC";
export const refOf = (u) => (u.ref ? REF_PREFIX + " " + u.ref : "");
export const nameOf = (u) => String(u.title || "").split("\n").map((t) => t.trim()).filter(Boolean).join(" · ");
const plainText = (html) => String(html || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();

/** The rows: [{u, id, ref, name, headline, status, on, total, open, ms: [{id, name}], text}]. `all` is workItems.rowsOf(d). */
export function listOf(d, all) {
  const link = {}, ms = {};
  const msById = Object.fromEntries(((d && d.milestones) || []).filter((m) => !m.archived).map((m) => [m.id, m]));
  for (const r of [...(d.actions || []), ...(d.raid || []), ...(d.decisions || [])]) {
    if (r.use_case) link[r.id] = r.use_case;
    if (r.use_case && r.milestone && msById[r.milestone]) (ms[r.use_case] = ms[r.use_case] || new Set()).add(r.milestone);
  }
  const when = (m) => m.baseline_date || m.forecast_date || m.actual_date || "9999";
  return liveOf(d).map((u) => {
    const linked = all.filter((r) => link[r.id] === u.id), open = linked.filter(isOpen);
    const mine = [...(ms[u.id] || [])].map((id) => msById[id]).sort((a, b) => (when(a) < when(b) ? -1 : when(a) > when(b) ? 1 : a.name < b.name ? -1 : 1));
    const row = { u, id: u.id, ref: refOf(u), name: nameOf(u), headline: u.headline || "", status: u.status, on: isOn(u), total: linked.length, open: open.length,
      ms: mine.map((m) => ({ id: m.id, name: m.name })) };
    row.text = [u.ref, row.ref, row.name, row.headline, plainText(u.standing), ...row.ms.map((m) => m.name)].join(" ").toLowerCase();
    return row;
  });
}

// ---- narrowing, ordering and counts ----
export const FIRST = { st: [], on: "all", sort: "ref", q: "" };                  // what a project starts with

/** A saved or typed state made well-formed: anything unknown falls back to the start. */
export function tidy(s) {
  const x = s && typeof s === "object" ? s : {};
  return {
    st: Array.isArray(x.st) ? STATUS_WORDS.filter((w) => x.st.includes(w)) : [],
    on: ["all", "on", "off"].includes(x.on) ? x.on : "all",
    sort: SORTS.some(([k]) => k === x.sort) ? x.sort : "ref",
    q: typeof x.q === "string" ? x.q.slice(0, 200) : "",
  };
}

export const narrowed = (f) => f.st.length > 0 || f.on !== "all" || f.q.trim() !== "";

/** The status filter and search without the On / Not on the dashboard switch: what the switch's counts are counted from. */
const fits = (r, f, skipOn) => (!f.st.length || f.st.includes(r.status)) && (skipOn || f.on === "all" || (f.on === "on") === r.on) && (!f.q.trim() || r.text.includes(f.q.trim().toLowerCase()));

/** Counts for the switch: how many are All, On and Not on the dashboard, with the Status filter and the search applied. */
export function onCounts(rows, f) {
  const base = rows.filter((r) => fits(r, f, true));
  return { all: base.length, on: base.filter((r) => r.on).length, off: base.filter((r) => !r.on).length };
}

// Reference order: its numbers one by one ("1.2" before "1.10"); one with no reference last, in the order the data gives.
const numbers = (r) => String(r.u.ref || "").split(/[^0-9]+/).filter(Boolean).map(Number);
function byRef(a, b) {
  const x = numbers(a), y = numbers(b);
  if (!x.length !== !y.length) return x.length ? -1 : 1;
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] === undefined ? -1 : x[i]) - (y[i] === undefined ? -1 : y[i]);
    if (d) return d;
  }
  return String(a.u.ref || "").localeCompare(String(b.u.ref || ""));
}
const ORDER = {
  ref: byRef,
  status: (a, b) => WORST_FIRST.indexOf(a.status) - WORST_FIRST.indexOf(b.status) || byRef(a, b),
  open: (a, b) => b.open - a.open || byRef(a, b),
};

/** The rows the filters keep, in the chosen order (the sort is stable, so ties keep the data's order). */
export function shownOf(rows, f) {
  return rows.map((r, i) => [r, i]).filter(([r]) => fits(r, f)).sort((a, b) => (ORDER[f.sort] || ORDER.ref)(a[0], b[0]) || a[1] - b[1]).map(([r]) => r);
}

/** "Showing 3 of 7 · 4 on the dashboard": how many show, of how many, and how many of all are on the dashboard. */
export const countWords = (shown, rows) => `Showing ${shown} of ${rows.length} · ${rows.filter((r) => r.on).length} on the dashboard`;

/** The row said in plain words, for its name button: the reference, the name, the status, the work items and the dashboard. */
export const rowSay = (r) => [r.ref || "Use case", r.name, r.status, r.total ? `${r.open} of ${plural(r.total, "work item")} open` : "No work items", r.on ? ON_WORDS : OFF_WORDS].join(", ");

// ---- remembered for each project, in this browser only ----
const STORE = "ucPage";
export const recalled = (code) => tidy((recall(STORE, {}) || {})[code]);
export function keep(code, state) {
  const all = recall(STORE, {});
  remember(STORE, { ...(all && typeof all === "object" ? all : {}), [code]: tidy(state) });
}
