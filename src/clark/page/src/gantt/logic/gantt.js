// The project Gantt chart's rules (row 926): pure functions and words, no DOM, no store, no clock (the caller passes today). Nothing is sent
// or saved here. A line is
//   { id, name, type: "phase" | "task" | "milestone", parent, start, end, pct, depends: [id], show }
// with dates stored YYYY-MM-DD and shown DD-MM-YYYY. The `id` is the stored, steady id (GNT-001); the outline number (phases 1, 2, 3, tasks
// 2.1, milestones M-1) is for the eye only: it is worked out from the order of the lines every time, so adding, deleting or moving a line
// renumbers what a reader sees while every dependency and parent keeps pointing at the right line. A milestone has one date: its end is its start.

import { EXAMPLE_DATE } from "./ganttWords.js";

export const DAY_MS = 864e5;
export const TYPES = ["phase", "task", "milestone"];
export const SCALES = ["week", "month", "quarter"];
export const FILTERS = ["all", "phases", "milestones", "ticked"];
export const YEARS = [2000, 2100];
export const NAME_MAX = 120;
export const MIN_PPD = 1.4;          // the narrowest a day may be drawn, in pixels
export const WEEK_PPD = 7;           // the Week scale draws a day at least this wide
export const MAX_ZOOM = 8;
export const ZOOM_STEP = 1.25;

export const WORDS = {
  phase: "Phase", task: "Task", milestone: "Milestone",
  done: "Done", late: "Late", inprogress: "In progress", notstarted: "Not started",
  today: "Today", zoomOut: "Zoom out", zoomIn: "Zoom in", fit: "Back to fit",
  week: "Week", month: "Month", quarter: "Quarter",
  all: "All lines", phases: "Phases only", milestones: "Phases and milestones", ticked: "Ticked lines",
  show: "Show", scrollToday: "Scroll to today", expand: "Expand to full screen", unexpand: "Back to page width",
  name: "Phase / task", start: "Start", end: "End", date: "Date", pct: "Done",
  colOn: "Shown in the client view", colOff: "Hidden from the client view",
  grip: "Drag to show more or fewer rows", gripLabel: "Plan height: drag to show more or fewer rows",
  legendPhase: "Phase", legendTask: "Task (lighter part = done)", legendMilestone: "Milestone", legendAchieved: "Achieved", legendToday: "Today",
  legendDepends: "depends on", legendClash: "clash",
  detailEmpty: "Select a bar or a milestone to see its details here. Every bar also carries its name as text, so nothing depends on hover.",
  noLines: "No lines to show.",
  addTask: "Add a task below", addPhase: "Add a phase below", addMilestone: "Add a milestone below",
  deleteLine: "Delete this line",
  boxName: "Name", boxStart: "Start (DD-MM-YYYY)", boxEnd: "End (DD-MM-YYYY)", boxDate: "Date (DD-MM-YYYY)", boxPct: "Done, 0 to 100",
  save: "Save", cancel: "Cancel",
  badDate: `Use DD-MM-YYYY, for example ${EXAMPLE_DATE}.`, endBeforeStart: "The end cannot be before the start.", needName: "A line needs a name.",
  badPct: "Done % is a number from 0 to 100.", oneDate: "A milestone has one date: change Start.",
  startsBefore: "Starts before",
};
export const typeWord = (t) => WORDS[t] || "";
export const statusWord = (s) => WORDS[s] || "";
export const filterWord = (f) => WORDS[f] || WORDS.all;
export const linesShown = (n, m) => `${n} of ${m} lines shown`;

// ── dates ────────────────────────────────────────────────────────────────────

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
const SHOWN = /^(\d{1,2})-(\d{1,2})-(\d{4})$/;

