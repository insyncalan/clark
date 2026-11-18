// The right-click menu on a work item (#97): what it offers for one item, and the words and requests behind each entry. Plain
// functions, no DOM and no Preact, so a test can run them alone. The menu itself is edit/RowMenu.jsx. An entry that can't be used
// is still listed, with the reason under it in words, so a person who uses the keys can read why (a greyed entry can't be focused).
import { statusChoices, tableOf, changeFor, quickDates, addDays } from "../edit/itemEdit.js";
import { ownerOf, showDate } from "../workItems.js";
import { buildOptions } from "./draftEmail.js";
import { searchPeople, sameName } from "./assignTo.js";

export const TITLE_OF = { actions: "description", raid: "description", decisions: "decision" };
const TITLE_LIMIT = 200;                         // clark/changes.py: a title is at most this many characters
export const VIEW_ONLY = "Switch to Edit to change this.";

export const NO_PEOPLE = "The To line is left empty: there is no People list to take the address from yet.";

/** Where a person's email address is kept: the project's people (data.people, #115), found by the owner's id, never the name
 *  (two people can share a name, docs/handoff/design-115-people-table.md). "" when there is no id, no such person or no address.
 *  A work item carries no owner id until #115 is built, so today this is always "". */
export function emailOf(data, ownerId) {
  const id = String(ownerId == null ? "" : ownerId).trim();
  if (!id) return "";
  const p = ((data && data.people) || []).find((x) => x && x.id === id);
  return p && typeof p.email === "string" ? p.email.trim() : "";
}

