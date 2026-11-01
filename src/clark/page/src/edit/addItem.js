// The Add menu on Work items (gap list B-8): Add action, risk, issue or decision makes the item at once, as the prototype does
// (views.js newItem), opens it in the item panel and says "<ID> added." with Undo. Edit code only: the published file has no Add
// (#204) and no route to call. The request is kind actions, raid or decisions, op new (clark/changes.py _do_new_row): clark gives
// the id, the project, the day it was raised, its status, its source and its owner (TBC); the page sends only a working title, a
// due date (a week from today; a decision is needed today, as the prototype has it), an action's or a risk's workstream (the one
// filtered on, else the first active one, as the prototype has it) and an action's priority. Whether the item is
// shown to the client is the store's default (every work item is client-visible by default, D-3); the eye hides it.
// #449: the prototype adds in View, so a pick made in View stays in View: the item is made, the toast with its Undo is drawn in View
// too (Toast.jsx), and the panel opens as View draws it (read only: there is no title to take the keyboard). As in the prototype, the list is then set so the new row is drawn: the Open, Closed, All switch, the type,
// every filter and the search are cleared, and the item's group is opened; the panel opens and its title takes the keyboard.
import { newItem } from "../stores/changes.js";
import { openPeek, filterState, setFilterState, setQuery, rows } from "../stores/report.js";
import { work, setWork, contextFor } from "../stores/work.js";
import { cellOf, isCollapsed, toggleCollapsed } from "../logic/board.js";
import { initial } from "../filters.js";
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
export function newItemRequest(kind, today, place = "menu", workstream = "") {
  if (!ADDABLE.includes(kind)) return null;
  const due = addDays(today, 7), ws = workstream ? { workstream } : {};     // a decision has no workstream
  if (kind === "decision") return { kind: "decisions", op: "new", values: { decision: TITLE.decision, needed_by: today }, place };
  if (kind === "action") return { kind: "actions", op: "new", values: { description: TITLE.action, due_date: due, priority: "Medium", ...ws }, place };
  return { kind: "raid", op: "new", values: { type: kind === "risk" ? "Risk" : "Issue", description: TITLE[kind], due_date: due, ...ws }, place };
}

/** What the toast says was filled in for the person: a due date, and for an action a priority, are placeholders. */
export const placeholderWords = (kind) => `${kind === "action" ? "Due date and priority are placeholders." : kind === "decision" ? "The needed-by date is a placeholder." : "The due date is a placeholder."} Change ${kind === "action" ? "them" : "it"} in the list.`;

/** The workstream a new item goes in, as the prototype has it: the one workstream filtered on (when exactly one is, and it is an
 *  active one), else the first active workstream, else none. */
export function workstreamFor(state, active) {
  const f = state && state.filters && state.filters.workstream;
  if (f && f.length === 1 && !(state.not && state.not.workstream) && active.includes(f[0])) return f[0];
  return active[0] || "";
}

// The list shows the new row: nothing filtered out, nothing searched, its group open (a shut group would hide it).
function showRow(ref, today) {
  setFilterState(initial());
  setQuery("");
  const r = rows.value.find((x) => x.id === ref), g = work.value.group;
  if (r && g && g !== "nothing") {
    const key = cellOf(g, r, contextFor(today, "all"));
    if (isCollapsed(work.value, g, key)) setWork(toggleCollapsed(work.value, g, key));
  }
}

// The panel's title takes the keyboard and its words are selected, once the panel is drawn (the prototype does the same at 60 ms).
function focusTitle() {
  setTimeout(() => {
    const t = document.querySelector("#peek .pk-title");
    if (!t) return;
    t.focus();
    if (window.getSelection) window.getSelection().selectAllChildren(t);
  }, 60);
}

/** Add one item and open it. Resolves to the new id, or null when nothing was added (the toast says why). */
export async function addItem(kind, place = "menu") {
  const today = todayIso();
  const req = newItemRequest(kind, today, place, workstreamFor(filterState.value, contextFor(today, "all").workstreams));
  if (!req) return null;
  const reply = await newItem(req, placeholderWords(kind));
  if (!reply || typeof reply.ref !== "string") return null;
  showRow(reply.ref, today);
  openPeek(reply.ref, "item");
  focusTitle();
  return reply.ref;
}
