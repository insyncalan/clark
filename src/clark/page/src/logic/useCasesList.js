// The Use cases page's list (the editor's page, one level above the dashboard's summary): every live use case of the project, selected
// for the dashboard or not, with what is linked to it, and the rules for narrowing and ordering the list. Plain JS and no page
// store, so the page and the tests share it. The eye (use_cases.client_visible) is the dashboard's own switch: a use case is
// "on the dashboard" when it is set, and a published file only ever holds the ones that were.
import { isOpen, plural } from "../workItems.js";
import { recall, remember } from "./remember.js";
import { commitWord } from "./commitment.js";

export const STATUS_WORDS = ["On track", "Flag", "High risk", "Done"];        // the schema's four, in the order the Status filter lists them
export const RAG = { "On track": "g", Flag: "a", "High risk": "r", Done: "b" };  // the tint of each status word's chip (row 1085: Done is blue, the approved colours)
export const CALM_WORDS = ["On track", "Done"];                                // the two that are not flagged: on track, and finished
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
/** The reference as it is read in the small box: references that were merged ("1.3, 1.4" or "1.3 and 1.4") read "1.3 + 1.4". */
export function refText(ref) {
  return String(ref || "").split(/\s*(?:,|;|\+|\band\b)\s*/i).map((x) => x.trim()).filter(Boolean).join(" + ");
}
/** The boxed reference, item 1149: the short form once, then the number ("UC 1.3 + 1.4"); the one string the dashboard, the page and the published tab draw in the box. Empty when there is no reference. */
export const refBox = (ref) => (refText(ref) ? REF_PREFIX + " " + refText(ref) : "");
/** The open next steps of a use case, as its row says them. */
export const stepsWord = (n) => (n === 1 ? "1 next step" : n ? `${n} next steps` : "No open steps");
export const nameOf = (u) => String(u.title || "").split("\n").map((t) => t.trim()).filter(Boolean).join(" · ");
// The common entities, decoded after the tags are gone (an encoded < is text, not a tag) and the ampersand last (so &amp;lt; stays &lt;).
const NAMED = { lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
const codeChar = (n) => (n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : " ");
const decode = (s) => s.replace(/&(?:#(\d+)|#x([0-9a-f]+)|(lt|gt|quot|apos|nbsp));/gi, (_, dec, hex, name) => (name ? NAMED[name.toLowerCase()] : codeChar(dec ? parseInt(dec, 10) : parseInt(hex, 16)))).replace(/&amp;/gi, "&");
const plainText = (html) => decode(String(html || "").replace(/<[^>]*>/g, " ")).replace(/\s+/g, " ").trim();

/** The rows: [{u, id, ref, name, headline, status, on, total, open, ms: [{id, name}], text}]. `all` is workItems.rowsOf(d). */
export function listOf(d, all) {
  const link = {}, ms = {};
  const msById = Object.fromEntries(((d && d.milestones) || []).filter((m) => !m.archived).map((m) => [m.id, m]));
  for (const r of [...(d.actions || []), ...(d.raid || []), ...(d.decisions || [])]) {
    if (r.use_case) link[r.id] = r.use_case;
    if (r.use_case && r.milestone && msById[r.milestone]) (ms[r.use_case] = ms[r.use_case] || new Set()).add(r.milestone);
  }
  for (const l of (d.uc_milestones || [])) if (l.use_case && msById[l.milestone]) (ms[l.use_case] = ms[l.use_case] || new Set()).add(l.milestone);   // linked straight to the milestone (row 1107), as the use case's own page counts it
  const when = (m) => m.baseline_date || m.forecast_date || m.actual_date || "9999";
  return liveOf(d).map((u) => {
    const linked = all.filter((r) => link[r.id] === u.id), open = linked.filter(isOpen);
    const mine = [...(ms[u.id] || [])].map((id) => msById[id]).sort((a, b) => (when(a) < when(b) ? -1 : when(a) > when(b) ? 1 : a.name < b.name ? -1 : 1));
    const row = { u, id: u.id, ref: refOf(u), name: nameOf(u), headline: u.headline || "", status: u.status, commitment: commitWord(u), on: isOn(u), total: linked.length, open: open.length,
      ms: mine.map((m) => ({ id: m.id, name: m.name })) };
    row.text = [u.ref, row.ref, row.name, row.headline, plainText(u.standing), row.commitment, row.status, ...row.ms.map((m) => m.name)].join(" ").toLowerCase();
    return row;
  });
}

const quoteVal = (v) => (/[\s,":]/.test(v) ? `"${String(v).replace(/"/g, "")}"` : String(v));

// ---- the tabs (row 1085) ----
// Four fixed views over the line, as the Work items saved views are drawn: [id, name, keeps(row)]. At risk is a status of Flag or High risk.
export const COMMITTED = "Committed";                                            // the commitment word the Committed tab asks for (the server's word)
export const TABS = [
  ["all", "All use cases", () => true],
  ["on", ON_WORDS, (r) => r.on],
  ["committed", COMMITTED, (r) => r.commitment === COMMITTED],
  ["risk", "At risk", (r) => r.status === "Flag" || r.status === "High risk"],
];
export const tabKeeps = (id) => (TABS.find(([k]) => k === id) || TABS[0])[2];

// ---- Group by (row 1085) ----
// Status, Commitment, On the dashboard or Nothing (the start): each group a bordered card as the Work items groups are, a group with no row left out.
const uniq = (xs) => [...new Set(xs.filter(Boolean))];
export const GROUPS = [["status", "Status"], ["commitment", "Commitment"], ["on", ON_WORDS], ["nothing", "Nothing"]];
export const groupLabel = (id) => (GROUPS.find(([k]) => k === id) || GROUPS[GROUPS.length - 1])[1];
export const NONE_LABEL = "None";                                                // the group of the rows with no commitment (the Milestones cell's word)
/** The groups of `shown` (already narrowed and ordered): [{key, label, rows}] in the group's own order. `words` is the server's commitment list, in its order. */
export function groupsOf(shown, group, words) {
  const by = (keys, keyOf, label) => keys.map((k) => ({ key: k, label: label(k), rows: shown.filter((r) => keyOf(r) === k) })).filter((g) => g.rows.length);
  if (group === "status") return by(uniq([...STATUS_WORDS, ...shown.map((r) => r.status)]), (r) => r.status, (k) => k);
  if (group === "on") return by(["on", "off"], (r) => (r.on ? "on" : "off"), (k) => (k === "on" ? ON_WORDS : OFF_WORDS));
  if (group === "commitment") return by([...uniq([...(words || []), ...shown.map((r) => r.commitment)]), ""], (r) => r.commitment || "", (k) => k || NONE_LABEL);
  return [{ key: "", label: "", rows: shown }];
}

// ---- narrowing, ordering and counts ----
export const FIRST = { line: "", tab: "all", group: "nothing", sort: "ref" };    // what a project starts with

// A browser's saved state from before the line held {st, on, sort, q}: the Status choice and the search become one line (row 1085), the
// status chip first, then the search's words as plain words (one that would read as a field is quoted, so it stays the plain word it was).
// The switch's On the dashboard is the tab of that name; its Not on the dashboard, which has no tab, is the line's on:no.
const quoteWord = (w) => (/^-?[A-Za-z][\w-]*:/.test(w) || w.includes('"') ? `"${w.replace(/"/g, "")}"` : w);
export function lineFromOld(x) {
  const st = Array.isArray(x.st) ? STATUS_WORDS.filter((w) => x.st.includes(w)) : [];
  const q = typeof x.q === "string" ? x.q.slice(0, 200) : "";
  return [...(st.length ? [`status:${st.map(quoteVal).join(",")}`] : []), ...(x.on === "off" ? ["on:no"] : []), ...q.split(/\s+/).filter(Boolean).map(quoteWord)].join(" ");
}

/** A saved or typed state made well-formed: anything unknown falls back to the start. A state with no `line` is an older one and is read as one. */
export function tidy(s) {
  const x = s && typeof s === "object" ? s : {};
  const old = x.line === undefined;
  return {
    line: typeof x.line === "string" ? x.line.slice(0, 600) : old ? lineFromOld(x) : "",
    tab: TABS.some(([k]) => k === x.tab) ? x.tab : old && x.on === "on" ? "on" : "all",
    group: GROUPS.some(([k]) => k === x.group) ? x.group : "nothing",
    sort: SORTS.some(([k]) => k === x.sort) ? x.sort : "ref",
  };
}

export const narrowed = (f) => f.tab !== "all" || f.line.trim() !== "";

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
/** The rows a tab keeps (and `test`, the filter line's test, when given), in the chosen order; ties keep the data's order. Shared by the editor's list and the published tab. */
export function pickRows(rows, f, test) {
  const keeps = tabKeeps(f.tab);
  return rows.map((r, i) => [r, i]).filter(([r]) => (!test || test(r)) && keeps(r)).sort((a, b) => (ORDER[f.sort] || ORDER.ref)(a[0], b[0]) || a[1] - b[1]).map(([r]) => r);
}
export const ORDER = {
  ref: byRef,
  status: (a, b) => WORST_FIRST.indexOf(a.status) - WORST_FIRST.indexOf(b.status) || byRef(a, b),
  open: (a, b) => b.open - a.open || byRef(a, b),
};


/** "Showing 3 of 7 · 4 on the dashboard": how many show, of how many, and how many of all are on the dashboard. */
export const countWords = (shown, rows) => `Showing ${shown} of ${rows.length} · ${rows.filter((r) => r.on).length} on the dashboard`;

/** The row said in plain words, for its name button: the reference, the name, the status, the work items and the dashboard. */
export const rowSay = (r) => [r.ref || "Use case", r.name, r.status, ...(r.commitment ? [r.commitment] : []), r.total ? `${r.open} of ${plural(r.total, "work item")} open` : "No work items", r.on ? ON_WORDS : OFF_WORDS].join(", ");

// ---- remembered for each project, in this browser only ----
const STORE = "ucPage";
export const recalled = (code) => tidy((recall(STORE, {}) || {})[code]);
export function keep(code, state) {
  const all = recall(STORE, {});
  remember(STORE, { ...(all && typeof all === "object" ? all : {}), [code]: tidy(state) });
}
