// The Gantt table's rules (#926), as pure functions: no page, no store, no saving. The 21 columns, the value of a cell, how a typed or
// pasted value is checked (and the plain words of a refusal), copy and paste as tab-separated text, fill down and right, a many-step
// undo, and the maths of a selected range. components/GanttTable.jsx draws it and calls these; the parent page owns the data.
//
// A line is { id, n, t, par, s, e, pct, rag, dep, o, ws, pri, bs, be, eff, cost, del, show, note }:
//   id   the stored id (GNT-001); the outline number is display only    n  the name        t  'p' phase, 't' task, 'm' milestone
//   par  the parent phase id or ''     s, e  start and end as YYYY-MM-DD    pct  0 to 100    rag  '' or Green, Amber, Red
//   dep  an array of line ids          o, ws, del, note  text    pri  '' or High, Medium, Low    bs, be  baseline dates or ''
//   eff, cost  a number or ''          show  true when the line is on the dashboard (the eye)
// Every function returns new values; none changes what it was given. Dates are shown as DD-MM-YYYY and stored as YYYY-MM-DD.
import { EXAMPLE_DATE } from "./ganttWords.js";


const DAY = 864e5;

export const TYPES = { p: "Phase", t: "Task", m: "Milestone" };
const TYPE_KEYS = { phase: "p", task: "t", milestone: "m" };

// key, label, width at 100%, type (text, date, date0 a date that may be empty, num, num0 a number that may be empty, select, ro worked out).
const WHEN = "date";      // the column kind for a plain DD-MM-YYYY box; held apart so no source line reads as a browser calendar field
export const COLUMNS = [
  { key: "id", label: "ID", width: 116, type: "ro", locked: true },
  { key: "n", label: "Line", width: 220, type: "text", locked: true },
  { key: "t", label: "Type", width: 96, type: "select", options: ["Phase", "Task", "Milestone"] },
  { key: "par", label: "Parent", width: 76, type: "text" },
  { key: "s", label: "Start", width: 100, type: WHEN },
  { key: "e", label: "End", width: 100, type: WHEN },
  { key: "dur", label: "Days", width: 76, type: "ro" },
  { key: "pct", label: "Done %", width: 90, type: "num" },
  { key: "st", label: "Status", width: 104, type: "ro" },
  { key: "rag", label: "Health", width: 90, type: "select", options: ["", "Green", "Amber", "Red"] },
  { key: "dep", label: "Depends on", width: 124, type: "text" },
  { key: "o", label: "Owner", width: 150, type: "text" },
  { key: "ws", label: "Workstream", width: 120, type: "text" },
  { key: "pri", label: "Priority", width: 90, type: "select", options: ["", "High", "Medium", "Low"] },
  { key: "bs", label: "Baseline start", width: 112, type: "date0" },
  { key: "be", label: "Baseline end", width: 112, type: "date0" },
  { key: "eff", label: "Effort (days)", width: 104, type: "num0" },
  { key: "cost", label: "Budget", width: 96, type: "num0" },
  { key: "del", label: "Deliverable", width: 170, type: "text" },
  { key: "show", label: "On dashboard", width: 136, type: "select", options: ["Yes", "No"] },
  { key: "note", label: "Notes", width: 240, type: "text" },
];

// Hidden from the client view until the author says otherwise (the eye on the column header).
// Type, Start, End and Done % are always in a client file (the chart cannot be drawn without them), so they have no eye and are never saved as hidden.
export const MAX_EFFORT = 1000000, MAX_BUDGET = 10 ** 12;      // the same limits as the data layer (store.py GANTT_MAX_EFFORT, GANTT_MAX_BUDGET)
export const NEVER_HIDDEN = ["t", "s", "e", "pct"];
// Only a column the author types into can be hidden: ID, Days and Status are worked out, so they have no eye (the data layer's hideable list has none of them).
export const hideable = (col) => !col.locked && col.type !== "ro" && !NEVER_HIDDEN.includes(col.key);
export const DEFAULT_HIDDEN = ["show", "note", "cost", "eff", "bs", "be"];

