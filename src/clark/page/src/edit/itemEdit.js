// #80: what the Work items table's four cells may change, as plain functions with no DOM and no clock (the caller hands in
// today). Each cell (owner, due, priority, status) has its own picker in ./cells/, and the peek (#42) can use the same pickers
// later. A change is sent through api.js as kind actions, raid or decisions, op update (clark/changes.py, #68): only
// the fields it accepts are named here. A RAID item's priority comes from its impact and likelihood and a decision has none, so
// their Priority cell is not a picker.
import { dueField, showDate, dayNumber, colourOf, pillOf } from "../workItems.js";

export const PRIORITIES = ["Urgent", "High", "Medium", "Low"];
const STATUSES = {
  action: ["Open", "Delayed", "Closed", "Cancelled"],
  raid: ["Open", "Closed", "Cancelled"],
  decision: ["Pending", "Made", "Withdrawn"],
};
export const FIELDS = ["owner", "due", "priority", "status"];
const DAY = 86400000;
// A character no one can see or that breaks a line (control, format such as a zero-width space or a right-to-left override,
// surrogate, private use, line and paragraph separators): clark/changes.py refuses a name with one (ITEM_BAD_KINDS), so the
// picker says so first and keeps the box open with what was typed.
const HIDDEN = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Zl}\p{Zp}]/u;

/** The table a row lives in, as clark names it. */
export function tableOf(row) {
  return row.kind === "action" ? "actions" : row.kind === "decision" ? "decisions" : "raid";
}

/** Whether a cell of this row opens a picker. */
export function canPick(row, field) {
  if (field === "priority") return row.kind === "action";
  return FIELDS.includes(field);
}

/** Why a cell that is not a picker can't be changed here, for its tooltip: a RAID item's priority comes from its impact and likelihood. */
export function whyFixed(row, field) {
  return field === "priority" && tableOf(row) === "raid" ? "Set from impact and likelihood" : "";
}

/** The statuses a row may be given. A made decision can't go back to Pending, so Pending is not offered then. */
export function statusChoices(row) {
  const all = row.kind === "action" ? STATUSES.action : row.kind === "decision" ? STATUSES.decision : STATUSES.raid;
  return row.kind === "decision" && row.status === "Made" ? all.filter((s) => s !== "Pending") : all.slice();
}

// #448 (row 54): the Status cell in Edit shows the live look, as the prototype's C.look does and View's pill does: a pick redraws it
// from the reply at once. An open risk or issue reads its colour (Red, Amber, Green), a late action Overdue, Delayed amber, Made
// green; Closed, Cancelled and Withdrawn are grey. The picker still offers, and its toast still says, the status words.

/** The Status cell's pill in Edit: {text, class}, the item's live look (the same as View's). `today` is YYYY-MM-DD. */
export function statusPill(row, today) { return pillOf(row, today); }

// D-12: a risk's or issue's rating is worked out from its impact and likelihood, so a colour is picked by setting those two:
// Red is High impact with Medium likelihood (High priority), Amber Medium and Medium, Green Low and Low.
export const RATINGS = { Red: { impact: "High", likelihood: "Medium" }, Amber: { impact: "Medium", likelihood: "Medium" }, Green: { impact: "Low", likelihood: "Low" } };

/** The Rating section of a risk's or issue's status picker: the three colours, whatever its status (#448, as the prototype), or
 * none for any other item (an action, a decision, an assumption, a dependency), as clark/changes.py refuses. */
export function ratingChoices(row) { return RATED.includes(row.kind) ? Object.keys(RATINGS) : []; }
const RATED = ["risk", "issue"];

/** The field a pick belongs to: the picker's Rating entries are sent as `rating:Red`, `rating:Amber` or `rating:Green`. */
export function pickField(field, value) { return field === "status" && /^rating:/.test(String(value)) ? "rating" : field; }

/** The small print under a status in the picker: Made is the one pick that can't be undone. */
export function statusNote(row, status) {
  return row.kind === "decision" && status === "Made" && row.status !== "Made" ? "Can't be undone" : "";
}

