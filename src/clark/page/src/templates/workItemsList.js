// Work items list (#96), store type "workitems": the pure rules (no DOM, no Preact). The section holds a saved filter, never rows;
// the rows are chosen again each time from the project's records. The same rules as src/clark/section_kinds/workitems.py
// (tests/test_tpl_workitems.py runs the two over the same rows):
// - the page clark serves (View and Edit's preview) reads the saved filter from the section's body and lists only rows that
//   logic/publishable.js would publish, so View shows exactly what the client sees (FR-11);
// - a published file holds no filter: its section carries `items` (the ids publish chose, in order, from rows it already kept),
//   `columns` and `caption`, and the rows are drawn from the file's own data.
import { dayNumber, rowsOf, colourOf } from "../workItems.js";
import { rulesFor, publishable } from "../logic/publishable.js";

export const KINDS = ["action", "risk", "issue", "assumption", "dependency", "decision"];
export const MODES = ["open", "closed", "all", "current"];
export const STATUSES = ["Open", "Delayed", "Pending", "Closed", "Cancelled", "Made", "Withdrawn"];
export const DUE = ["overdue", "soon", "none", "later"];
export const NONE = "(none)";
export const PRIORITIES = ["Urgent", "High", "Medium", "Low"];
export const SORTS = ["due", "priority", "id", "type", "owner"];
export const CARDS_SORTS = ["due", "priority", "id"];      // what the Cards Configure box offers, unchanged
export const DESIGN_SORTS = ["due", "priority", "type", "owner"];
// The options of the Configure box's Sort by: the layer's own list, and the saved sort too when that list lacks it, so the box never shows a sort the list does not have.
export const sortChoices = (classic, saved) => { const own = classic ? DESIGN_SORTS : CARDS_SORTS; return own.includes(saved) ? own : [...own, saved]; };      // row 1339: the approved Configure box offers these four, in this order; a saved sort by ID is kept (SORTS) and still read
export const COLUMNS = ["type", "id", "owner", "due", "status", "priority", "workstream", "milestone"];
export const DEFAULT_COLUMNS = ["id", "owner", "due", "priority"];      // row 1199: Status, Workstream and Milestone start off in a new list; a saved list keeps its own columns
export const SAVED_FALLBACK_COLUMNS = ["type", "id", "owner", "due", "priority"];      // row 1268: what a saved list or file that names no column has always shown; only a NEW list starts with DEFAULT_COLUMNS
export const MAX_ROWS = 50;
export const DEFAULT_MAX = 10;
export const RECENT = 14;      // row 1268: "current" lists a decision made in the last 14 days, as the built-in Decisions section does (logic/sectionRows.js)
export const MAX_CAPTION = 200;
const CLOSED = ["Closed", "Cancelled", "Made", "Withdrawn"];
const FILTERS = ["kinds", "status", "due", "owner", "workstream", "use_case", "priority"];
export const LEFT_OUT = [...FILTERS, "milestone"];      // what a "not" may name
export const PRESENT = ["type", "status", "owner", "priority", "due", "workstream", "usecase", "milestone"];      // what has: and no: may name
const WORK = ["actions", "raid", "decisions"];

// The words a person reads for each choice.
export const WORDS = {
  kinds: { action: "Actions", risk: "Risks", issue: "Issues", assumption: "Assumptions", dependency: "Dependencies", decision: "Decisions" },
  mode: { open: "Open", closed: "Closed", all: "Open and closed", current: "Open, and decisions made in the last 14 days" },
  due: { overdue: "Overdue", soon: "Due in 7 days", none: "No date", later: "Later" },
  sort: { due: "Due date", priority: "Priority", id: "ID", type: "Type", owner: "Owner" },
  columns: { type: "Type", id: "ID", owner: "Owner", due: "Due", status: "Status", workstream: "Workstream", priority: "Priority", milestone: "Milestone" },
  none: { owner: "No owner", workstream: "No workstream", use_case: "No use case", priority: "No priority" },
};

// The filter a new list starts from: open work items of every kind, soonest due first, ten at most, the default columns.
const leftOut = () => Object.fromEntries(LEFT_OUT.map((f) => [f, []]));
export function defaults() {
  return { v: 1, kinds: [], mode: "open", status: [], due: [], owner: [], workstream: [], use_case: [], priority: [], sort: "due",
    max: DEFAULT_MAX, columns: DEFAULT_COLUMNS.slice(), caption: "", milestone: [], not: leftOut(), has: [], no: [], text: [] };
}

