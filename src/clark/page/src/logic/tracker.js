// The 'Progress tracker' section's rules (#189): pure functions and words, no DOM, no signals, no clock, nothing sent. The section keeps
// its content as text in the section's body (clark/section_bodies.py is the store's own check of the same shape; the page checks first
// so a mistake is said in words before anything is sent, and the store checks again). The shape is
//   { v: 1, size?, overall: { actual, planned, health, note }, columns: { tasks, agents, workflows },
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
export const SIZES = ["large", "medium", "small", "compact"];       // the tracker's size (#930); a body without one reads as Medium
export const DEFAULT_SIZE = "medium";
export const COLUMNS = [["tasks", "Tasks"], ["agents", "Agents"], ["workflows", "Workflows"]];
export const statusWord = (s) => (STATUSES.find((x) => x[0] === s) || ["", ""])[1];
export const healthWord = (h) => (HEALTH.find((x) => x[0] === h) || ["", ""])[1];

// The words a reader's page shows (View and the published file). The author's words (buttons, placeholders, notes, the sentences that
// say what is wrong) are in logic/trackerEdit.js, which only Edit imports, so none of them is in the published file (#451). A test reads
// each word: no jargon, and no sentence that starts with the product name.
export const WORDS = {
  title: "Progress tracker",
  actual: "Achieved",
  scaleStart: "0%",
  scaleEnd: "100%",
  planned: "Planned",
  achieved: "Achieved",
  weight: "Weight",
  no: "Number",
  what: "Description",
  start: "Start",
  end: "End",
  status: "Status",
  total: "Total",
  noLines: "No lines yet",
  none: "Nothing is being tracked yet.",
  behindLabel: "behind plan",
  aheadLabel: "ahead of plan",
  onPlan: "On plan.",
};
export const ALL_WORDS = () => {
  const out = Object.values(WORDS);
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

// The words under the chip when the owner has written none, from the gap in tenths (planned minus achieved; negative is ahead):
// "2.5 points behind plan.", "1 point ahead of plan.", "On plan.". "" when there is no figure to compare.
export function autoWords(actual, planned) {
  if (actual === null || planned === null) return "";
  const gap = planned - actual;
  if (gap > 0) return `${behindWords(gap)}.`;
  if (gap < 0) return `${fmt(-gap)} point${gap === -10 ? "" : "s"} ${WORDS.aheadLabel}.`;
  return WORDS.onPlan;
}

// The health the rule gives, from the gap in tenths: On track up to 2 points behind (ahead counts as On track), At risk up to 9.9
// behind, Off track from 10. "" when there is no figure.
export const RULE = { ontrack: 20, atrisk: 99 };            // the most tenths behind each still allows
export function healthRule(actual, planned) {
  if (actual === null || planned === null) return "";
  const behind = planned - actual;
  return behind <= RULE.ontrack ? "ontrack" : behind <= RULE.atrisk ? "atrisk" : "offtrack";
}

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
    size: SIZES.includes(v.size) ? v.size : DEFAULT_SIZE,
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
// (actual and planned are null only when there are no lines and none were typed). `weights` is the sum of every weight (the author's
// note about it is logic/trackerNote.js, Edit only).
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
  return { groups, lines, weights,
    overall: { actual, planned, behind, behindWords: behindWords(behind), health: o.health, note: o.note, fromLines,
      shownHealth: o.health || healthRule(actual, planned), auto: autoWords(actual, planned) } };
}

// The Achieved bar of one line: its achieved share of its own weight, as a whole percent from 0 to 100. A line with no weight is empty
// until something is achieved, then full (it has done all it was asked to).
export const lineFill = (l) => (l.weight > 0 ? Math.min(100, Math.round((100 * l.achieved) / l.weight)) : l.achieved > 0 ? 100 : 0);

// Where the "Planned" label sits on the bar: its left edge at the mark near the start, its right edge near the end, centred between,
// so the label never runs off the bar. "start", "end" or "".
export const markEdge = (planned) => (planned <= WHOLE / 10 ? "start" : planned >= (WHOLE * 9) / 10 ? "end" : "");

// How much of the bar to fill: the figure, never past the whole. null (nothing typed) draws an empty bar.
export const fill = (t) => (t === null ? 0 : Math.min(WHOLE, Math.max(0, t)));

// A saved line as the form shows it.
export const draftOf = (l) => ({ no: l.no, text: l.text, start: l.start ? showDate(l.start) : "", end: l.end ? showDate(l.end) : "", status: l.status,
  weight: fmt(l.weight), planned: fmt(l.planned), achieved: fmt(l.achieved),
  tasks: l.tasks === null ? "" : String(l.tasks), agents: l.agents === null ? "" : String(l.agents), workflows: l.workflows === null ? "" : String(l.workflows) });

export const blankLine = () => ({ no: "", text: "", start: "", end: "", status: "planned", weight: "", planned: "", achieved: "", tasks: "", agents: "", workflows: "" });

// ── The body, and the list after one change ─────────────────────────────────────────────────────────────────────────────

// The body text for a tracker: what the one change sends.
// A Medium size is left out (an old body has none), so an older clark build still reads a body that never chose a size.
export const bodyOf = (t) => JSON.stringify({ v: 1, ...(t.size && t.size !== DEFAULT_SIZE ? { size: t.size } : {}), overall: t.overall, columns: t.columns, groups: t.groups });

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
export const withSize = (t, size) => (SIZES.includes(size) ? { ...t, size } : null);
export const withColumn = (t, name, on) => ({ ...t, columns: { ...t.columns, [name]: !!on } });