/** The column the Owner cell changes: a decision's is who makes it. */
export function ownerField(row) { return row.kind === "decision" ? "made_by" : "owner"; }

/** The column the Due cell changes: a pending decision's is the date it is needed by, any other decision's the date it was made. */
export function dueColumn(row) {
  if (row.kind !== "decision") return "due_date";
  return row.status === "Pending" ? "needed_by" : "date";
}

/** Whether the Due cell may be cleared: a made decision always has its date. */
export function canClearDue(row) { return !(row.kind === "decision" && row.status === "Made"); }

// What a cell is called in a sentence, for the label and the toast.
export function fieldName(row, field) {
  if (field === "owner") return row.kind === "decision" ? "Decider" : "Owner";
  if (field === "due") return row.kind !== "decision" ? "Due date" : row.status === "Pending" ? "Needed-by date" : "Decision date";
  return field === "priority" ? "Priority" : field === "rating" ? "Rating" : "Status";
}

/**
 * The change one pick makes: {changes, words, back} to send, {error} to say in the picker and send nothing, or null when the pick
 * is the value the row already has. `words` is what the toast says; `back` what its Undo says, the value the cell goes back to.
 * `today` is YYYY-MM-DD.
 */
export function changeFor(row, field, value, today) {
  const name = fieldName(row, field);
  if (field === "owner") {
    const text = String(value == null ? "" : value).trim().split(/\s+/).filter(Boolean).join(" ");
    const col = ownerField(row);
    const now = String(row.owner == null ? "" : row.owner).trim();
    if (!text) {
      if (row.kind !== "decision") return { error: "An owner can't be blank. Type a name, or TBC if no one is known yet." };
      return now ? { changes: { [col]: null }, words: `${name} of ${row.id} cleared.`, back: `${name} of ${row.id} is back to ${now}.` } : null;
    }
    if (HIDDEN.test(text)) return { error: "That name has a hidden character in it, often from copying and pasting. Type the name again, then press Enter." };
    if (Array.from(text).length > 200) return { error: "A name can be 200 characters at most. Shorten it and try again." };
    if (text === now) return null;
    const back = now ? `${name} of ${row.id} is back to ${now}.` : `${name} of ${row.id} is blank again.`;
    return { changes: { [col]: text }, words: `${name} of ${row.id} changed to ${text}.`, back };
  }
  if (field === "due") {
    const iso = value || null;
    if (iso !== null && dayNumber(iso) === null) return { error: "That date isn't a real day, so nothing was changed. Pick another date." };
    if (iso === null && !canClearDue(row)) return { error: "A made decision keeps the date it was made. Pick another date instead." };
    const was = dueField(row) || null;
    if (iso === was) return null;
    const back = was ? `${name} of ${row.id} is back to ${showDate(was)}.` : `${name} of ${row.id} is blank again.`;
    return { changes: { [dueColumn(row)]: iso }, words: iso ? `${name} of ${row.id} changed to ${showDate(iso)}.` : `${name} of ${row.id} cleared.`, back };
  }
  if (field === "priority") {
    if (tableOf(row) === "raid") return { error: "A risk's or issue's priority is set from its impact and likelihood, so nothing was changed." };
    if (!canPick(row, "priority")) return { error: "A decision has no priority, so nothing was changed." };
    if (!PRIORITIES.includes(value)) return { error: "That priority can't be used, so nothing was changed. Pick Urgent, High, Medium or Low." };
    if (value === row.priority) return null;
    const back = row.priority ? `Priority of ${row.id} is back to ${row.priority}.` : `Priority of ${row.id} is blank again.`;
    return { changes: { priority: value }, words: `Priority of ${row.id} changed to ${value}.`, back };
  }
  if (field === "rating") {
    const word = String(value).replace(/^rating:/, "");
    if (!ratingChoices(row).length || !RATINGS[word]) return { error: "Only a risk or an issue has a rating. Pick Red, Amber or Green." };
    const now = colourOf(row.priority);
    if (now.word === word) return null;
    return { changes: { ...RATINGS[word] }, words: `${row.id} rated ${word}.`, back: `${row.id} is back to ${now.word}.` };
  }
  if (field === "status") {
    if (!statusChoices(row).includes(value)) return { error: "That status isn't one this item can have, so nothing was changed. Pick one from the list." };
    if (value === row.status) return null;
    const changes = { status: value };
    if (row.kind === "decision") {
      if (value === "Made" && !row.date) changes.date = today;          // a made decision needs the date it was made: today
      if (value === "Pending" && row.date) changes.date = null;         // a pending one has none yet
    }
    const words = row.kind === "decision" && value === "Made"
      ? `${row.id} is now made, on ${showDate(changes.date || row.date)}. This can't be undone. To change it, record a new decision.`
      : `Status of ${row.id} changed to ${value}.`;
    return { changes, words, back: `Status of ${row.id} is back to ${row.status}.` };
  }
  return { error: "Only the owner, due date, priority and status can be changed here. Nothing was changed." };
}