// Item 1195 (the approved design, v1.1). Saved views: each is the filter a tab starts from; "all" is the filter a new list starts from.
export const VIEWS = [
  { id: "all", name: "All work items", patch: {} },
  { id: "actions", name: "Actions", patch: { kinds: ["action"] } },
  { id: "risks-issues", name: "Risks and issues", patch: { kinds: ["risk", "issue"] } },
  { id: "decisions", name: "Decisions", patch: { kinds: ["decision"], mode: "current" } },      // row 1268: Pending, and Made in the last 14 days
  { id: "overdue", name: "Overdue", patch: { due: ["overdue"] } },
];

// A fresh filter for a view (an unknown id gives the default filter), so a caller can change it without touching the view.
export function viewFilter(id) {
  const v = VIEWS.find((x) => x.id === id);
  const out = defaults();
  if (v) for (const k of Object.keys(v.patch)) out[k] = v.patch[k].slice();
  return out;
}

// The priority cell of a row: the priority word with the colour class of the pills (the Rating chip's colour). A decision's priority
// is the one its peek sets (row 1195, peek_priority on a drawn row, priority on a rule row); a decision with none says nothing.
export function priorityCell(row) {
  const p = row && row.kind === "decision" ? (row.peek_priority || row.priority) : row && row.priority;
  if (row && row.kind === "decision" && !p) return { text: "", class: "n" };
  const c = colourOf(p);
  return { text: p || "Not rated", class: c.class };
}

// How many rows to draw and which link sits under the table: "Show all items" when the list is longer than Most rows, then "Show only N".
export function windowOf(total, max, showAll) {
  if (total <= max) return { count: total, link: "" };
  return showAll ? { count: total, link: `Show only ${max}` } : { count: max, link: "Show all items" };
}

// Row 1268 (mock-up work-items-mockup.html, rows()): the foot under the scrolling rows. Edit says how many of the rows are in view and that the
// rest scroll; View and Edit both carry the link that opens the Work items page on the same filter.
export const footWords = (total, max, all = false, classic = false) => (classic && (all || total <= max) ? `Showing all of ${total}` : `Showing ${Math.min(total, max)} of ${total}${total > max ? ", scroll for the rest" : ""}`);      // row 1195 (Classic): ruling NEW-WORDS 04:2x, WO-M8328: Showing all of N when nothing is cut and after Show all items
export const reviewWords = (total) => `Review all ${total} items`;

// The Work items page's filter state (filters.js shape) for a list's saved filter, so "Review all N items" opens the page on the same rows.
// Open, closed or all; the type when the kinds are one of the page's (Actions, Risks and issues, Decisions); the field choices. The
// "not", "has", "no" and free-word parts of a list have no place in that state and are left out (the page then shows a few more rows).
export function pageState(filter, nameOf = (f, v) => v) {
  const type = !filter.kinds.length ? "all" : filter.kinds.every((k) => k === "action") ? "action" : filter.kinds.every((k) => k === "decision") ? "decision"
    : filter.kinds.every((k) => k === "risk" || k === "issue") ? "risk" : "all";
  const filters = {};
  for (const f of ["workstream", "status", "due", "owner", "priority", "use_case", "milestone"]) {
    const list = f === "use_case" ? filter[f].map((v) => nameOf(f, v)) : filter[f];
    if (list.length) filters[f] = list.slice();
  }
  return { mode: filter.mode, type, filters, not: {} };
}

// The columns of the approved design, in its order; Status, Workstream and Milestone are off by default.
export const DESIGN_COLUMNS = ["status", "owner", "due", "priority", "workstream", "milestone", "id"];
export const DESIGN_DEFAULT_COLUMNS = ["owner", "due", "priority", "id"];
export function columnsFor(chosen) {
  const got = DESIGN_COLUMNS.filter((c) => Array.isArray(chosen) && chosen.includes(c));
  return got.length ? got : DESIGN_DEFAULT_COLUMNS.slice();
}

const isList = (v) => Array.isArray(v) && v.every((x) => typeof x === "string");

