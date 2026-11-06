// The Gantt page's own rules (#926, #928), pure: no page, no store, no saving. The page holds the plan in the shape the data layer stores
// (the "stored line" below); the chart and the table each want their own shape, so this file turns one into the other and works out what changed.
//
// A stored line: { id 'GNT-001', name, type 'phase'|'task'|'milestone', parent, start, end (YYYY-MM-DD), pct, health, depends [ids], owner,
//   workstream, priority, baseline_start, baseline_end, effort, budget, deliverable, show 0|1, note, sort_order }.
// (The agreed contract lists no `name`; the line's name is its "Line" column, so it is carried here as `name`. Change it in one place: NAME.)

import { FIELDS, DEFAULT_NAME } from "../ganttTab.js";

export const NAME = "name";

export const DEFAULT_SETTINGS = {
  [FIELDS.editor]: 0, [FIELDS.client]: 0, [FIELDS.name]: DEFAULT_NAME, gantt_title: "",      // the three tab fields are named in ganttTab.js only
  gantt_hidden_columns: ["show", "note", "budget", "effort", "baseline_start", "baseline_end"],
  gantt_plan_rows: null,                      // the saved plan height in rows (null = every row); not in the first contract, added by the page
};

// The page's words. Every one is in the spec's word list (#926 section 4) unless it says "added".
export const PAGE_WORDS = {
  edit: "Edit", view: "View", table: "Table", chart: "Chart",
  editTip: "Edit the plan", viewTip: "Back to the view (what the client sees)", tableTip: "Show the plan as a table", chartTip: "Back to the chart",
  exportXl: "Export to Excel", importXl: "Import from Excel",
  soon: "Coming with the Excel step",                                                   // added: the disabled export and import
  show: "Show", undo: "Undo",
  editNote: "Editing · each change saves on its own",                                  // the Dashboard's own words, reused
  titleLabel: "Title",                                                                   // added: the title box's accessible name
  titleChanged: "Title changed.",                                                        // added: the title's Undo toast
  changed: (id) => `${id} changed.`,                                                     // added: a line edited in the chart
  added: "A line was added with the next free ID.",
  deleted: (id) => `Line ${id} deleted.`,
  deletedMany: (n) => `${n} lines deleted.`,                                             // added
  eyeOn: (name) => `Shown on the dashboard: ${name}.`,
  eyeOff: (name) => `Taken off the dashboard: ${name}.`,
  colOn: (col) => `${col}: shown to the client.`,
  colOff: (col) => `${col}: hidden from the client.`,
  rows: (n, m) => `Plan height saved: ${n} of ${m} rows. Viewers can still change their own.`,
  rowsAll: "Plan height: all rows shown.",
  columnsChanged: "Hidden columns changed.",                                             // added: the table's column eye
};

// The chart's column keys are the stored names; the table's keys are shorter. One map between them.
const TABLE_KEY = {
  id: "id", name: "n", type: "t", parent: "par", start: "s", end: "e", pct: "pct", health: "rag", depends: "dep", owner: "o", workstream: "ws",
  priority: "pri", baseline_start: "bs", baseline_end: "be", effort: "eff", budget: "cost", deliverable: "del", show: "show", note: "note",
};
const STORED_KEY = Object.fromEntries(Object.entries(TABLE_KEY).map(([k, v]) => [v, k]));
export const hiddenForTable = (keys) => (keys || []).map((k) => TABLE_KEY[k]).filter(Boolean);
export const hiddenFromTable = (keys) => (keys || []).map((k) => STORED_KEY[k]).filter(Boolean);
export const CHART_COLUMNS = { start: "Start", end: "End", pct: "Done" };

const TYPE_SHORT = { phase: "p", task: "t", milestone: "m" };
const TYPE_LONG = { p: "phase", t: "task", m: "milestone" };
const num = (v) => (v === null || v === undefined || v === "" ? "" : v);
const on = (v) => !!v && v !== "0";

export const sortLines = (lines) => (lines || []).slice().sort((a, b) => (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0));

export function toChart(lines) {
  return sortLines(lines).map((l) => ({ id: l.id, name: l[NAME] || "", type: l.type, parent: l.parent || "", start: l.start || "", end: l.end || l.start || "",
    pct: Number(l.pct) || 0, depends: l.depends || [], show: on(l.show) }));
}