// The server's own rule for an address (draft_email_feed.py ADDRESS, MAX_EMAIL): one plain address, no space, bracket, quote, comma, semicolon,
// colon or query mark, at most 254 characters. The page sends nothing that the server would refuse, so a bad People address leaves the To line empty.
const ADDRESS = /^[^@\s<>?,;:"()[\]\\]+@[^@\s<>?,;:"()[\]\\]+\.[^@\s<>?,;:"()[\]\\]+$/;
// The server also refuses a control character, a line break, a space and any hidden mark (bidi override, zero-width, private use, lone surrogate).
const HIDDEN = /[\p{Cc}\p{Cf}\p{Co}\p{Cs}\p{Zl}\p{Zp}]/u;
const ADDRESS_MAX = 254, NAME_MAX = 100;

/** The Draft email's recipient from the People list: {email, name} for the owner's id, or null when there is no id, no such person, no
 *  address, or an address the server would refuse. Found by id, never by name; nothing is invented. */
export function recipientOf(people, ownerId) {
  if (!Array.isArray(people)) return null;
  const email = emailOf({ people }, ownerId);
  if (!email || email.length > ADDRESS_MAX || !ADDRESS.test(email) || HIDDEN.test(email)) return null;
  const id = String(ownerId).trim(), p = people.find((x) => x && x.id === id);
  const name = typeof p.name === "string" ? p.name.trim() : "";
  return { email, name: name.length <= NAME_MAX && !/[\r\n]/.test(name) ? name : "" };
}

/** The Draft email entry: {name, reason, to, disabled}. It opens the Draft email dialog with a draft the server builds for this one
 *  item (POST /api/draft-email); nothing is sent. Only an item with no owner is greyed. `to` is the address found by owner id on the People
 *  list (#115), "" until that exists, and then the To line is left empty for the person to type: `reason` says so. */
export function draftEntry(row, data) {
  const o = ownerOf(row.owner);
  if (!o.initials) return { name: "Draft email to the owner", reason: "This item has no owner yet, so there is no one to write to.", to: "", disabled: true };
  const who = recipientOf(data && data.people, row.owner_id), to = who ? who.email : "";
  const reason = !(data && Array.isArray(data.people)) ? NO_PEOPLE : to ? "" : `${o.text} has no email on the People list, so the To line is left empty.`;
  return { name: `Draft email to ${o.text}`, reason, to, disabled: false };
}

/** What the Show / Hide entry asks for: one change to the item's own eye, with the words the toast says and says after an Undo.
 *  The name follows the item: a client-visible item offers Hide from the client, a hidden one Show to the client. */
export function eyeChange(row) {
  const on = !!row.client, value = on ? 0 : 1;
  return {
    name: on ? "Hide from the client" : "Show to the client",
    table: tableOf(row), id: row.id, changes: { client_visible: value },
    words: on ? `${row.id} is hidden from the client.` : `${row.id} is shown to the client.`,
    back: on ? `${row.id} is shown to the client again.` : `${row.id} is hidden from the client again.`,
  };
}

export const NOT_OFFERED = "This item cannot go in an email: it is hidden from the report, marked sensitive or restricted, or no longer open.";

/** The body of POST /api/draft-email (draft_email_feed.py) for this one item. `state` is the dialog's (logic/draftEmail.js buildOptions); without
 *  it, the first ask: the item ticked and the kind left for the server to choose from the item. `item` keeps the offer to this one item. */
export function draftRequest(id, state, who) {
  let body = { item: id, picked: [id] };
  if (state) {
    const o = buildOptions(state);
    body = { item: id, mode: o.mode, picked: o.picked, include_update: o.include_update };
    if (o.reply_by) body.reply_by = o.reply_by;
    if (o.unblocks) body.unblocks = o.unblocks;
    if (o.tone != null) body.tone = o.tone;                                                     // the chase tone the person pressed
  }
  if (who && who.email) { body.email = who.email; if (who.name) body.name = who.name; }      // #1048: the owner, from their People row
  return body;
}

/** The dialog's state from the route's answer: the kind and ticks it chose, with the options as they were (or empty at the first ask). */
export function draftState(reply, was) {
  const next = { mode: reply.mode, picked: reply.picked, replyBy: was ? was.replyBy : "", unblocks: was ? was.unblocks : "", includeUpdate: was ? !!was.includeUpdate : false };
  if (was && was.tone != null) next.tone = was.tone;
  return next;
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

/** Item 1070: the names the Change owner list shows for what is typed in its search box. Nothing typed: the list as it was. Typed:
 *  the register's live people (name, alias, email, role) and the project's names that match, as the Assign-to picker finds them,
 *  except the current owner. */
export function ownerChoices(register, names, row, typed) {
  if (!String(typed == null ? "" : typed).trim()) return ownerList(names, row);
  const now = ownerOf(row.owner).text;
  return searchPeople(register, names, typed).map((h) => h.name).filter((n) => !sameName(n, now));
}

/** Item 1070: whether the typed text can be offered as "Add ... as a new person": some text that is not TBC and is no one the
 *  register (an archived person too) or the project already names (nor the current owner). The picker's own rule (OwnerPick.known). */
export function canAddPerson(register, names, row, typed) {
  const t = String(typed == null ? "" : typed).trim();
  if (!t || sameName(t, "TBC") || sameName(t, ownerOf(row.owner).text)) return false;
  const known = [...names, ...(Array.isArray(register) ? register : []).filter((p) => p).flatMap((p) => [p.name, ...String(p.aliases || "").split(";")])];
  return !known.some((n) => n && sameName(n, t));
}

/** What Duplicate asks for (#442): the item's id and a title that says it is a copy. The server copies everything else from the
 *  STORED item (status, latest update, use case, owner, dates, the eye, its labels and its hiding), never from this request. */
export const COPY_MARK = " (copy)";
export function duplicateRequest(raw, table) {
  const title = TITLE_OF[table];
  const values = { [title]: String(raw[title]).slice(0, TITLE_LIMIT - COPY_MARK.length) + COPY_MARK };
  if (table === "raid" && raw.type) values.type = raw.type;          // the server's check for a new risk; it takes the stored one
  return { kind: table, op: "new", values, copy_of: raw.id, place: "menu" };
}

/** The toast's words for a copy, once the server gave it its id: what was added, and what Undo says when it takes the copy back. */
export function duplicateWords(row, ref) {
  return { text: `${ref} added, a copy of ${row.id}.`, back: `${ref} is taken back. ${row.id} is as it was.` };
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

/** Delete one work item (item 658): the question the dialog asks, the toast after it and the Undo words. The item is removed with its links and labels in one
 *  step; the toast's Undo (the store can restore it) brings all of it back. Only an action, a RAID item or a decision (never a milestone or a use case). */
export const deleteQuestion = (id) => `Delete ${id}? This removes it from your project record.`;
export const deleteWords = (id) => ({ text: `${id} deleted.`, back: `${id} is back.` });
export const deleteRequest = (id, kind, place) => ({ kind, op: "delete", id, place });
