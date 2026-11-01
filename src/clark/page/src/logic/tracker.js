// The 'Progress tracker' section's rules (#189): pure functions and words, no DOM, no signals, no clock, nothing sent. The section keeps
// its content as text in the section's body (clark/section_bodies.py is the store's own check of the same shape; the page checks first
// so a mistake is said in words before anything is sent, and the store checks again). The shape is
//   { v: 1, overall: { actual, planned, health, note }, columns: { tasks, agents, workflows },
//     groups: [ { name, lines: [ { no, text, start, end, status, weight, planned, achieved, tasks, agents, workflows } ] } ] }
//
// ASSUMPTIONS (the owner has not confirmed the first; the issue is silent on the second, and it reads "a total row sums weight,
// planned and achieved"):
//  1. Every percentage is kept as a whole number of TENTHS of a percent, 0 to 1000 (625 shows as 62.5), so a sum never drifts. A
//     person may type one decimal; if the owner decides on whole numbers only, only `pct` below changes.
//  2. A line's `planned` and `achieved` are SHARES OF THE WHOLE, like its `weight`: the part of the whole tracker that line should
//     have delivered by now and the part it has. So a group's total is the plain sum of its lines, the overall is the plain sum of
//     the group totals, and "points behind plan" is planned minus achieved when that is above zero. (They are not each line's own
//     percent complete: that would need a weighting by `weight`, which nothing in the issue asks for.)
//  3. The overall is worked out from the lines whenever there are any; the figures typed in `overall` count only while there are no
//     lines at all (the "just the bar" case), so the overall can never disagree with the lines under it.
// Totals are never stored: this file works them out every time.
import { dayNumber, showDate } from "../workItems.js";

export const MAX_GROUPS = 10;
export const MAX_LINES = 47;                   // in all (the store's own cap: clark/section_bodies.py TRACKER_MAX_LINES)
export const NAME_MAX = 80;
export const TEXT_MAX = 100;
export const NO_MAX = 10;
export const NOTE_MAX = 100;
export const COUNT_MAX = 99999;
export const WHOLE = 1000;                     // the whole, in tenths of a percent
export const YEARS = [2000, 2100];
export const STATUSES = [["planned", "Planned"], ["inprogress", "In progress"], ["completed", "Completed"], ["late", "Late"]];
export const HEALTH = [["ontrack", "On track"], ["atrisk", "At risk"], ["offtrack", "Off track"]];
export const COLUMNS = [["tasks", "Tasks"], ["agents", "Agents"], ["workflows", "Workflows"]];
export const statusWord = (s) => (STATUSES.find((x) => x[0] === s) || ["", ""])[1];
export const healthWord = (h) => (HEALTH.find((x) => x[0] === h) || ["", ""])[1];

// Every word the section shows or says. A test reads each one: no jargon, and no sentence that starts with the product name.
export const WORDS = {
  title: "Progress tracker",
  actual: "Actual",
  planned: "Planned",
  achieved: "Achieved",
  weight: "Weight",
  no: "No.",
  what: "Description",
  start: "Start",
  end: "End",
  status: "Status",
  health: "Health",
  note: "A line about it",
  group: "Group name",
  total: "Total",
  noLines: "No lines yet",
  none: "Nothing is being tracked yet.",
  behindLabel: "behind plan",
  addLine: "Add a line",
  addGroup: "Add a group",
  add: "Add",
  save: "Save",
  cancel: "Cancel",
  edit: "Edit",
  remove: "Remove",
  up: "Move up",
  down: "Move down",
  rename: "Rename",
  removeGroup: "Remove group",
  overall: "Overall",
  columns: "Show these columns",
  datePlaceholder: "DD-MM-YYYY",
  percentPlaceholder: "0 to 100",
  noHealth: "Not set",
  added: "Line added.",
  saved: "Saved.",
  removed: "Line removed.",
  moved: "Moved.",
  groupAdded: "Group added.",
  groupRemoved: "Group removed.",
  fullLines: `A tracker can have ${MAX_LINES} lines in all. Remove one to add another.`,
  fullGroups: `A tracker can have ${MAX_GROUPS} groups at most. Remove one to add another.`,
  problems: {
    text: "Describe each line.",
    textLong: `A line description can be ${TEXT_MAX} characters at most.`,
    noLong: `A line number can be ${NO_MAX} characters at most.`,
    percent: "A percentage must be a number from 0 to 100.",
    date: `A date must be a real day written DD-MM-YYYY, between ${YEARS[0]} and ${YEARS[1]}, or empty.`,
    order: "A line can't end before it starts.",
    status: "Choose Planned, In progress, Completed or Late.",
    count: `A count must be a whole number from 0 to ${COUNT_MAX}, or empty.`,
    name: "Give each group a name.",
    nameLong: `A group name can be ${NAME_MAX} characters at most.`,
    total: "The lines' weight, planned and achieved figures can each add up to 100% at most.",
    noteLong: `The note can be ${NOTE_MAX} characters at most.`,
  },
};
export const ALL_WORDS = () => {
  const out = [];
  const walk = (o) => { for (const v of Object.values(o)) { if (typeof v === "string") out.push(v); else walk(v); } };
  walk(WORDS);
  for (const [, w] of [...STATUSES, ...HEALTH, ...COLUMNS]) out.push(w);
  return out;
};