export function toTable(lines) {
  return sortLines(lines).map((l) => ({
    id: l.id, n: l[NAME] || "", t: TYPE_SHORT[l.type] || "t", par: l.parent || "", s: l.start || "", e: l.end || l.start || "", pct: Number(l.pct) || 0,
    rag: l.health || "", dep: l.depends || [], o: l.owner || "", ws: l.workstream || "", pri: l.priority || "", bs: l.baseline_start || "", be: l.baseline_end || "",
    eff: num(l.effort), cost: num(l.budget), del: l.deliverable || "", show: on(l.show), note: l.note || "",
  }));
}

// The whole list the table handed back, as stored lines in that order (sort_order is the place in the list).
export function fromTable(rows) {
  return rows.map((r, i) => ({
    id: r.id, [NAME]: r.n, type: TYPE_LONG[r.t] || "task", parent: r.par || "", start: r.s, end: r.t === "m" ? r.s : r.e, pct: Number(r.pct) || 0, health: r.rag || "",
    depends: r.dep || [], owner: r.o || "", workstream: r.ws || "", priority: r.pri || "", baseline_start: r.bs || "", baseline_end: r.be || "",
    effort: num(r.eff), budget: num(r.cost), deliverable: r.del || "", show: r.show ? 1 : 0, note: r.note || "", sort_order: i + 1,
  }));
}

export const renumber = (lines) => lines.map((l, i) => (l.sort_order === i + 1 ? l : { ...l, sort_order: i + 1 }));

// One change from the chart (a name, the done %, the dates) applied to the stored line.
export function applyChart(line, field, value) {
  if (field === "dates") return { ...line, start: value.start, end: value.end };
  if (field === "name") return { ...line, [NAME]: value };
  return { ...line, [field]: value };
}

// A line the chart added, as a stored line.
export const fromChartLine = (c) => ({
  id: c.id, [NAME]: c.name, type: c.type, parent: c.parent || "", start: c.start, end: c.end, pct: 0, health: "", depends: [], owner: "", workstream: "",
  priority: "", baseline_start: "", baseline_end: "", effort: "", budget: "", deliverable: "", show: 0, note: "", sort_order: 0,
});

// Adding below, then deleting: the new list (stored lines, in order). A deleted phase's tasks keep their place at the top level; a line that
// depended on a deleted line stops depending on it.
export function without(lines, ids) {
  const gone = new Set(ids);
  return renumber(sortLines(lines).filter((l) => !gone.has(l.id)).map((l) => {
    const parent = gone.has(l.parent) ? "" : l.parent;
    const depends = (l.depends || []).filter((d) => !gone.has(d));
    return parent === l.parent && depends.length === (l.depends || []).length ? l : { ...l, parent, depends };
  }));
}

const same = (a, b) => JSON.stringify(a ?? "") === JSON.stringify(b ?? "");
export const FIELDS = ["name", "type", "parent", "start", "end", "pct", "health", "depends", "owner", "workstream", "priority", "baseline_start", "baseline_end",
  "effort", "budget", "deliverable", "show", "note", "sort_order"];

// What changed between two lists, as the steps the data layer takes: new (every field), update (only the fields that changed), delete.
export function diff(before, after) {
  const was = new Map((before || []).map((l) => [l.id, l]));
  const now = new Set(after.map((l) => l.id));
  const ops = [];
  for (const l of after) {
    const old = was.get(l.id);
    if (!old) { ops.push({ op: "new", id: l.id, values: pick(l) }); continue; }
    const changes = {};
    for (const f of FIELDS) {
      const key = f === "name" ? NAME : f;
      if (!same(f === "show" ? (on(old.show) ? 1 : 0) : old[key], f === "show" ? (on(l.show) ? 1 : 0) : l[key])) changes[f] = f === "show" ? (on(l.show) ? 1 : 0) : l[key];
    }
    if (Object.keys(changes).length) ops.push({ op: "update", id: l.id, changes });
  }
  for (const l of before || []) if (!now.has(l.id)) ops.push({ op: "delete", id: l.id });
  return ops;
}
const pick = (l) => Object.fromEntries(FIELDS.map((f) => [f, f === "name" ? l[NAME] : f === "show" ? (on(l.show) ? 1 : 0) : l[f]]));

// Put the steps into a list (the in-memory host uses this; the store host lets the server do it).
export function applyOps(lines, ops) {
  let out = (lines || []).slice();
  for (const o of ops) {
    if (o.op === "new") out.push({ ...o.values, id: o.id, [NAME]: o.values.name });
    else if (o.op === "delete") out = out.filter((l) => l.id !== o.id);
    else out = out.map((l) => (l.id === o.id ? { ...l, ...Object.fromEntries(Object.entries(o.changes).map(([k, v]) => [k === "name" ? NAME : k, v])) } : l));
  }
  return sortLines(out);
}