export const WORDS = {
  badDate: (label) => (label === "Start" || label === "End" ? `Use DD-MM-YYYY, for example ${EXAMPLE_DATE}.` : `${label}: use DD-MM-YYYY, for example ${EXAMPLE_DATE}.`),
  endBeforeStart: "The end cannot be before the start.",
  needName: "A line needs a name.",
  pct: "Done % is a number from 0 to 100.",
  noDepend: (id) => `There is no line "${id}" to depend on.`,
  noParent: (id) => `There is no line "${id}" to be the parent.`,
  notPhase: (id) => `Line "${id}" is not a phase, so it cannot be a parent.`,
  oneDate: "A milestone has one date: change Start.",
  workedOut: (label) => `${label} is worked out; it cannot be typed over.`,
  number: (label) => `${label} is a number.`,
  bigNumber: "Effort and budget are numbers, zero or more.",      // the server's own sentence, for a number it would refuse (above the limits below)
  choose: (label, options) => `${label}: choose ${options.filter(Boolean).join(", ")}.`,
  viewOnly: "Switch to Edit to change the plan.",
  needValue: "Those cells need a value.",
  nothingToPaste: "Nothing to paste.",
  cleared: (n, bad) => `${n} cell${n === 1 ? "" : "s"} cleared${bad ? `, ${bad} need a value` : ""}.`,
  pasted: (n, bad, first) => `Pasted ${n} cell${n === 1 ? "" : "s"}${bad ? `, ${bad} refused (${first})` : ""}`,
  pasteNone: (first) => `Nothing pasted: ${first}`,
  filledDown: (n) => `Filled down ${n} cell${n === 1 ? "" : "s"}.`,
  filledRight: (n) => `Filled right ${n} cell${n === 1 ? "" : "s"}.`,
  filled: (n) => `Filled ${n} cell${n === 1 ? "" : "s"}.`,
  added: "A line was added with the next free ID",
  deleted: (ids) => (ids.length === 1 ? `Line ${ids[0]} deleted` : `${ids.length} lines deleted`),
  copied: "Copied. Paste it here or into Excel.",
  changed: (label, row) => `${label} changed on line ${row}.`,
  hiddenCol: (label, hidden) => `${label}: ${hidden ? "hidden from" : "shown to"} the client.`,
  startsBefore: (ids) => `Starts before ${ids.join(", ")} ends`,
};

// ── dates ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

const pad = (n) => String(n).padStart(2, "0");
const utc = (iso) => { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d); };
const isoOf = (t) => { const a = new Date(t); return `${a.getUTCFullYear()}-${pad(a.getUTCMonth() + 1)}-${pad(a.getUTCDate())}`; };

// DD-MM-YYYY (or D/M/YYYY, D.M.YYYY, or a stored YYYY-MM-DD) to YYYY-MM-DD; null when it is not a real day.
export function parseDate(text) {
  const v = String(text ?? "").trim();
  let y; let m; let d; let x = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/.exec(v);
  if (x) { d = +x[1]; m = +x[2]; y = +x[3]; } else if ((x = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(v))) { y = +x[1]; m = +x[2]; d = +x[3]; } else return null;
  const a = new Date(Date.UTC(y, m - 1, d));
  return a.getUTCFullYear() === y && a.getUTCMonth() === m - 1 && a.getUTCDate() === d ? `${y}-${pad(m)}-${pad(d)}` : null;
}

export const formatDate = (iso) => (iso ? `${iso.slice(8, 10)}-${iso.slice(5, 7)}-${iso.slice(0, 4)}` : "");
export const addDays = (iso, n) => isoOf(utc(iso) + n * DAY);

// ── what a cell shows ──────────────────────────────────────────────────────────────────────────────────────────────────

// Done, Late, In progress, Not started; worked out from the dates and the percentage, never typed.
export function statusOf(line, today) {
  if (line.pct >= 100) return "Done";
  if (today && line.e < today) return "Late";
  if ((today && line.s <= today) || line.pct > 0) return "In progress";
  return "Not started";
}

export function getValue(line, key, today = "") {
  switch (key) {
    case "t": return TYPES[line.t] || "";
    case "s": return formatDate(line.s);
    case "e": return line.t === "m" ? "" : formatDate(line.e);
    case "dur": return line.t === "m" || !line.s || !line.e ? "" : String(Math.round((utc(line.e) - utc(line.s)) / DAY) + 1);
    case "pct": return line.t === "m" ? "" : String(line.pct ?? 0);
    case "st": return statusOf(line, today);
    case "dep": return (line.dep || []).join(", ");
    case "show": return line.show ? "Yes" : "No";
    case "bs": case "be": return formatDate(line[key]);
    default: return line[key] === undefined || line[key] === null ? "" : String(line[key]);
  }
}

