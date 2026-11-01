// Work items list (#96), store type "workitems": the pure rules (no DOM, no Preact). The section holds a saved filter, never rows;
// the rows are chosen again each time from the project's records. The same rules as src/clark/section_kinds/workitems.py
// (tests/test_tpl_workitems.py runs the two over the same rows):
// - the page clark serves (View and Edit's preview) reads the saved filter from the section's body and lists only rows that
//   logic/publishable.js would publish, so View shows exactly what the client sees (FR-11);
// - a published file holds no filter: its section carries `items` (the ids publish chose, in order, from rows it already kept),
//   `columns` and `caption`, and the rows are drawn from the file's own data.
import { dayNumber, rowsOf } from "../workItems.js";
import { rulesFor, publishable } from "../logic/publishable.js";

export const KINDS = ["action", "risk", "issue", "assumption", "dependency", "decision"];
export const MODES = ["open", "closed", "all"];
export const STATUSES = ["Open", "Delayed", "Pending", "Closed", "Cancelled", "Made", "Withdrawn"];
export const DUE = ["overdue", "soon", "none", "later"];
export const NONE = "(none)";
export const PRIORITIES = ["Urgent", "High", "Medium", "Low"];
export const SORTS = ["due", "priority", "id"];
export const COLUMNS = ["type", "id", "owner", "due", "status", "workstream"];
export const DEFAULT_COLUMNS = ["type", "id", "owner", "due", "status"];
export const MAX_ROWS = 50;
export const DEFAULT_MAX = 10;
export const MAX_CAPTION = 200;
const CLOSED = ["Closed", "Cancelled", "Made", "Withdrawn"];
const FILTERS = ["kinds", "status", "due", "owner", "workstream", "use_case", "priority"];
const WORK = ["actions", "raid", "decisions"];

// The words a person reads for each choice.
export const WORDS = {
  kinds: { action: "Actions", risk: "Risks", issue: "Issues", assumption: "Assumptions", dependency: "Dependencies", decision: "Decisions" },
  mode: { open: "Open", closed: "Closed", all: "Open and closed" },
  due: { overdue: "Overdue", soon: "Due in 7 days", none: "No date", later: "Later" },
  sort: { due: "Due date", priority: "Priority", id: "ID" },
  columns: { type: "Type", id: "ID", owner: "Owner", due: "Due", status: "Status", workstream: "Workstream" },
  none: { owner: "No owner", workstream: "No workstream", use_case: "No use case", priority: "No priority" },
};

// The filter a new list starts from: open work items of every kind, soonest due first, ten at most, the default columns.
export function defaults() {
  return { v: 1, kinds: [], mode: "open", status: [], due: [], owner: [], workstream: [], use_case: [], priority: [], sort: "due",
    max: DEFAULT_MAX, columns: DEFAULT_COLUMNS.slice(), caption: "" };
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
  for (const f of [...FILTERS, "columns"]) if (isList(v[f])) out[f] = v[f].slice();
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
  for (const r of (data && data.actions) || []) out.push({ id: r.id, kind: "action", status: r.status, owner: r.owner, workstream: r.workstream, use_case: r.use_case, priority: r.priority, due: r.due_date });
  for (const r of (data && data.raid) || []) out.push({ id: r.id, kind: String(r.type == null ? "" : r.type).toLowerCase(), status: r.status, owner: r.owner, workstream: r.workstream, use_case: r.use_case, priority: r.priority, due: r.due_date });
  for (const r of (data && data.decisions) || []) out.push({ id: r.id, kind: "decision", status: r.status, owner: r.made_by, workstream: null, use_case: r.use_case, priority: null, due: r.status === "Pending" ? r.needed_by : r.date });
  return out;
}

const isOpen = (r) => !CLOSED.includes(r.status);
const tidy = (v) => (typeof v === "string" ? v.split(/\s+/).filter(Boolean).join(" ") : "");

function bucket(r, today) {
  const a = dayNumber(r.due), t = dayNumber(today);
  if (a === null || t === null) return "none";
  if (!isOpen(r)) return "";
  return a < t ? "overdue" : a - t <= 7 ? "soon" : "later";
}

function member(r, field, chosen, today) {
  if (!chosen.length) return true;
  if (field === "kinds") return chosen.includes(r.kind);
  if (field === "status") return chosen.includes(r.status);
  if (field === "due") return chosen.includes(bucket(r, today));
  return chosen.includes(tidy(r[field]) || NONE);
}

const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
const dueKey = (r) => (dayNumber(r.due) !== null ? [0, r.due] : [1, ""]);
function byDue(x, y) {
  const a = dueKey(x), b = dueKey(y);
  return cmp(a[0], b[0]) || cmp(a[1], b[1]);
}
const rank = (r) => { const i = PRIORITIES.indexOf(r.priority); return i < 0 ? PRIORITIES.length : i; };

// The ids of `rows` (ruleRows' shape) that `filter` lists, sorted and cut to its max: section_kinds/workitems.py matching().
export function matching(filter, rows, today) {
  const hits = rows.filter((r) => typeof r.id === "string" && r.id
    && (filter.mode === "all" || (filter.mode === "open") === isOpen(r))
    && FILTERS.every((f) => member(r, f, filter[f], today)));
  const closedLast = (x, y) => cmp(isOpen(x) ? 0 : 1, isOpen(y) ? 0 : 1);
  if (filter.sort === "id") hits.sort((x, y) => cmp(x.id, y.id));
  else if (filter.sort === "priority") hits.sort((x, y) => closedLast(x, y) || cmp(rank(x), rank(y)) || byDue(x, y) || cmp(x.id, y.id));
  else hits.sort((x, y) => closedLast(x, y) || byDue(x, y) || cmp(x.id, y.id));
  return hits.slice(0, filter.max).map((r) => r.id);
}

// The rules for what the page clark serves may show: the publishable() mirror of publish.select, from what the data carries.
export function servedRules(data) {
  return rulesFor({ code: data && data.project && data.project.code, hidden: (data && data.report_hidden) || [],
    labelRules: (data && data.label_rules) || [], labels: (data && data.labels) || {}, sections: (data && data.report_sections) || [] });
}

// Only the rows that would be published, of the three work kinds, in a data shape ruleRows reads.
export function publishedOnly(data) {
  const rules = servedRules(data);
  const out = { ...data };
  for (const k of WORK) out[k] = ((data && data[k]) || []).filter((r) => publishable(r, k, rules));
  return out;
}

// What the list shows, as { items: [ids in order], columns, caption, saved }. A published file: the ids its section carries that its
// data holds. The page clark serves: the saved filter over the rows that would be published. `saved` is false when no filter is
// saved yet (then the list is empty and the section stays out of View and the file).
export function listOf(section, data, today) {
  if (section && Array.isArray(section.items)) {
    const there = new Set(WORK.flatMap((k) => ((data && data[k]) || []).map((r) => r.id)));
    const cols = isList(section.columns) ? section.columns.filter((c) => COLUMNS.includes(c)) : [];
    return { items: section.items.filter((id) => typeof id === "string" && there.has(id)), columns: cols.length ? cols : DEFAULT_COLUMNS.slice(),
      caption: typeof section.caption === "string" ? section.caption : "", saved: true };
  }
  const filter = filterOf(section);
  if (!filter) return { items: [], columns: DEFAULT_COLUMNS.slice(), caption: "", saved: false };
  return { items: matching(filter, ruleRows(publishedOnly(data)), today), columns: filter.columns.length ? filter.columns : DEFAULT_COLUMNS.slice(), caption: filter.caption, saved: true };
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
