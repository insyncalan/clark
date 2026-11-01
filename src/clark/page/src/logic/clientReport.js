// Client Requested Report View (#192): the figures for Overall progress and Progress by plan, worked out from the milestones the
// project already has. Plain functions, no DOM, no signals and no clock (the status date is passed in).
//
// THE BOUNDARY: components/clientreport/Overall.jsx and Plans.jsx draw only what `progress()` returns, so the Progress tracker
// (#189, typed weight, planned and achieved) can replace those two files by returning the same shape:
//   { overall: { actual, planned } | null, groups: [{ name, lines: [Line], total: { actual, planned } }] }
//   Line = { id, no, text, end (YYYY-MM-DD or null), word, colour, mark, planned, achieved (0 to 100 or null), behind (0 to 100) }
//
// WHAT EACH NUMBER MEANS (said on the page too):
//   A line is a milestone, and every line counts the same (clark has no weight on a milestone).
//   Achieved: 100 when the milestone is Done, else its percent complete; "Not set" (null) when none was typed.
//   Planned: 100 when its agreed date is on or before the status date, else 0; null when it has no agreed date.
//   Overall Actual: the average of Achieved over every line (a missing percent counts as 0). Overall Planned: the average of Planned
//   over every line (no agreed date counts as 0). A group's total is the same average over its own lines.
//   Behind: Planned minus Achieved, when Achieved is lower (a missing Achieved counts as 0).
import { milestoneRows, CANCELLED } from "./milestones.js";
import { rulesFor, publishable } from "./publishable.js";

/** The client's rules for this project (main's gate, logic/publishable.js, the page's mirror of publish.select): a row this view
 *  draws or counts must be one the published file would hold, so a hidden row never shows and never moves a figure. In a published
 *  file (`isFile`) there are no rules: the file's rows are already the kept ones, so null is given and progress() and riskRows() keep all. */
export function clientRules(data, isFile) {
  if (isFile) return null;      // a published file holds only the rows that passed the gate, and carries none of the fields it reads: no rules, nothing left out twice
  const d = data || {};
  return rulesFor({ code: d.project && d.project.code, hidden: (d.report_hidden || []).map((h) => (h && h.item_id) || h),
    labelRules: d.label_rules, labels: d.labels, sections: d.report_sections });
}

export const OTHER = "Other milestones";
export const ONLY = "Milestones";

const avg = (xs) => (xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : null);

/** One line from a milestone row (logic/milestones.js milestoneRows) and the status date. */
export function line(r, on, no) {
  const achieved = r.status === "Done" ? 100 : r.percent === null || r.percent === undefined ? null : r.percent;
  const planned = r.baseline ? (r.baseline <= on ? 100 : 0) : null;
  const behind = planned !== null && planned > (achieved || 0) ? planned - (achieved || 0) : 0;
  return { id: r.id, no, text: r.name, end: r.achieved || r.forecast || r.baseline || null, word: r.word, colour: r.colour, mark: r.mark, planned, achieved, behind };
}

/** The sums of some lines: { actual, planned } as whole percents, or null for no lines. */
export function total(lines) {
  if (!lines.length) return null;
  return { actual: avg(lines.map((l) => l.achieved || 0)), planned: avg(lines.map((l) => l.planned || 0)) };
}

/** {overall, groups} for the milestones `list` (data.milestones) as at `on`, in the client's words when `client` is true. Only the
 *  milestones `rules` (clientRules) would publish are used: archived, not for the client, report-hidden, Sensitive or excluded by a
 *  label, or in a hidden Milestones section are left out, as are cancelled ones. With no `rules` nothing is left out by them. Groups are the milestones' workstreams, in the order their first line falls by date; one with no
 *  workstream is in "Other milestones" (or "Milestones" when no milestone has a workstream). */
export function progress(list, on, client, rules) {
  const kept = rules ? (list || []).filter((m) => publishable(m, "milestones", rules)) : list;
  const rows = milestoneRows(kept, on, client).filter((r) => r.status !== CANCELLED && r.state !== CANCELLED);
  const ws = Object.fromEntries((list || []).map((m) => [m.id, typeof m.workstream === "string" ? m.workstream.trim() : ""]));
  const named = rows.some((r) => ws[r.id]);
  const order = [], by = {};
  for (const r of rows) {
    const name = ws[r.id] || (named ? OTHER : ONLY);
    if (!by[name]) { by[name] = []; order.push(name); }
    by[name].push(r);
  }
  const groups = order.map((name) => {
    const lines = by[name].map((r, i) => line(r, on, i + 1));
    return { name, lines, total: total(lines) };
  });
  return { overall: total(groups.flatMap((g) => g.lines)), groups };
}

/** The words under the figures: "1 point behind plan", "2 points ahead of plan" or "On plan"; "" when either figure is missing. */
export function gapWords(overall) {
  if (!overall) return "";
  const d = overall.planned - overall.actual;
  const n = Math.abs(d);
  return d === 0 ? "On plan" : `${n} ${n === 1 ? "point" : "points"} ${d > 0 ? "behind" : "ahead of"} plan`;
}

/** What a line's behind-plan mark says out loud (for a screen reader; the mark itself is "▼n"). */
export const behindWords = (n) => `${n} ${n === 1 ? "point" : "points"} behind plan`;

/** The text section the words come from: the first shown text section whose title matches. Not by position, because a section can
 *  be moved. A section the owner hid, or left out of the client's report (report_hidden), is never used. */
export function sectionFor(sections, pattern, hidden) {
  const out = new Set(((hidden || [])).map((h) => (h && h.item_id) || h));
  return (sections || []).find((s) => s.type === "text" && !(s.hidden === 1 || s.hidden === true) && !out.has(s.id) && pattern.test(String(s.title || ""))) || null;
}