// Line ids whose end is after this line's start: { lineId: [ids it starts before] }.
export function clashes(lines) {
  const byId = new Map(lines.map((l) => [l.id, l]));
  const out = {};
  for (const l of lines) {
    const before = (l.dep || []).filter((id) => byId.has(id) && byId.get(id).e > l.s);
    if (before.length) out[l.id] = before;
  }
  return out;
}

// ── columns and rows ───────────────────────────────────────────────────────────────────────────────────────────────────

// View shows no hidden column (it is not drawn at all); Edit shows all, with the hidden ones marked. ID and Line are never hidden.
export function visibleColumns(hidden, edit) {
  const gone = new Set(hidden || []);
  return COLUMNS.filter((c) => edit || !hideable(c) || !gone.has(c.key));
}

export const FILTERS = { all: "All lines", phases: "Phases only", phasesMilestones: "Phases and milestones", ticked: "Ticked lines" };

// The indexes (in `lines`) of the rows the table draws, in order. View draws only lines that are on the dashboard; the filter is the page's "Show".
export function visibleRows(lines, { edit = false, filter = "all" } = {}) {
  const keep = (l) => {
    if (!edit && !l.show) return false;
    if (filter === "phases") return l.t === "p";
    if (filter === "phasesMilestones") return l.t !== "t";
    if (filter === "ticked") return edit && !!l.show;
    return true;
  };
  const out = [];
  lines.forEach((l, i) => { if (keep(l)) out.push(i); });
  return out;
}

// ── checking and setting one value ─────────────────────────────────────────────────────────────────────────────────────

const column = (key) => COLUMNS.find((c) => c.key === key);
const replaceAt = (lines, i, next) => lines.map((l, j) => (j === i ? next : l));

// Sets one cell. Gives { lines, error }: on a refusal `lines` is the same array and `error` is the sentence for the person.
export function setField(lines, index, key, text) {
  const col = column(key);
  const line = lines[index];
  const v = String(text ?? "").trim();
  const refuse = (error) => ({ lines, error });
  const done = (next) => ({ lines: replaceAt(lines, index, next), error: "" });
  if (!col || !line) return refuse("");
  if (col.type === "ro") return refuse(WORDS.workedOut(col.label));
  const ids = lines.map((l) => l.id);
  if (key === "n") return v ? done({ ...line, n: v }) : refuse(WORDS.needName);
  if (key === "par") {
    if (!v) return done({ ...line, par: "" });
    const parent = lines.find((l) => l.id === v);
    if (!parent || v === line.id) return refuse(WORDS.noParent(v));
    return parent.t === "p" ? done({ ...line, par: v }) : refuse(WORDS.notPhase(v));
  }
  if (key === "dep") {
    const list = v ? v.split(/[\s,;]+/).filter(Boolean) : [];
    const bad = list.find((id) => !ids.includes(id) || id === line.id);
    return bad ? refuse(WORDS.noDepend(bad)) : done({ ...line, dep: list });
  }
  if (col.type === "select") {
    let option = col.options.find((o) => o.toLowerCase() === v.toLowerCase());
    if (option === undefined && key === "t") option = col.options.find((o) => v.length === 1 && o[0].toLowerCase() === v.toLowerCase());
    if (option === undefined && key === "show") option = /^(y|true|1)$/i.test(v) ? "Yes" : /^(n|false|0)$/i.test(v) ? "No" : undefined;
    if (option === undefined) return refuse(WORDS.choose(col.label, col.options));
    if (key === "t") { const t = TYPE_KEYS[option.toLowerCase()]; return done({ ...line, t, e: t === "m" ? line.s : line.e }); }
    if (key === "show") return done({ ...line, show: option === "Yes" });
    return done({ ...line, [key]: option });
  }
  if (key === "s" || key === "e") {
    const iso = parseDate(v);
    if (iso === null) return refuse(WORDS.badDate(col.label));
    if (line.t === "m") return key === "e" ? refuse(WORDS.oneDate) : done({ ...line, s: iso, e: iso });
    const s = key === "s" ? iso : line.s;
    const e = key === "e" ? iso : line.e;
    return e < s ? refuse(WORDS.endBeforeStart) : done({ ...line, s, e });
  }
  if (key === "bs" || key === "be") {
    if (!v) return done({ ...line, [key]: "" });
    const iso = parseDate(v);
    return iso === null ? refuse(`${col.label}: use DD-MM-YYYY.`) : done({ ...line, [key]: iso });
  }
  if (key === "pct") {
    const n = Number(v.replace("%", ""));
    return v === "" || Number.isNaN(n) || n < 0 || n > 100 ? refuse(WORDS.pct) : done({ ...line, pct: Math.round(n) });
  }
  if (key === "eff" || key === "cost") {
    if (!v) return done({ ...line, [key]: "" });
    const n = Number(v.replace(/,/g, ""));
    return !Number.isFinite(n) || n < 0 || n > (key === "eff" ? MAX_EFFORT : MAX_BUDGET) ? refuse(WORDS.bigNumber) : done({ ...line, [key]: n });
  }
  return done({ ...line, [key]: v });
}

