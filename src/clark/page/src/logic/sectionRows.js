// The rows of the Risks and issues, Open actions and Decisions sections (prototype parity A-D5): plain functions, no DOM, no clock.
// They read only the rows the page already holds (data from /api/data, or a published file's own block, where the build has
// already dropped every row a client may not read). `today` is passed in: the publish date in a file, the clock on the page clark serves.
import { isOpen, dayNumber, sortRows, pillOf, dueField } from "../workItems.js";
import { rulesFor, keptRows } from "./publishable.js";

export const KINDS = { raid: ["risk", "issue"], actions: ["action"], decisions: ["decision"] };
const RECENT = 14;                                                             // a decision made in the last 14 days is still shown

// Is this row one that its section lists? Open ones only, and a decision that was made lately.
export function listed(type, row, today) {
  if (!KINDS[type] || !KINDS[type].includes(row.kind)) return false;
  if (row.kind !== "decision") return isOpen(row);
  if (row.status === "Pending") return true;
  const a = dayNumber(row.date), b = dayNumber(today);
  return row.status === "Made" && a !== null && b !== null && b - a <= RECENT && b - a >= 0;
}

// A published file holds only rows the client may read; the page clark serves holds all of them and marks each one.
export function visible(row, fromFile) { return fromFile || row.client; }

// The section's rows in order: soonest date first, then by ID.
export function sectionRows(type, rows, today, fromFile) {
  return sortRows(rows.filter((r) => visible(r, fromFile) && listed(type, r, today)), today);
}

// The word before a row's date: "Due" on an action, "Review by" on a risk or issue, and on a decision "Needed by" or "Decided".
export function dateWord(row) {
  if (row.kind === "decision") return row.status === "Pending" ? "Needed by" : "Decided";
  return row.kind === "action" ? "Due" : "Review by";
}

// The status pill on a row, as the prototype draws it (core.js C.look): a risk or issue reads Red, Amber or Green (its priority's
// colour), an action Overdue, Delayed, Due soon or Open, a decision Pending, Made or Withdrawn; a closed one reads its status.
// The same words as the Work items list (workItems.pillOf), so a row says one thing wherever it is read.
// Row 1021: on the report's rows an action that is neither late, delayed nor due soon reads "On track" (green), the word the icon says;
// the Work items list keeps "Open" (workItems.pillOf is not changed).
// Row 1021, option B: an open action, risk or issue whose own status is not plain (Blocked, In progress, ...) keeps that word, in its colour
// (amber, green, blue, else grey); Delayed and the closed statuses read as pillOf reads them.
export const PLAIN_STATUS = [null, undefined, "", "Open", "Planned"];
export const OWN_STATUS_CLASS = { Blocked: "a", "In progress": "g", Completed: "b" };
export function clientPill(row, today) {
  const s = row.status;
  if (["action", "risk", "issue"].includes(row.kind) && typeof s === "string" && !PLAIN_STATUS.includes(s) && !["Closed", "Cancelled", "Made", "Withdrawn", "Delayed"].includes(s)) {
    return { text: s, class: OWN_STATUS_CLASS[s] || "n" };
  }
  const p = pillOf(row, today);
  return row.kind === "action" && p.text === "Open" ? { text: "On track", class: "g" } : p;
}

// "3 d late" for an open action whose date has passed; nothing otherwise (a decision, a risk, an action not late).
export function lateWord(row, today) {
  if (row.kind !== "action" || !isOpen(row) || row.status === "Completed") return "";
  const a = dayNumber(dueField(row)), b = dayNumber(today);
  return a !== null && b !== null && a < b ? `${b - a} d late` : "";
}

// The ids the report leaves out (taken off with the eye), from the page's data: the page clark serves holds the list, a published
// file holds none (the build has already dropped those rows).
export function hiddenIds(data) {
  return ((data && data.report_hidden) || []).map((h) => (h && h.item_id) || h);
}

// The rows of a kind that the report would publish, by id, from the page's data: what publish keeps (logic/publishable.js), so what
// View and Edit draw is what the client reads. The report's own section visibility is left out of it: this section is one of them.
export function keptIds(data) {
  const rules = rulesFor({ code: data && data.project && data.project.code, hidden: hiddenIds(data), labelRules: data && data.label_rules, labels: data && data.labels, sections: [] });
  return new Set(["actions", "raid", "decisions"].flatMap((k) => keptRows(data, k, rules).map((r) => r.id)));
}