/** Everyone named as an owner or a decider in the project's data, in alphabetical order, once each. */
export function people(data) {
  const names = new Set();
  const add = (v) => { const t = String(v == null ? "" : v).trim(); if (t && t.toUpperCase() !== "TBC") names.add(t); };
  for (const r of (data && data.actions) || []) add(r.owner);
  for (const r of (data && data.raid) || []) add(r.owner);
  for (const r of (data && data.decisions) || []) add(r.made_by);
  for (const m of (data && data.milestones) || []) add(m.owner);
  return Array.from(names).sort((a, b) => a.localeCompare(b, "en-GB"));
}

/** The names that match what has been typed (any word starting with it, or the whole name containing it), best first. */
export function matching(names, typed) {
  const q = String(typed || "").trim().toLowerCase();
  if (!q) return names.slice();
  const starts = names.filter((n) => n.toLowerCase().split(/\s+/).some((w) => w.startsWith(q)) || n.toLowerCase().startsWith(q));
  const inside = names.filter((n) => !starts.includes(n) && n.toLowerCase().includes(q));
  return starts.concat(inside);
}

// ── Dates for the picker: plain days, read in UTC so a clock change never moves one ──

function iso(t) {
  const d = new Date(t);
  return `${String(d.getUTCFullYear()).padStart(4, "0")}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}

/** The day `n` days after `day` (YYYY-MM-DD). */
export function addDays(day, n) { return iso((dayNumber(day) + n) * DAY); }

/** YYYY-MM of the month `n` months after `ym`. */
export function addMonths(ym, n) {
  const y = +ym.slice(0, 4), m = +ym.slice(5, 7) - 1 + n;
  const t = new Date(Date.UTC(y, m, 1));
  return iso(t.getTime()).slice(0, 7);
}

/** A month's grid, Monday first: '' for a blank before the 1st, then each day as YYYY-MM-DD. */
export function monthCells(ym) {
  const y = +ym.slice(0, 4), m = +ym.slice(5, 7) - 1;
  const first = new Date(Date.UTC(y, m, 1)), lead = (first.getUTCDay() + 6) % 7;
  const n = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  const out = new Array(lead).fill("");
  for (let d = 1; d <= n; d++) out.push(`${ym}-${String(d).padStart(2, "0")}`);
  return out;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export function monthTitle(ym) { return `${MONTHS[+ym.slice(5, 7) - 1]} ${ym.slice(0, 4)}`; }

/** The quick choices under the month: Today, Tomorrow, Friday (the next one, a week on if today is Friday), Next week. */
export function quickDates(today) {
  const wd = new Date(dayNumber(today) * DAY).getUTCDay();               // 0 Sunday .. 6 Saturday
  const toFri = ((5 - wd + 7) % 7) || 7;
  return [["Today", today], ["Tomorrow", addDays(today, 1)], ["Friday", addDays(today, toFri)], ["Next week", addDays(today, 7)]];
}
