// What the Gantt page reads from the report's data, and the host of a published file (row 926). No store writes and no change route here, so the
// published page (page-view.html) carries this file and not the Edit parts. The server keeps a line's id as CODE-GNT-001 and the page shows
// GNT-001: the code is taken off on the way in (ganttStoreHost.js puts it back on the way out).
import { data, fromFile } from "../../stores/report.js";
import { DEFAULT_SETTINGS, sortLines } from "./ganttPage.js";

export const ROWS_FIELD = "gantt_default_rows";          // the server's name for the page's gantt_plan_rows

export const list = (v) => (Array.isArray(v) ? v : typeof v === "string" ? v.split(",") : []).map((s) => String(s).trim()).filter(Boolean);
export const strip = (code, id) => (typeof id === "string" && id.startsWith(`${code}-`) ? id.slice(code.length + 1) : id);

// A stored line as the page holds it (GNT-001, depends as a list, no parent as "").
function pageLine(code, l) {
  return { ...l, id: strip(code, l.id), parent: l.parent ? strip(code, l.parent) : "", depends: list(l.depends).map((d) => strip(code, d)) };
}

// The columns a published file may carry beyond the line's id and name; one it does not carry is hidden.
const FILE_COLUMNS = ["type", "parent", "start", "end", "pct", "health", "depends", "owner", "workstream", "priority", "baseline_start", "baseline_end",
  "effort", "budget", "deliverable", "show", "note"];

// The served page: every line and every setting of the open project.
export function readStore(d) {
  d = d || {};
  const p = d.project || {};
  const code = p.code || "";
  const settings = { ...DEFAULT_SETTINGS };
  for (const k of Object.keys(DEFAULT_SETTINGS)) if (p[k] !== undefined && p[k] !== null) settings[k] = p[k];
  if (p[ROWS_FIELD] !== undefined) settings.gantt_plan_rows = p[ROWS_FIELD];
  settings.gantt_hidden_columns = list(settings.gantt_hidden_columns);
  return { project: p, settings, lines: sortLines((d.gantt_lines || []).map((l) => pageLine(code, l))), toast: null };
}

// A published file: the lines and columns the file carries (data.gantt), nothing else. Every line in it has its eye on; a column it does not
// carry is hidden, so the page draws exactly what the file holds.
export function readFile(d) {
  d = d || {};
  const p = d.project || {};
  const g = d.gantt || {};
  const code = p.code || "";
  const columns = Array.isArray(g.columns) ? g.columns : [];
  const settings = { ...DEFAULT_SETTINGS, gantt_title: typeof g.title === "string" ? g.title : "", gantt_plan_rows: Number.isInteger(g.default_rows) ? g.default_rows : null,
    gantt_hidden_columns: FILE_COLUMNS.filter((c) => !columns.includes(c)) };
  const lines = (Array.isArray(g.lines) ? g.lines : []).map((l, i) => ({ ...pageLine(code, l), show: 1, sort_order: i + 1 }));
  return { project: p, settings, lines, toast: null };
}

// The host of a page that cannot change anything: a published file (reads what the file carries) or the served page looking at the past.
export function createFileHost() {
  const none = () => Promise.resolve({ ok: false });
  return { ownUndoKey: false, read: () => (fromFile.value ? readFile(data.value) : readStore(data.value)), subscribe: () => () => {}, applyLines: none, saveSettings: none, undoLast: none, dismiss() {} };
}