// The saved filter of a section the page clark serves, read from its body (the store checked it); null when there is none yet or
// it can't be read. Every key is filled in, so the rules never meet a missing one.
export function filterOf(section) {
  const body = section && section.body;
  if (typeof body !== "string" || !body) return null;
  let v;
  try { v = JSON.parse(body); } catch (e) { return null; }
  if (!v || typeof v !== "object" || Array.isArray(v)) return null;
  const out = defaults();
  for (const f of [...FILTERS, "columns", "milestone", "text"]) if (isList(v[f])) out[f] = v[f].slice();
  if (!isList(v.columns)) out.columns = SAVED_FALLBACK_COLUMNS.slice();      // row 1268: a saved body with no columns key keeps what it always showed; only a NEW list starts without Type
  if (v.not && typeof v.not === "object" && !Array.isArray(v.not)) for (const f of LEFT_OUT) if (isList(v.not[f])) out.not[f] = v.not[f].slice();
  for (const f of ["has", "no"]) if (Array.isArray(v[f])) out[f] = v[f].filter((g) => isList(g) && g.length).map((g) => g.slice());
  if (MODES.includes(v.mode)) out.mode = v.mode;
  if (SORTS.includes(v.sort)) out.sort = v.sort;
  if (Number.isInteger(v.max) && v.max >= 1 && v.max <= MAX_ROWS) out.max = v.max;
  if (typeof v.caption === "string") out.caption = v.caption;
  return out;
}

// The body to save for a filter: the store keeps it as canonical JSON, so key order here does not matter.
export function bodyOf(filter) { return JSON.stringify(filter); }

// One flat list for the rules, from the rows of a project's data: as section_kinds/workitems.py rows_of.
export function ruleRows(data) {
  const out = [];
  const ms = Object.fromEntries(((data && data.milestones) || []).map((m) => [m.id, tidy(m.name)]));
  for (const r of (data && data.actions) || []) out.push({ id: r.id, kind: "action", title: r.description, milestone: ms[r.milestone] || "", status: r.status, owner: r.owner, workstream: r.workstream, use_case: r.use_case, priority: r.priority, due: r.due_date });
  for (const r of (data && data.raid) || []) out.push({ id: r.id, kind: String(r.type == null ? "" : r.type).toLowerCase(), title: r.description, milestone: ms[r.milestone] || "", status: r.status, owner: r.owner, workstream: r.workstream, use_case: r.use_case, priority: r.priority, due: r.due_date });
  for (const r of (data && data.decisions) || []) out.push({ id: r.id, kind: "decision", title: r.decision, milestone: "", status: r.status, owner: r.made_by, workstream: null, use_case: r.use_case, priority: null, due: r.status === "Pending" ? r.needed_by : r.date });
  return out;
}

const low = (s) => String(s == null ? "" : s).toLowerCase();
const isOpen = (r) => !CLOSED.includes(r.status);
// row 1268: a decision Made in the last 14 days (today counts, a date in the future does not), as logic/sectionRows.js listed().
function madeLately(r, today) {
  const a = dayNumber(r.due), t = dayNumber(today);
  return r.kind === "decision" && r.status === "Made" && a !== null && t !== null && t - a >= 0 && t - a <= RECENT;
}
const modeFits = (mode, r, today) => mode === "all" || (mode === "current" ? isOpen(r) || madeLately(r, today) : (mode === "open") === isOpen(r));
const tidy = (v) => (typeof v === "string" ? v.split(/\s+/).filter(Boolean).join(" ") : "");

function bucket(r, today) {
  const a = dayNumber(r.due), t = dayNumber(today);
  if (a === null || t === null) return "none";
  if (!isOpen(r) || (a < t && r.status === "Completed")) return "";     // closed, or finished work: never Overdue
  return a < t ? "overdue" : a - t <= 7 ? "soon" : "later";
}

function member(r, field, chosen, today) {
  if (!chosen.length) return true;
  if (field === "kinds") return chosen.includes(r.kind);
  if (field === "status") return chosen.includes(r.status);
  if (field === "due") return chosen.includes(bucket(r, today));
  if (field === "milestone") return chosen.some((c) => low(c) === low(tidy(r.milestone) || NONE));
  return chosen.includes(tidy(r[field]) || NONE);
}

// Nothing in the field, as the page's no: reads it (a type and a status are never empty).
function emptyIn(r, field, today) {
  if (field === "due") return dayNumber(r.due) === null || dayNumber(today) === null;
  const key = field === "usecase" ? "use_case" : field;
  if (key === "type" || key === "status") return false;
  return !tidy(r[key]);
}

// The parts of the filter beyond the choices: milestone, not, has, no and the free words (section_kinds/workitems.py _allowed).
function allowed(r, f, today) {
  if (!member(r, "milestone", f.milestone, today)) return false;
  if (LEFT_OUT.some((k) => f.not[k].length && member(r, k, f.not[k], today))) return false;
  if (f.has.some((g) => g.every((k) => emptyIn(r, k, today)))) return false;
  if (f.no.some((g) => !g.some((k) => emptyIn(r, k, today)))) return false;
  const hay = low(`${r.title || ""} ${r.id || ""}`);
  return f.text.every((w) => hay.includes(low(w)));
}