// Days since 1970-01-01 for a stored date, or null if it is not a real date.
export function dayNum(iso) {
  const m = ISO.exec(String(iso || ""));
  if (!m) return null;
  const t = Date.UTC(+m[1], +m[2] - 1, +m[3]);
  const a = new Date(t);
  if (a.getUTCFullYear() !== +m[1] || a.getUTCMonth() !== +m[2] - 1 || a.getUTCDate() !== +m[3]) return null;
  return Math.round(t / DAY_MS);
}
export function isoOf(days) {
  const a = new Date(days * DAY_MS);
  return `${a.getUTCFullYear()}-${String(a.getUTCMonth() + 1).padStart(2, "0")}-${String(a.getUTCDate()).padStart(2, "0")}`;
}
export const addDays = (iso, n) => isoOf(dayNum(iso) + n);
// "2026-11-06" -> "06-11-2026"; anything that is not a stored date comes back empty (no bare dashes).
export function formatDate(iso) {
  return dayNum(iso) === null ? "" : `${iso.slice(8, 10)}-${iso.slice(5, 7)}-${iso.slice(0, 4)}`;
}
// What a person typed (DD-MM-YYYY, one or two digits for day and month) -> the stored date, or null.
export function parseDate(text) {
  const m = SHOWN.exec(String(text == null ? "" : text).trim());
  if (!m || +m[3] < YEARS[0] || +m[3] > YEARS[1]) return null;
  const iso = `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
  return dayNum(iso) === null ? null : iso;
}
// Whole days from a to b (b later is positive).
export const daysBetween = (a, b) => dayNum(b) - dayNum(a);
// The days a line spans, both ends counted.
export const spanDays = (line) => daysBetween(line.start, endOf(line)) + 1;
// A milestone's one date is its end too.
export const endOf = (line) => (line.type === "milestone" ? line.start : line.end);

// ── the line model ───────────────────────────────────────────────────────────

const cleanPct = (n) => Math.max(0, Math.min(100, Math.round(Number(n) || 0)));

// A line made safe to draw: a milestone's end is its start, done is 0 to 100, depends is a list.
export function tidy(line) {
  const type = TYPES.includes(line.type) ? line.type : "task";
  const start = dayNum(line.start) === null ? "" : line.start;
  let end = dayNum(line.end) === null ? start : line.end;
  if (type === "milestone") end = start;
  if (start && end && dayNum(end) < dayNum(start)) end = start;
  return { id: String(line.id), name: String(line.name == null ? "" : line.name), type, parent: line.parent || "", start, end,
    pct: cleanPct(line.pct), depends: Array.isArray(line.depends) ? line.depends.map(String) : [], show: line.show !== false && line.show !== 0 };
}
export const tidyAll = (lines) => (lines || []).map(tidy).filter((l) => l.start);
// The lines tidyAll leaves out because their start is no usable date (so they have nowhere on the time line), in their order. The chart says
// how many with the existing "N of M lines shown"; in the View only the lines with their eye on count (the others are not the viewer's).
export const leftOut = (lines, { edit = true } = {}) => (lines || []).map(tidy).filter((l) => !l.start && (edit || l.show));

// The next free steady id: GNT-001, GNT-002 ...
export function nextId(lines) {
  let top = 0;
  for (const l of lines) { const m = /^GNT-(\d+)$/.exec(l.id); if (m) top = Math.max(top, +m[1]); }
  return `GNT-${String(top + 1).padStart(3, "0")}`;
}

// A new line placed below `afterId`: a phase goes after the last line of the phase block it follows; a task takes the phase of the line above
// (or is that phase's own first task); a milestone likewise. It starts where the line above ends. Shown to the client: no (taking a line
// to the client is the author's choice). Returns { lines, line }.
export function addBelow(lines, afterId, type, id) {
  const i = lines.findIndex((l) => l.id === afterId);
  const ref = lines[i] || lines[lines.length - 1];
  const at = i < 0 ? lines.length : i;
  const kind = TYPES.includes(type) ? type : "task";
  const parent = kind === "phase" ? "" : !ref ? "" : ref.type === "phase" ? ref.id : ref.parent;
  const start = ref ? endOf(ref) : "";
  const end = kind === "milestone" ? start : addDays(start, 13);
  const name = "New " + kind;   // built from the kind, so the editor's own add-milestone words are not copied into the published file
  const line = { id: id || nextId(lines), name, type: kind, parent, start, end, pct: 0, depends: [], show: false };
  let to = at + 1;
  if (kind === "phase") { while (to < lines.length && lines[to].type !== "phase") to += 1; }
  const out = lines.slice();
  out.splice(to, 0, line);
  return { lines: out, line };
}

// ── outline numbers (display only) ───────────────────────────────────────────

// id -> the number a reader sees: phases 1, 2, 3; a task under a phase 2.1, 2.2; a milestone M-1, M-2; a task with no phase T-1.
export function outline(lines) {
  const map = {}, phases = new Set(lines.filter((l) => l.type === "phase").map((l) => l.id));
  let p = 0, m = 0, t = 0;
  const under = {};
  for (const l of lines) if (l.type === "phase") map[l.id] = String(++p);
  for (const l of lines) {
    if (l.type === "milestone") map[l.id] = `M-${++m}`;
    else if (l.type === "task") {
      if (l.parent && phases.has(l.parent)) { under[l.parent] = (under[l.parent] || 0) + 1; map[l.id] = `${map[l.parent]}.${under[l.parent]}`; }
      else map[l.id] = `T-${++t}`;
    }
  }
  return map;
}
// The same lines, each with its number (`no`), its parent's number and the numbers of what it depends on, so a screen never shows a stale one.
export function renumber(lines) {
  const map = outline(lines);
  return lines.map((l) => ({ ...l, no: map[l.id], parentNo: l.parent ? (map[l.parent] || "") : "", dependsNo: l.depends.map((d) => map[d] || d) }));
}

// ── clash and status ─────────────────────────────────────────────────────────

// id -> the ids it depends on that end after it starts (a line that starts on the day another ends is not a clash).
export function clashes(lines) {
  const by = Object.fromEntries(lines.map((l) => [l.id, l]));
  const out = {};
  for (const l of lines) {
    for (const d of l.depends) {
      const q = by[d];
      if (q && dayNum(l.start) < dayNum(endOf(q))) (out[l.id] = out[l.id] || []).push(d);
    }
  }
  return out;
}

// Done (100%), Late (ended before today and not done), In progress (some done, or today is inside it), Not started.
export function statusOf(line, today) {
  if (line.pct >= 100) return "done";
  const t = dayNum(today), s = dayNum(line.start), e = dayNum(endOf(line));
  if (t !== null && e !== null && e < t) return "late";
  if (line.pct > 0 || (t !== null && s !== null && s <= t && line.type !== "milestone")) return "inprogress";
  return "notstarted";
}

// ── rows to show ─────────────────────────────────────────────────────────────

// View draws the lines whose eye is on and nothing else. Edit draws every line. The filter: all, phases only, phases and milestones, and
// (Edit only) the ticked lines, which are the lines whose eye is on. In View a "ticked" choice is the same as All lines.
export function visibleRows(lines, { edit = false, filter = "all" } = {}) {
  const f = FILTERS.includes(filter) ? filter : "all";
  const base = edit ? lines : lines.filter((l) => l.show);
  return base.filter((l) => f === "all" || (f === "phases" && l.type === "phase") || (f === "milestones" && l.type !== "task") || (f === "ticked" && edit && l.show) || (f === "ticked" && !edit));
}
export const filtersFor = (edit) => (edit ? FILTERS : FILTERS.filter((f) => f !== "ticked"));

// How many rows the plan shows: in Edit the saved default; for a viewer their own choice, else the saved default. Never below 1 row and never
// beyond the last row (a missing or huge number means every row).
export function rowsShown(total, saved, own, edit) {
  if (total <= 0) return 0;
  const want = edit ? saved : (own === null || own === undefined ? saved : own);
  const n = want === null || want === undefined || !Number.isFinite(+want) ? total : Math.round(+want);
  return Math.max(1, Math.min(total, n));
}
// The rows a drag of the grip gives: it moves by whole rows.
export function rowsFromDrag(startRows, dy, rowH, total) {
  return Math.max(1, Math.min(total, Math.round(startRows + dy / rowH)));
}

// ── time scale ───────────────────────────────────────────────────────────────

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const monthStart = (iso) => `${iso.slice(0, 7)}-01`;
const nextMonth = (iso) => { const y = +iso.slice(0, 4), m = +iso.slice(5, 7); return m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, "0")}-01`; };