// ── Percentages ─────────────────────────────────────────────────────────────────────────────────────────────────────────

// Tenths of a percent as a person reads them: 625 is "62.5", 940 is "94", 5 is "0.5".
export const fmt = (t) => `${Math.floor(t / 10)}${t % 10 ? `.${t % 10}` : ""}`;

// What was typed ("62", "62.5", "62%", "62,5") as whole tenths, or null when it is not a number from 0 to 100 with at most one decimal.
export function pct(text) {
  const t = String(text == null ? "" : text).trim().replace(/%$/, "").trim().replace(",", ".");
  if (!/^\d{1,3}(\.\d)?$/.test(t)) return null;
  const n = Math.round(parseFloat(t) * 10);
  return n >= 0 && n <= WHOLE ? n : null;
}

// "1 point behind plan", "2.5 points behind plan"; "" when nothing is behind. `behind` is in tenths.
export const behindWords = (behind) => (behind > 0 ? `${fmt(behind)} point${behind === 10 ? "" : "s"} ${WORDS.behindLabel}` : "");

// ── Reading ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

export const isoOf = (text) => {
  const t = String(text == null ? "" : text).trim();
  if (!t) return "";
  const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(t);
  const iso = m ? `${m[3]}-${m[2]}-${m[1]}` : /^\d{4}-\d{2}-\d{2}$/.test(t) ? t : "";
  if (dayNumber(iso) === null) return null;
  const y = +iso.slice(0, 4);
  return y >= YEARS[0] && y <= YEARS[1] ? iso : null;
};

const tenths = (v) => (Number.isInteger(v) && v >= 0 && v <= WHOLE ? v : 0);
const count = (v) => (Number.isInteger(v) && v >= 0 && v <= COUNT_MAX ? v : null);
const str = (v) => (typeof v === "string" ? v : "");

// The tracker a section holds, as one shape. `fromFile`: the file's own copy (the published section's entry itself, which carries
// the shown groups and lines only, dates as DD-MM-YYYY). Otherwise the stored body, which is text; text that can't be read is an empty
// tracker. Never throws, and never trusts a field it does not name.
export function trackerOf(section, fromFile) {
  let v = {};
  if (fromFile) v = section && typeof section === "object" ? section : {};     // the published entry carries overall, columns and groups beside its id and title
  else {
    try { v = JSON.parse(section && typeof section.body === "string" && section.body ? section.body : "{}"); } catch (e) { v = {}; }
  }
  if (!v || typeof v !== "object" || Array.isArray(v)) v = {};
  const o = v.overall && typeof v.overall === "object" ? v.overall : {};
  const c = v.columns && typeof v.columns === "object" ? v.columns : {};
  const groups = [];
  for (const g of Array.isArray(v.groups) ? v.groups : []) {
    if (!g || typeof g !== "object" || typeof g.name !== "string") continue;
    const lines = [];
    for (const l of Array.isArray(g.lines) ? g.lines : []) {
      if (!l || typeof l !== "object" || typeof l.text !== "string") continue;
      const start = isoOf(l.start), end = isoOf(l.end);
      lines.push({ no: str(l.no), text: l.text, start: start || "", end: end || "", status: STATUSES.some((s) => s[0] === l.status) ? l.status : "planned",
        weight: tenths(l.weight), planned: tenths(l.planned), achieved: tenths(l.achieved),
        tasks: count(l.tasks), agents: count(l.agents), workflows: count(l.workflows) });
    }
    groups.push({ name: g.name, lines });
  }
  return {
    overall: { actual: o.actual == null ? null : tenths(o.actual), planned: o.planned == null ? null : tenths(o.planned),
      health: HEALTH.some((h) => h[0] === o.health) ? o.health : "", note: str(o.note) },
    columns: { tasks: c.tasks === true, agents: c.agents === true, workflows: c.workflows === true },
    groups,
  };
}