const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
const dueKey = (r) => (dayNumber(r.due) !== null ? [0, r.due] : [1, ""]);
function byDue(x, y) {
  const a = dueKey(x), b = dueKey(y);
  return cmp(a[0], b[0]) || cmp(a[1], b[1]);
}
const kindRank = (r) => { const i = KINDS.indexOf(r.kind); return i < 0 ? KINDS.length : i; };
const ownerKey = (r) => { const o = String(r.owner == null ? "" : r.owner).trim().toLowerCase(); return o ? [0, o] : [1, ""]; };
const rank = (r) => { const i = PRIORITIES.indexOf(r.priority); return i < 0 ? PRIORITIES.length : i; };

// The filter with the owners, workstreams and use cases that no longer exist taken out of its choices; null when a choice list had
// names and none is left (a name that is gone matches nothing): section_kinds/workitems.py _alive. `live` as liveOf makes it.
function alive(filter, live) {
  if (!live) return filter;
  const ok = {
    owner: (c) => !(live.goneOwner || []).includes(low(tidy(c))),
    workstream: (c) => !live.workstream || live.workstream.includes(low(tidy(c))),
    use_case: (c) => !live.use_case || live.use_case.includes(c),
  };
  const out = { ...filter };
  for (const f of Object.keys(ok)) {
    if (!filter[f].length) continue;
    out[f] = filter[f].filter((c) => c === NONE || ok[f](c));
    if (!out[f].length) return null;
  }
  return out;
}

// What still exists in the data the page has: workstream names, use case ids, and the owners archived from the people list.
export function liveOf(data) {
  const some = (k, f) => (Array.isArray(data && data[k]) ? data[k].map(f) : null);
  return { workstream: some("workstreams", (w) => low(tidy(w.name))), use_case: some("use_cases", (u) => u.id), goneOwner: (data && data.gone_owners) || [] };
}

// The ids of `rows` (ruleRows' shape) that `filter` lists, sorted and cut to its max (`all` true: every hit, for Show all items): section_kinds/workitems.py matching().
export function matching(filter, rows, today, live, all) {
  filter = alive(filter, live);
  if (!filter) return [];
  const hits = rows.filter((r) => typeof r.id === "string" && r.id
    && modeFits(filter.mode, r, today)
    && FILTERS.every((f) => member(r, f, filter[f], today)) && allowed(r, filter, today));
  const closedLast = (x, y) => cmp(isOpen(x) ? 0 : 1, isOpen(y) ? 0 : 1);
  if (filter.sort === "id") hits.sort((x, y) => cmp(x.id, y.id));
  else if (filter.sort === "priority") hits.sort((x, y) => closedLast(x, y) || cmp(rank(x), rank(y)) || byDue(x, y) || cmp(x.id, y.id));
  else if (filter.sort === "type") hits.sort((x, y) => closedLast(x, y) || cmp(kindRank(x), kindRank(y)) || byDue(x, y) || cmp(x.id, y.id));
  else if (filter.sort === "owner") hits.sort((x, y) => closedLast(x, y) || cmp(ownerKey(x)[0], ownerKey(y)[0]) || cmp(ownerKey(x)[1], ownerKey(y)[1]) || byDue(x, y) || cmp(x.id, y.id));
  else hits.sort((x, y) => closedLast(x, y) || byDue(x, y) || cmp(x.id, y.id));
  return (all ? hits : hits.slice(0, filter.max)).map((r) => r.id);
}

// The rules for what the page clark serves may show: the publishable() mirror of publish.select, from what the data carries.
export function servedRules(data) {
  const rules = rulesFor({ code: data && data.project && data.project.code, hidden: ((data && data.report_hidden) || []).map((h) => (h && h.item_id) || h),
    labelRules: (data && data.label_rules) || [], labels: (data && data.labels) || {}, sections: (data && data.report_sections) || [], deleted: !!(data && data.sections_deleted) });
  for (const k of WORK) rules.hiddenTypes.delete(k);      // row 1268: a list prints its own rows when the built-in section is hidden (publish.select does the same)
  return rules;
}

// Only the rows that would be published, of the three work kinds, in a data shape ruleRows reads.
export function publishedOnly(data) {
  const rules = servedRules(data);
  const out = { ...data };
  for (const k of WORK) out[k] = ((data && data[k]) || []).filter((r) => publishable(r, k, rules));
  out.milestones = ((data && data.milestones) || []).filter((m) => publishable(m, "milestones", rules));      // a client sees a milestone's name only when it is published
  return out;
}