// The range the chart covers: from the first of the month of the earliest date (today counts) to the end of the month of the latest, and
// never under six months.
export function chartRange(lines, today) {
  const days = [];
  for (const l of lines) { days.push(dayNum(l.start), dayNum(endOf(l))); }
  if (dayNum(today) !== null) days.push(dayNum(today));
  const ok = days.filter((d) => d !== null);
  if (!ok.length) return null;
  const first = monthStart(isoOf(Math.min(...ok)));
  let stop = nextMonth(monthStart(isoOf(Math.max(...ok))));
  while (daysBetween(first, stop) < 180) stop = nextMonth(stop);
  return { start: first, end: addDays(stop, -1) };
}
// The pixels one day gets when the whole range fits the width.
export function fitPpd(width, range) {
  if (!range) return MIN_PPD;
  return Math.max(MIN_PPD, (width - 6) / (daysBetween(range.start, range.end) + 1));
}
export const clampZoom = (z) => Math.max(1, Math.min(MAX_ZOOM, Math.round((Number(z) || 1) * 100) / 100));
export const zoomIn = (z) => clampZoom(z * ZOOM_STEP);
export const zoomOut = (z) => clampZoom(z / ZOOM_STEP);
// The pixels one day gets: the fit width times the zoom, never below the fit. Week never draws a day narrower than WEEK_PPD.
export function ppdFor(scale, fit, zoom) {
  const base = scale === "week" ? Math.max(fit, WEEK_PPD) : fit;
  return base * clampZoom(zoom);
}
export const xOf = (iso, range, ppd) => (dayNum(iso) - dayNum(range.start)) * ppd;