// ── Totals ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

const sum = (list, k) => list.reduce((n, x) => n + x[k], 0);
export const behindOf = (line) => Math.max(0, line.planned - line.achieved);

// The figures the section shows, all in tenths. `groups[i]` is { name, weight, planned, achieved, behind, none } (`none`: no lines, so
// 0 everywhere and the words "No lines yet"), each with `lines[j].behind`. `overall` is { actual, planned, behind, health, note, fromLines }
// (actual and planned are null only when there are no lines and none were typed). `weights` is the sum of every weight, and
// `weightsNote` says so ("Weights add up to 94%") only when there are lines and the sum is not the whole.
export function totals(tracker) {
  const groups = tracker.groups.map((g) => {
    const planned = sum(g.lines, "planned"), achieved = sum(g.lines, "achieved");
    return { name: g.name, none: g.lines.length === 0, weight: sum(g.lines, "weight"), planned, achieved, behind: Math.max(0, planned - achieved),
      lines: g.lines.map((l) => ({ ...l, behind: behindOf(l) })) };
  });
  const lines = groups.reduce((n, g) => n + g.lines.length, 0);
  const o = tracker.overall;
  const fromLines = lines > 0;
  const actual = fromLines ? sum(groups, "achieved") : o.actual;
  const planned = fromLines ? sum(groups, "planned") : o.planned;
  const behind = actual !== null && planned !== null ? Math.max(0, planned - actual) : 0;
  const weights = sum(groups, "weight");
  return { groups, lines, weights, weightsNote: fromLines && weights !== WHOLE ? `Weights add up to ${fmt(weights)}%` : "",
    overall: { actual, planned, behind, behindWords: behindWords(behind), health: o.health, note: o.note, fromLines } };
}

// How much of the bar to fill: the figure, never past the whole. null (nothing typed) draws an empty bar.
export const fill = (t) => (t === null ? 0 : Math.min(WHOLE, Math.max(0, t)));

// ── Checking a line before anything is sent ─────────────────────────────────────────────────────────────────────────────

const chars = (s) => Array.from(s).length;
const countOf = (text) => {
  const t = String(text == null ? "" : text).trim();
  if (!t) return null;
  return /^\d{1,5}$/.test(t) && +t <= COUNT_MAX ? +t : undefined;
};

// A typed line ({ no, text, start, end, status, weight, planned, achieved, tasks, agents, workflows }, every value as typed) as a
// plain sentence, the store's own words, or "" when it can be saved.
export function problem(draft) {
  const P = WORDS.problems;
  const text = String(draft.text == null ? "" : draft.text).trim();
  if (!text) return P.text;
  if (chars(text) > TEXT_MAX) return P.textLong;
  if (chars(String(draft.no == null ? "" : draft.no).trim()) > NO_MAX) return P.noLong;
  if (!STATUSES.some((s) => s[0] === draft.status)) return P.status;
  const start = isoOf(draft.start), end = isoOf(draft.end);
  if (start === null || end === null) return P.date;
  if (start && end && end < start) return P.order;
  for (const k of ["weight", "planned", "achieved"]) {
    const t = String(draft[k] == null ? "" : draft[k]).trim();
    if (t !== "" && pct(t) === null) return P.percent;
  }
  for (const k of ["tasks", "agents", "workflows"]) if (countOf(draft[k]) === undefined) return P.count;
  return "";
}

// A typed line as it is saved (an empty percentage is 0, an empty count is none).
export function made(draft) {
  const p = (k) => pct(draft[k]) || 0;
  return { no: String(draft.no == null ? "" : draft.no).trim(), text: String(draft.text).trim(), start: isoOf(draft.start) || "", end: isoOf(draft.end) || "",
    status: draft.status, weight: p("weight"), planned: p("planned"), achieved: p("achieved"),
    tasks: countOf(draft.tasks) ?? null, agents: countOf(draft.agents) ?? null, workflows: countOf(draft.workflows) ?? null };
}