// What the list shows, as { items: [ids in order], columns, caption, saved }. A published file: the ids its section carries that its
// data holds. The page clark serves: the saved filter over the rows that would be published. `saved` is false when no filter is
// saved yet (then the list is empty and the section stays out of View and the file).
export function listOf(section, data, today) {
  if (section && Array.isArray(section.items)) {
    const there = new Set(WORK.flatMap((k) => ((data && data[k]) || []).map((r) => r.id)));
    const cols = isList(section.columns) ? section.columns.filter((c) => COLUMNS.includes(c)) : [];
    return { items: section.items.filter((id) => typeof id === "string" && there.has(id)), columns: cols.length ? cols : SAVED_FALLBACK_COLUMNS.slice(),
      caption: typeof section.caption === "string" ? section.caption : "", saved: true };
  }
  const filter = filterOf(section);
  if (!filter) return { items: [], columns: SAVED_FALLBACK_COLUMNS.slice(), caption: "", saved: false };
  const every = matching({ ...filter, max: Number.MAX_SAFE_INTEGER }, ruleRows(publishedOnly(data)), today, liveOf(data));
  return { items: every.slice(0, filter.max), all: every, max: filter.max, more: every.length > filter.max, columns: filter.columns.length ? filter.columns : SAVED_FALLBACK_COLUMNS.slice(), caption: filter.caption, saved: true };
}

// What Edit lists: the rows the saved filter lists (as listOf) plus the ones the client eye has taken off (the work item's own client-visible
// flag, or its hidden entry), so an eye turned off can be turned on again from here. Rows publish keeps out for any other reason (Sensitive,
// archived, another project, a hidden section) are never listed. Walks the filter's whole match in its order: an eye-off row is listed where
// it falls, a kept row counts toward the filter's max, and nothing after the max-th kept row is listed. Returns the listOf shape plus `off`
// (the ids listed that the client does not see).
export function editListOf(section, data, today) {
  const base = listOf(section, data, today);
  const filter = filterOf(section);
  if (!filter || (section && Array.isArray(section.items))) return { ...base, off: [] };
  const served = servedRules(data), open = { ...served, hidden: new Set() };
  const out = { ...data };
  for (const k of WORK) out[k] = ((data && data[k]) || []).filter((r) => publishable({ ...r, client_visible: 1 }, k, open));
  const off = new Set(WORK.flatMap((k) => (out[k] || []).filter((r) => !publishable(r, k, served)).map((r) => r.id)));
  const every = matching({ ...filter, max: Number.MAX_SAFE_INTEGER }, ruleRows(out), today, liveOf(data));
  const items = [], listedOff = [];
  let kept = 0, full = false;
  for (const id of every) {
    if (full) continue;
    if (off.has(id)) { items.push(id); listedOff.push(id); }
    else if (kept < filter.max) { items.push(id); kept += 1; }
    else full = true;
  }
  return { ...base, items, all: every, max: filter.max, more: full, off: listedOff };
}

// The rows to draw for a list's ids, in the ids' order, from the data (workItems.js rowsOf: title, owner, dates, status).
export function drawRows(ids, data) {
  const byId = new Map(rowsOf(data || {}).map((r) => [r.id, r]));
  return ids.map((id) => byId.get(id)).filter(Boolean);
}

// The values a filter can offer for owner, workstream and use case: those found in the rows that would be published, then any
// already chosen that are not (so a saved choice can always be taken off). Sorted, "(none)" last.
export function offered(field, data, chosen) {
  const rows = ruleRows(publishedOnly(data));
  const seen = new Set();
  for (const r of rows) seen.add(tidy(r[field]) || NONE);
  for (const v of chosen || []) seen.add(v);
  const list = [...seen].filter((v) => v !== NONE).sort((a, b) => a.localeCompare(b));
  return seen.has(NONE) ? [...list, NONE] : list;
}

// Row 1199: the rows the section draws, the first Most rows or, once "Show all items" is open, every row the filter lists (the served page only:
// a published file carries just the ids publish chose, so it has none to add). `more` is true when there are rows beyond Most rows.
export const idsToShow = (list, all) => (all && list.all ? list.all : list.items);

// The data a served page draws rows from: a milestone's name is read only when the report would publish that milestone, as in a file.
export function drawn(data, served) {
  if (!served) return data;
  return { ...data, milestones: publishedOnly(data).milestones };
}
