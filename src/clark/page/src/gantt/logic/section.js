// The Gantt as a Dashboard section (#926 part 3): what the section reads from the report's data, as pure functions. No DOM, no Preact,
// nothing sent. The lines are `data.gantt_lines` (id, name, type, parent, start, end, pct, depends, show, sort_order ...); the columns the
// client must not see are `data.project.gantt_hidden_columns`. The server drops the eye-off lines and the hidden columns before a client
// file is built; the section drops them again here so the served View and a file read alike.
import { tidyAll, leftOut, visibleRows } from "./gantt.js";

// The chart's three optional columns, whatever the store calls them.
const COLUMN = { start: "start", start_date: "start", end: "end", end_date: "end", pct: "pct", percent_complete: "pct", done: "pct" };

const list = (v) => (Array.isArray(v) ? v : typeof v === "string" ? v.split(",") : []);

// The plan lines in the order the author saved them, in the shape the chart draws (logic/gantt.js tidy). Anything that is not a line is skipped.
export function allLinesOf(data) {
  // The editor's report carries data.gantt_lines; a published file carries only data.gantt.lines (the lines the client may see, already in order).
  const raw = data && Array.isArray(data.gantt_lines) ? data.gantt_lines : data && data.gantt && Array.isArray(data.gantt.lines) ? data.gantt.lines : [];
  const lines = raw.filter((l) => l && typeof l === "object" && l.id != null)
    .map((l, i) => ({ l, i, order: Number.isFinite(+l.sort_order) ? +l.sort_order : i }))
    .sort((a, b) => a.order - b.order || a.i - b.i)
    .map(({ l }) => ({ ...l, name: l.name != null ? l.name : l.line != null ? l.line : "", depends: list(l.depends).map((d) => String(d).trim()).filter(Boolean) }));
  return lines;
}
// The same, only the lines with a usable start date (the ones with a place on the time line).
export const linesOf = (data) => tidyAll(allLinesOf(data));
// How many lines with their eye on have no usable start date: the chart leaves them out and says so.
export const leftOutOf = (data) => leftOut(allLinesOf(data), { edit: false }).length;

// The chart columns (start, end, pct) the project hides from the client.
export function hiddenOf(data) {
  const project = (data && data.project) || {};
  const out = [];
  for (const k of list(project.gantt_hidden_columns)) {
    const c = COLUMN[String(k).trim()];
    if (c && !out.includes(c)) out.push(c);
  }
  return out;
}

// The plan height the author saved, in rows; null means every row. (A project field the guarded step will name; absent until then.)
export function savedRows(data) {
  const n = Math.round(Number(((data && data.project) || {}).gantt_default_rows));
  return Number.isFinite(n) && n >= 1 ? n : null;
}

// Whether the section has nothing to show: no line has its eye on.
export const isEmptyData = (data) => visibleRows(linesOf(data), { edit: false }).length === 0 && leftOutOf(data) === 0;