// The date header: an upper band and a lower band, each cell { iso, label, to } where `to` is the date the cell stops at (exclusive).
export function headerCells(scale, range, ppd) {
  const upper = [], lower = [];
  const stop = addDays(range.end, 1);
  if (scale === "quarter") {
    for (let m = monthStart(range.start); dayNum(m) < dayNum(stop); m = nextMonth(m)) {
      const mo = +m.slice(5, 7) - 1;
      lower.push({ iso: m, label: MONTHS[mo], to: nextMonth(m) });
      if (mo % 3 === 0 || m === monthStart(range.start)) {
        let q = m; do { q = nextMonth(q); } while (dayNum(q) < dayNum(stop) && (+q.slice(5, 7) - 1) % 3 !== 0);
        upper.push({ iso: m, label: `Q${Math.floor(mo / 3) + 1} ${m.slice(0, 4)}`, to: dayNum(q) > dayNum(stop) ? stop : q });
      }
    }
    return { upper, lower };
  }
  for (let m = monthStart(range.start); dayNum(m) < dayNum(stop); m = nextMonth(m)) {
    upper.push({ iso: m, label: `${MONTHS[+m.slice(5, 7) - 1]} ${m.slice(2, 4)}`, to: nextMonth(m) });
    if (scale === "month" && ppd * 7 >= 28) {
      for (const d of [1, 8, 15, 22]) lower.push({ iso: addDays(m, d - 1), label: String(d).padStart(2, "0"), to: addDays(m, d + 6), edge: d === 1 });
    }
  }
  if (scale === "week") {
    let t = dayNum(range.start);
    t += (8 - ((t + 3) % 7 + 1)) % 7;                // forward to a Monday (1970-01-01 was a Thursday)
    for (; t < dayNum(stop); t += 7) lower.push({ iso: isoOf(t), label: isoOf(t).slice(8, 10), to: isoOf(t + 7) });
  }
  return { upper, lower };
}

// ── the dependency arrow ─────────────────────────────────────────────────────

// From the right end of what is depended on (ax, ay) to the left end of the line that depends on it (bx, by). A line that starts before
// its predecessor ends goes round through the gap between rows. Returns { d: path, head: polygon points }.
export function arrowPath(ax, ay, bx, by, rowH) {
  const head = `${bx},${by} ${bx - 6},${by - 3.5} ${bx - 6},${by + 3.5}`;
  if (bx - 4 >= ax + 10) return { d: `M${ax} ${ay} H${ax + 8} V${by} H${bx - 4}`, head };
  const ym = by >= ay ? by - rowH / 2 : by + rowH / 2;
  return { d: `M${ax} ${ay} H${ax + 8} V${ym} H${bx - 12} V${by} H${bx - 4}`, head };
}

