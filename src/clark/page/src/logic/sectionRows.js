// The rows of the Risks and issues, Open actions and Decisions sections (prototype parity A-D5): plain functions, no DOM, no clock.
// They read only the rows the page already holds (data from /api/data, or a published file's own block, where the build has
// already dropped every row a client may not read). `today` is passed in: the publish date in a file, the clock on the page clark serves.
import { isOpen, dayNumber, sortRows, pillOf, colourOf } from "../workItems.js";

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

// The pill a client reads on a row, in the client's words: "Late" on an action past its date (the help note says the published
// page reads Overdue as Late), the priority word on a risk or issue (as the row carries it: Urgent, High, Medium or Low) and no
// pill at all when it has none.
export function clientPill(row, today) {
  if (row.kind === "risk" || row.kind === "issue") {
    const c = colourOf(row.priority);
    return c.colour ? { text: row.priority, class: c.class } : null;
  }
  const pill = pillOf(row, today);
  return pill.text === "Overdue" ? { ...pill, text: "Late" } : pill;
}