// ── lines: add and delete ──────────────────────────────────────────────────────────────────────────────────────────────

export function nextId(lines) {
  let top = 0;
  for (const l of lines) { const m = /^GNT-(\d+)$/.exec(l.id); if (m) top = Math.max(top, +m[1]); }
  return `GNT-${String(top + 1).padStart(3, "0")}`;
}

const NEW_KIND = { p: "phase", t: "task", m: "milestone" };
const NEW_NAME = (type) => "New " + (NEW_KIND[type] || NEW_KIND.t);   // built from the kind, so the editor's own add-milestone words are not copied into the published file

// A new line below the line `afterId` (at the end when it is not found), with the next free id, not on the dashboard until the author says so.
export function addLine(lines, afterId, type = "t") {
  const at = lines.findIndex((l) => l.id === afterId);
  const ref = lines[at >= 0 ? at : lines.length - 1];
  const s = ref ? ref.s : "";
  const line = {
    id: nextId(lines), n: NEW_NAME(type), t: type, par: ref && ref.t !== "p" ? ref.par || "" : "", s,
    e: type === "m" || !s ? s : addDays(s, 13), pct: 0, rag: "", dep: [], o: "", ws: "", pri: "", bs: "", be: "", eff: "", cost: "", del: "", show: false, note: "",
  };
  const next = lines.slice();
  next.splice(at >= 0 ? at + 1 : lines.length, 0, line);
  return { lines: next, id: line.id, index: next.indexOf(line) };
}

// Deletes the lines; what pointed at them (a dependency, a parent) lets go.
export function deleteLines(lines, ids) {
  const gone = new Set(ids);
  return lines.filter((l) => !gone.has(l.id)).map((l) => ({
    ...l, dep: (l.dep || []).filter((d) => !gone.has(d)), par: gone.has(l.par) ? "" : l.par,
  }));
}

// ── a selected range ───────────────────────────────────────────────────────────────────────────────────────────────────

// A selection is the cell it started at (ar, ac) and the cell it reaches (fr, fc), in the table's rows and columns as drawn.
export const makeSel = (ar, ac, fr = ar, fc = ac) => ({ ar, ac, fr, fc });
export const rangeOf = (s) => ({ r0: Math.min(s.ar, s.fr), r1: Math.max(s.ar, s.fr), c0: Math.min(s.ac, s.fc), c1: Math.max(s.ac, s.fc) });
export const cellCount = (s) => { const { r0, r1, c0, c1 } = rangeOf(s); return (r1 - r0 + 1) * (c1 - c0 + 1); };
export const inRange = (s, r, c) => { const g = rangeOf(s); return r >= g.r0 && r <= g.r1 && c >= g.c0 && c <= g.c1; };
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));

export function clampSel(s, rows, cols) {
  const r = (n) => clamp(n, 0, Math.max(0, rows - 1));
  const c = (n) => clamp(n, 0, Math.max(0, cols - 1));
  return makeSel(r(s.ar), c(s.ac), r(s.fr), c(s.fc));
}

