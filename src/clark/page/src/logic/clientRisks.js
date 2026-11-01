// Client Requested Report View (#192): the "Risks, delays and items to watch" rows, worked out from the Risks and issues rows the
// project already has. Pure functions, no DOM and no clock, so a test can run them alone. Nothing here is saved: there is no
// field for "Escalate" or "Back on track by" (a typed version needs a guarded change; see the note in the pull request), so each
// is worked out from what a row already says, or shown as a dash.
import { dayNumber, isOpen, colourOf } from "../workItems.js";
import { publishable } from "./publishable.js";

export const DELAY = "Delay", RISK = "Risk", MONITOR = "Monitor";
const RANK = { [DELAY]: 0, [RISK]: 1, [MONITOR]: 2 };
const TONE = { [DELAY]: "r", [RISK]: "a", [MONITOR]: "n" };       // the pill colours of the Work items page: red, amber, grey

/** The word for a row. An issue is a Delay. A risk that is High or Urgent is a Risk. Any other risk (Medium, Low, or not rated) is
 *  something to Monitor. Assumptions and dependencies are not on this page (null). */
export function wordOf(row) {
  const kind = String(row.type || row.kind || "").toLowerCase();
  if (kind === "issue") return DELAY;
  if (kind !== "risk") return null;
  return row.priority === "High" || row.priority === "Urgent" ? RISK : MONITOR;
}

export const toneOf = (word) => TONE[word] || "n";

/** "Yes" for a row whose priority is Urgent or whose colour is Red (a High or Urgent priority: a RAID row's colour is its priority);
 *  otherwise no answer (null), shown as a dash. Never a No: nothing in the data says that nobody should be told. */
export function escalateOf(row) {
  return row.priority === "Urgent" || colourOf(row.priority).colour === "red" ? "Yes" : null;
}

/** The date a row should be back on track: its due date when that is a real day, otherwise null (a dash). */
export function backOnTrack(row) {
  return dayNumber(row.due_date) === null ? null : row.due_date;
}

/** The words the client reads for a row: its client message when there is one, else its description. The response (a working
 *  note, never published) is never used. */
export function titleOf(row) {
  const m = typeof row.client_message === "string" ? row.client_message.trim() : "";
  return m || row.description;
}

/** The rows the page shows: open risks and issues the published file would hold (`rules`, clientReport.clientRules: not archived,
 *  for the client, not report-hidden, no Sensitive or excluding label, Risks section shown), Delays first, then Risks, then Monitor;
 *  inside a word by date (no date last), then by id. With no `rules` only archived and not-for-the-client rows are left out. */
export function riskRows(raid, rules) {
  const out = [];
  for (const r of raid || []) {
    const word = wordOf(r);
    if (!word || !isOpen(r) || Number(r.archived) === 1 || Number(r.client_visible) === 0 || (rules && !publishable(r, "raid", rules))) continue;
    out.push({ id: r.id, word, tone: TONE[word], title: titleOf(r), owner: r.owner, due: backOnTrack(r), escalate: escalateOf(r) });
  }
  return out.sort((x, y) => RANK[x.word] - RANK[y.word] || (x.due === y.due ? 0 : x.due === null ? 1 : y.due === null ? -1 : x.due < y.due ? -1 : 1) || (x.id < y.id ? -1 : x.id > y.id ? 1 : 0));
}