// ── changes a person makes ───────────────────────────────────────────────────

// A bar moved by whole days keeps its length; a milestone moves its one date.
export function moved(line, delta) {
  const start = addDays(line.start, delta);
  return { start, end: line.type === "milestone" ? start : addDays(line.end, delta) };
}
// A bar's right edge dragged by whole days: never before its start. A milestone does not stretch.
export function resized(line, delta) {
  if (line.type === "milestone") return { start: line.start, end: line.start };
  const end = Math.max(dayNum(line.start), dayNum(line.end) + delta);
  return { start: line.start, end: isoOf(end) };
}

// What typed text means for one field of one line. Returns { ok: true, field, value } (field "dates" carries { start, end }; every other
// carries the plain value) or { ok: false, message } in plain words. Nothing here changes the line.
export function checkEdit(line, field, text) {
  const bad = (message) => ({ ok: false, message });
  if (field === "name") {
    const v = String(text == null ? "" : text).trim();
    return v ? { ok: true, field, value: v.slice(0, NAME_MAX) } : bad(WORDS.needName);
  }
  if (field === "pct") {
    const raw = String(text == null ? "" : text).trim().replace(/%$/, "");
    const n = Number(raw);
    return raw !== "" && Number.isInteger(n) && n >= 0 && n <= 100 ? { ok: true, field, value: n } : bad(WORDS.badPct);
  }
  if (field === "start" || field === "end") {
    const iso = parseDate(text);
    if (!iso) return bad(WORDS.badDate);
    if (line.type === "milestone") return field === "end" ? bad(WORDS.oneDate) : { ok: true, field: "dates", value: { start: iso, end: iso } };
    if (field === "start" && dayNum(iso) > dayNum(line.end)) return bad(WORDS.endBeforeStart);
    if (field === "end" && dayNum(iso) < dayNum(line.start)) return bad(WORDS.endBeforeStart);
    return { ok: true, field: "dates", value: { start: field === "start" ? iso : line.start, end: field === "end" ? iso : line.end } };
  }
  return bad(WORDS.badDate);
}

// The edit box's fields together -> the changes to send, or the first refusal. `form` is { name, start, end, pct } as typed (end and pct are
// absent for a milestone). Only what changed is returned: [{ field, value }].
export function checkBox(line, form) {
  const out = [];
  const name = checkEdit(line, "name", form.name);
  if (!name.ok) return { ok: false, message: name.message, field: "name" };
  if (name.value !== line.name) out.push({ field: "name", value: name.value });
  const s = parseDate(form.start);
  if (!s) return { ok: false, message: WORDS.badDate, field: "start" };
  let e = s;
  if (line.type !== "milestone") {
    e = parseDate(form.end);
    if (!e) return { ok: false, message: WORDS.badDate, field: "end" };
    if (dayNum(e) < dayNum(s)) return { ok: false, message: WORDS.endBeforeStart, field: "end" };
  }
  if (s !== line.start || e !== endOf(line)) out.push({ field: "dates", value: { start: s, end: e } });
  if (line.type !== "milestone") {
    const p = checkEdit(line, "pct", form.pct);
    if (!p.ok) return { ok: false, message: p.message, field: "pct" };
    if (p.value !== line.pct) out.push({ field: "pct", value: p.value });
  }
  return { ok: true, changes: out };
}

// The words under the chart when a line is selected.
export function detailOf(line, lines, today) {
  const no = outline(lines), by = Object.fromEntries(lines.map((l) => [l.id, l]));
  const bad = (clashes(lines)[line.id] || []).map((d) => no[d] || d);
  return {
    title: `${no[line.id]} ${line.name}`,
    kind: typeWord(line.type),
    when: line.type === "milestone" ? formatDate(line.start) : `${formatDate(line.start)} to ${formatDate(line.end)} (${spanDays(line)} days)`,
    pct: line.pct,
    status: statusWord(statusOf(line, today)),
    depends: line.depends.filter((d) => by[d]).map((d) => no[d] || d),
    clash: bad.length ? `${WORDS.startsBefore} ${bad.join(", ")} ends` : "",
    shown: !!line.show,
  };
}