// An arrow key: one step, or (with Cmd/Ctrl) to the edge; with Shift the far corner moves and the start stays.
export function moveSel(s, dr, dc, { extend = false, edge = false, rows, cols }) {
  const tr = edge ? (dr < 0 ? 0 : dr > 0 ? rows - 1 : s.fr) : s.fr + dr;
  const tc = edge ? (dc < 0 ? 0 : dc > 0 ? cols - 1 : s.fc) : s.fc + dc;
  return clampSel(extend ? makeSel(s.ar, s.ac, tr, tc) : makeSel(tr, tc), rows, cols);
}

export const homeSel = (s, edge) => (edge ? makeSel(0, 0) : makeSel(s.fr, 0));
export const endSel = (s, edge, rows, cols) => (edge ? makeSel(rows - 1, cols - 1) : makeSel(s.fr, cols - 1));
export const selectRow = (s, r, cols, extend) => makeSel(extend ? s.ar : r, 0, r, cols - 1);
export const selectColumn = (s, c, rows, extend) => makeSel(0, extend ? s.ac : c, rows - 1, c);
export const selectAll = (rows, cols) => makeSel(0, 0, rows - 1, cols - 1);

// Tab moves right and wraps to the next line; past the last cell of the last line it asks for a new line.
export function tabNext(s, back, rows, cols) {
  let r = s.fr; let c = s.fc + (back ? -1 : 1);
  if (c >= cols) { c = 0; r += 1; }
  if (c < 0) { c = cols - 1; r -= 1; }
  if (r >= rows) return { sel: makeSel(rows - 1, cols - 1), addLine: true };
  if (r < 0) return { sel: makeSel(0, 0), addLine: false };
  return { sel: makeSel(r, c), addLine: false };
}

// Enter moves down (Shift+Enter up); past the last line it stays on the last.
export const enterNext = (s, back, rows) => makeSel(clamp(s.fr + (back ? -1 : 1), 0, rows - 1), s.fc);

// ── copy and paste ─────────────────────────────────────────────────────────────────────────────────────────────────────

