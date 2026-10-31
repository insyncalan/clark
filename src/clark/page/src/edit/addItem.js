// The Add menu on Work items (gap list B-8): Add action, risk, issue or decision makes the item at once, as the prototype does
// (views.js newItem), opens it in the item panel and says "<ID> added" with Undo. Edit code only: the published file has no Add
// (#204) and no route to call. The request is kind actions, raid or decisions, op new (clark/changes.py _do_new_row): clark gives
// the id, the project, the day it was raised, its status, its source and its owner (TBC); the page sends only a working title, a
// due date (a week from today; a decision is needed today, as the prototype has it) and an action's priority. Whether the item is
// shown to the client is the store's default (every work item is client-visible by default, D-3); the eye hides it.
// View is read only, so a pick made in View turns the page to Edit first: the new item is open to be edited, and the toast with its
// Undo is an Edit part.
import { newItem } from "../stores/changes.js";
import { openPeek, mode } from "../stores/report.js";
import { todayIso, dayNumber } from "../workItems.js";

const DAY = 86400000;
export const ADDABLE = ["action", "risk", "issue", "decision"];
const TITLE = { action: "New action", risk: "New risk", issue: "New issue", decision: "New decision" };

/** `iso` (YYYY-MM-DD) moved on by `days`, as YYYY-MM-DD; null for anything that isn't a real day. */
export function addDays(iso, days) {
  const n = dayNumber(iso);
  if (n === null) return null;
  return new Date(n * DAY + days * DAY).toISOString().slice(0, 10);
}

/** The request that adds one item of `kind` (action, risk, issue, decision), or null for any other kind. `today` is YYYY-MM-DD;
 *  `place` is where it was asked for (the menu, or the board). */
export function newItemRequest(kind, today, place = "menu") {
  if (!ADDABLE.includes(kind)) return null;
  const due = addDays(today, 7);
  if (kind === "decision") return { kind: "decisions", op: "new", values: { decision: TITLE.decision, needed_by: today }, place };
  if (kind === "action") return { kind: "actions", op: "new", values: { description: TITLE.action, due_date: due, priority: "Medium" }, place };
  return { kind: "raid", op: "new", values: { type: kind === "risk" ? "Risk" : "Issue", description: TITLE[kind], due_date: due }, place };
}

/** Add one item and open it. Resolves to the new id, or null when nothing was added (the toast says why). */
export async function addItem(kind, place = "menu") {
  const req = newItemRequest(kind, todayIso(), place);
  if (!req) return null;
  if (mode.value !== "edit") mode.value = "edit";
  const reply = await newItem(req);
  if (!reply || typeof reply.ref !== "string") return null;
  openPeek(reply.ref, "item");
  return reply.ref;
}