// A saved line as the form shows it.
export const draftOf = (l) => ({ no: l.no, text: l.text, start: l.start ? showDate(l.start) : "", end: l.end ? showDate(l.end) : "", status: l.status,
  weight: fmt(l.weight), planned: fmt(l.planned), achieved: fmt(l.achieved),
  tasks: l.tasks === null ? "" : String(l.tasks), agents: l.agents === null ? "" : String(l.agents), workflows: l.workflows === null ? "" : String(l.workflows) });

export const blankLine = () => ({ no: "", text: "", start: "", end: "", status: "planned", weight: "", planned: "", achieved: "", tasks: "", agents: "", workflows: "" });

// Problems with a group's name or the overall's typed words, as a sentence or "".
export function nameProblem(name) {
  const t = String(name == null ? "" : name).trim();
  return !t ? WORDS.problems.name : chars(t) > NAME_MAX ? WORDS.problems.nameLong : "";
}
export const noteProblem = (note) => (chars(String(note == null ? "" : note).trim()) > NOTE_MAX ? WORDS.problems.noteLong : "");

// ── The body, and the list after one change ─────────────────────────────────────────────────────────────────────────────

// The body text for a tracker: what the one change sends.
export const bodyOf = (t) => JSON.stringify({ v: 1, overall: t.overall, columns: t.columns, groups: t.groups });

const total = (t) => t.groups.reduce((n, g) => n + g.lines.length, 0);
const inRange = (list, i) => Number.isInteger(i) && i >= 0 && i < list.length;
const swap = (list, i, j) => { const out = list.slice(); [out[i], out[j]] = [out[j], out[i]]; return out; };
const inGroup = (t, g, f) => (inRange(t.groups, g) ? { ...t, groups: t.groups.map((x, k) => (k === g ? { ...x, lines: f(x.lines) } : x)) } : null);

// Each returns the new tracker, or null when it can't be done (no such group or line, or a limit is reached).
export const withLineAdded = (t, g, line) => (total(t) >= MAX_LINES ? null : inGroup(t, g, (ls) => [...ls, line]));
export const withLineReplaced = (t, g, i, line) => (inRange(t.groups, g) && inRange(t.groups[g].lines, i) ? inGroup(t, g, (ls) => ls.map((l, k) => (k === i ? line : l))) : null);
export const withoutLine = (t, g, i) => (inRange(t.groups, g) && inRange(t.groups[g].lines, i) ? inGroup(t, g, (ls) => ls.filter((_, k) => k !== i)) : null);
export const withLineMoved = (t, g, i, by) => (inRange(t.groups, g) && inRange(t.groups[g].lines, i) && inRange(t.groups[g].lines, i + by) ? inGroup(t, g, (ls) => swap(ls, i, i + by)) : null);
export const withGroupAdded = (t, name) => (t.groups.length >= MAX_GROUPS ? null : { ...t, groups: [...t.groups, { name, lines: [] }] });
export const withGroupRenamed = (t, g, name) => (inRange(t.groups, g) ? { ...t, groups: t.groups.map((x, k) => (k === g ? { ...x, name } : x)) } : null);
export const withoutGroup = (t, g) => (inRange(t.groups, g) ? { ...t, groups: t.groups.filter((_, k) => k !== g) } : null);
export const withGroupMoved = (t, g, by) => (inRange(t.groups, g) && inRange(t.groups, g + by) ? { ...t, groups: swap(t.groups, g, g + by) } : null);
export const withOverall = (t, overall) => ({ ...t, overall: { ...t.overall, ...overall } });
export const withColumn = (t, name, on) => ({ ...t, columns: { ...t.columns, [name]: !!on } });

// "" when no column of figures (weight, planned, achieved) adds up to more than the whole across the tracker, else the store's sentence.
export function totalProblem(tracker) {
  const all = tracker.groups.flatMap((g) => g.lines);
  return ["weight", "planned", "achieved"].some((k) => all.reduce((n, l) => n + l[k], 0) > WHOLE) ? WORDS.problems.total : "";
}