// The selected cells as tab-separated text (rows by new lines), as Excel reads it. A cell with a tab, a quote or a new line is quoted.
export function toTSV(lines, rows, cols, sel, today = "") {
  const { r0, r1, c0, c1 } = rangeOf(sel);
  const quote = (t) => (/[\t\n"]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t);
  const out = [];
  for (let r = r0; r <= r1; r++) {
    const row = [];
    for (let c = c0; c <= c1; c++) row.push(quote(getValue(lines[rows[r]], cols[c].key, today)));
    out.push(row.join("\t"));
  }
  return out.join("\n");
}

// Tab-separated text to rows of cells. Handles Excel's quotes (a cell with a new line inside), CRLF, and one trailing new line.
export function parseTSV(text) {
  const src = String(text ?? "").replace(/\r\n?/g, "\n");
  const rows = []; let row = []; let cell = ""; let quoted = false;
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (quoted) {
      if (ch === '"') { if (src[i + 1] === '"') { cell += '"'; i++; } else quoted = false; } else cell += ch;
    } else if (ch === '"' && cell === "") quoted = true;
    else if (ch === "\t") { row.push(cell); cell = ""; } else if (ch === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; } else cell += ch;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

// Sets many cells. `edits` is [[row (in the lines), key, text]]; each is checked on its own and the refused ones are counted.
function applyEdits(lines, edits) {
  let next = lines; let ok = 0; let bad = 0; let first = "";
  for (const [i, key, text] of edits) {
    const got = setField(next, i, key, text);
    if (got.error) { bad += 1; first = first || got.error; } else { next = got.lines; ok += 1; }
  }
  return { lines: next, ok, bad, first };
}

// Pastes rows of cells with the top-left at the selection. A single value fills the whole selection; a block lands as it is, and rows past
// the last line add lines (tasks, next free id). Read-only columns are skipped. Gives { lines, ok, bad, first, added }.
export function pasteCells(lines, rows, cols, sel, matrix) {
  if (!matrix.length) return { lines, ok: 0, bad: 0, first: "", added: [] };
  const { r0, r1, c0, c1 } = rangeOf(sel);
  const writable = (c) => cols[c] && cols[c].type !== "ro";
  let work = lines; const added = []; const edits = []; const index = rows.slice();
  if (matrix.length === 1 && matrix[0].length === 1) {
    for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) if (writable(c)) edits.push([index[r], cols[c].key, matrix[0][0]]);
  } else {
    matrix.forEach((cells, i) => {
      const r = r0 + i;
      while (r >= index.length) {
        const after = index.length ? work[index[index.length - 1]].id : "";
        const made = addLine(work, after, "t");
        work = made.lines; added.push(made.id);
        index.push(made.index);                                  // the new line sits right after the last one drawn
        for (let k = 0; k < index.length - 1; k++) if (index[k] >= made.index) index[k] += 1;
      }
      cells.forEach((text, j) => { if (writable(c0 + j)) edits.push([index[r], cols[c0 + j].key, text]); });
    });
  }
  return { ...applyEdits(work, edits), added };
}

export function clearCells(lines, rows, cols, sel) {
  const { r0, r1, c0, c1 } = rangeOf(sel);
  const edits = [];
  for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) if (cols[c].type !== "ro") edits.push([rows[r], cols[c].key, ""]);
  return applyEdits(lines, edits);
}

// Cmd+D: the top row of the selection into the rows under it, each column on its own.
export function fillDown(lines, rows, cols, sel, today = "") {
  const { r0, r1, c0, c1 } = rangeOf(sel);
  const edits = [];
  for (let c = c0; c <= c1; c++) {
    if (cols[c].type === "ro") continue;
    const v = getValue(lines[rows[r0]], cols[c].key, today);
    for (let r = r0 + 1; r <= r1; r++) edits.push([rows[r], cols[c].key, v]);
  }
  return applyEdits(lines, edits);
}

// Cmd+R: the left column of the selection into the columns to its right, each line on its own.
export function fillRight(lines, rows, cols, sel, today = "") {
  const { r0, r1, c0, c1 } = rangeOf(sel);
  const edits = [];
  for (let r = r0; r <= r1; r++) {
    const v = getValue(lines[rows[r]], cols[c0].key, today);
    for (let c = c0 + 1; c <= c1; c++) if (cols[c].type !== "ro") edits.push([rows[r], cols[c].key, v]);
  }
  return applyEdits(lines, edits);
}

// The fill handle dragged down to row `toRow`: the selected block repeats under itself.
export function fillTo(lines, rows, cols, sel, toRow, today = "") {
  const { r0, r1, c0, c1 } = rangeOf(sel);
  const edits = [];
  for (let r = r1 + 1; r <= Math.min(toRow, rows.length - 1); r++) {
    for (let c = c0; c <= c1; c++) {
      if (cols[c].type === "ro") continue;
      edits.push([rows[r], cols[c].key, getValue(lines[rows[r0 + ((r - r1 - 1) % (r1 - r0 + 1))]], cols[c].key, today)]);
    }
  }
  return applyEdits(lines, edits);
}

// ── undo and redo ──────────────────────────────────────────────────────────────────────────────────────────────────────

export const HISTORY_LIMIT = 100;
export const emptyHistory = () => ({ past: [], future: [] });

// A step is about to be made: remember how things were. A new step ends the redo trail.
export const record = (h, before) => ({ past: [...h.past, before].slice(-HISTORY_LIMIT), future: [] });

// Back one step; `current` is what is on show now. Gives { history, lines } (lines null when there is nothing to undo).
export function undo(h, current) {
  if (!h.past.length) return { history: h, lines: null };
  return { history: { past: h.past.slice(0, -1), future: [...h.future, current] }, lines: h.past[h.past.length - 1] };
}

export function redo(h, current) {
  if (!h.future.length) return { history: h, lines: null };
  return { history: { past: [...h.past, current], future: h.future.slice(0, -1) }, lines: h.future[h.future.length - 1] };
}

// ── widths ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

// The width that fits the longest text in a column (double-click on the edge of its header), between 56 and 420.
export function fitWidth(label, texts, edit) {
  let longest = label.length + (edit ? 4 : 0);
  for (const t of texts) longest = Math.max(longest, String(t).length);
  return clamp(Math.round(longest * 7.2 + 22), 56, 420);
}

export const ZOOM_MIN = 0.5;
export const ZOOM_MAX = 2;
export const clampZoom = (z) => clamp(Math.round(z * 100) / 100, ZOOM_MIN, ZOOM_MAX);
