// #199: Hand over, the rules as plain functions with no DOM, no signals and no clock. Hand over gives the open work items on the
// list to someone else in one step with one Undo: the items are ticked, a person is named, and one request goes to clark (op
// "handover", clark/changes.py, through the bulk change's writer). The ticks are the page's own and never saved. Archived and
// closed items are never offered. Once the people list has anyone on it, clark takes only a person on it.
import { isOpen } from "../workItems.js";
import { CONFIRM_ABOVE, MAX, tableOf, itemsWords } from "../edit/bulkLogic.js";

/** The items Hand over offers from the rows shown: the open ones, in the order given. */
export const offered = (rows) => rows.filter((r) => isOpen(r));

/** "3 of 12 selected": what the bar and a screen reader say. */
export const countWords = (n, m) => `${n} of ${m} selected`;

/** The name as it will be sent: trimmed, with inner spaces made single. */
export const clean = (to) => String(to == null ? "" : to).trim().split(/\s+/).filter(Boolean).join(" ");

const key = (s) => clean(s).toLowerCase();

/** What stops the Hand over button, in words, or "" when it can go. `to` is what has been typed in the person field. */
export function why(n, to) {
  if (n === 0) return "Tick at least one item.";
  if (n > MAX) return `Tick at most ${MAX} items at a time.`;
  if (!clean(to)) return "Say who to hand over to.";
  if (key(to) === "tbc") return "Say who to hand over to: a person, not TBC.";
  return "";
}

/** The names the person field suggests: the live people on the people list when it has anyone (clark takes only them then),
 *  else the names already on the project (`project`, as the Owner picker offers them). */
export function names(people, project) {
  const live = (Array.isArray(people) ? people : []).filter((p) => p && !p.archived && typeof p.name === "string").map((p) => p.name);
  return live.length ? Array.from(new Set(live)).sort((a, b) => a.localeCompare(b, "en-GB")) : project.slice();
}

/** A line under the field when the name typed is none of the names offered: a hint, never a stop (clark has the last word).
 *  `listed`: the names are the people list's. */
export function hint(to, offeredNames, listed = false) {
  if (!clean(to) || (offeredNames || []).some((x) => key(x) === key(to))) return "";
  return listed ? "No one on the people list has that name. Check the spelling." : "No one in this project has that name yet. Check the spelling.";
}

/** The request for clark: one hand over of `ids` to `to`. The kind is the first item's; the items may be of all three kinds. */
export function requestFor(rows, ids, to, { confirm = false } = {}) {
  const first = rows.find((r) => r.id === ids[0]);
  return { kind: first ? tableOf(first) : "actions", op: "handover", ids: ids.slice(), to: clean(to), place: "bulk", ...(confirm ? { confirm: true } : {}) };
}

/** Whether to ask first, and the question: above CONFIRM_ABOVE items. */
export const needsConfirm = (n) => n > CONFIRM_ABOVE;
export const confirmWords = (n, to) => `Hand over ${n} items to ${clean(to)}?`;

/** What the toast says after the Undo of a hand over, from clark's reply: the items it changed, not the items ticked. */
export function backWords(reply) {
  const n = reply && Array.isArray(reply.changed) ? reply.changed.length : 0;
  return n ? `Undone: ${itemsWords(n)} ${n === 1 ? "is" : "are"} back with ${n === 1 ? "its" : "their"} owner.` : "Undone.";
}

/** Whether the Owner filter is on and picks people (not "is not"): the Hand over button is offered then. */
export function ownerFilterOn(state) {
  const f = state && state.filters && state.filters.owner;
  return Array.isArray(f) && f.length > 0 && !(state.not && state.not.owner);
}
