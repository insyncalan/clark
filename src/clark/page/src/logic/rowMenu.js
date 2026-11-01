// The right-click menu on a work item (#97): what it offers for one item, and the words and requests behind each entry. Plain
// functions, no DOM and no Preact, so a test can run them alone. The menu itself is edit/RowMenu.jsx. An entry that can't be used
// is still listed, with the reason under it in words, so a person who uses the keys can read why (a greyed entry can't be focused).
import { statusChoices, tableOf, changeFor, quickDates, addDays } from "../edit/itemEdit.js";
import { ownerOf, showDate } from "../workItems.js";

export const TITLE_OF = { actions: "description", raid: "description", decisions: "decision" };
const TITLE_LIMIT = 200;                         // clark/changes.py: a title is at most this many characters
export const VIEW_ONLY = "Switch to Edit to change this.";
export const EYE_LATER = "Showing or hiding an item for the client from here comes with a later release.";

export const NEEDS_PEOPLE = "Draft email needs the People list (coming with #115).";
export const NOT_CONNECTED = "Draft email will open from here in a later release.";

/** Where a person's email address is kept: the project's people (data.people, #115), found by the owner's id, never the name
 *  (two people can share a name, docs/handoff/design-115-people-table.md). "" when there is no id, no such person or no address.
 *  A work item carries no owner id until #115 is built, so today this is always "". */
export function emailOf(data, ownerId) {
  const id = String(ownerId == null ? "" : ownerId).trim();
  if (!id) return "";
  const p = ((data && data.people) || []).find((x) => x && x.id === id);
  return p && typeof p.email === "string" ? p.email.trim() : "";
}

/** The Draft email entry: {name, reason, to}. It is always greyed for now: the editor (DraftEmail.jsx) is given an email that the
 *  builder (clark/draft_email.py) makes, and the page has no route to it. `reason` says why; `to` is the address found by id. */
export function draftEntry(row, data) {
  const o = ownerOf(row.owner);
  if (!o.initials) return { name: "Draft email to the owner", reason: "This item has no owner yet, so there is no one to write to.", to: "" };
  const to = emailOf(data, row.owner_id);
  const reason = !(data && Array.isArray(data.people)) ? NEEDS_PEOPLE : to ? NOT_CONNECTED : `${o.text} has no email on the People list.`;
  return { name: `Draft email to ${o.text}`, reason, to };
}

/** The statuses the Change status list offers (the same as the Status cell's picker), without the one the item has. */
export function statusList(row) { return statusChoices(row).filter((s) => s !== row.status); }

/** The dates the Move due date list offers: Friday and a week on (both counted from today), each with its date. */
export function dueList(today) {
  const fri = quickDates(today).find((q) => q[0] === "Friday");
  return [{ id: "friday", name: "Friday", day: fri[1] }, { id: "week", name: "A week on", day: addDays(today, 7) }]
    .map((d) => ({ ...d, line: showDate(d.day) }));
}

/** The names the Change owner list offers: the people in the project's data, except the current owner. */
export function ownerList(names, row) {
  const now = ownerOf(row.owner).text;
  return names.filter((n) => n !== now);
}

/** What Duplicate asks for: the item's own fields and a title that says it is a copy. No id, status, dates it was given or history. */
export function duplicateRequest(raw, table) {
  const keep = { actions: ["owner", "priority", "due_date", "workstream", "milestone"],
    raid: ["type", "owner", "impact", "likelihood", "due_date", "workstream", "milestone"], decisions: ["made_by", "needed_by"] }[table];
  const title = TITLE_OF[table];
  const values = {};
  for (const k of keep) if (raw[k] != null && raw[k] !== "") values[k] = raw[k];
  values[title] = ("Copy of " + String(raw[title])).slice(0, TITLE_LIMIT);
  return { kind: table, op: "new", values, place: "menu" };
}

/** The raw record of a row in the project's data (the page keeps a flat row; Duplicate needs every field). */
export function rawOf(data, row) {
  return ((data && data[tableOf(row)]) || []).find((r) => r.id === row.id) || null;
}

/** The change a pick makes from the menu, as the cells make it: {table, id, changes, words, back}, {error}, or null for no change. */
export function pickChange(row, field, value, today) {
  const c = changeFor(row, field, value, today);
  if (!c || c.error) return c;
  return { table: tableOf(row), id: row.id, changes: c.changes, words: c.words, back: c.back };
}

/** The address of an item's peek, for Copy link: this page with the item in it. `format` is the router's. */
export function linkFor(row, project, base, format) {
  return base + format({ view: "work", project, item: row.id, ms: "", f: "" });
}
