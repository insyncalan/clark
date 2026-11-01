// The 'Needs from you' section's rules (#121): pure functions and words, no DOM, no signals, no clock, nothing sent. The section keeps
// its rows as text in the section's body (clark/section_bodies.py is the store's own check of the same shape; the page checks first
// so a mistake is said in words before anything is sent, and the store checks again). A row is
//   { what, kind: "decision" | "information" | "date", from, by: "YYYY-MM-DD" or "", hidden: 0 | 1 }
// and the list's order is the order shown. In a published file the rows arrive as the file holds them: shown rows only, `by` written
// DD-MM-YYYY (publish: section_bodies.published); rowsOf turns both into one shape.
import { dayNumber, showDate } from "../workItems.js";

export const MAX_ROWS = 100;
export const WHAT_MAX = 300;
export const FROM_MAX = 100;
export const YEARS = [2000, 2100];
export const KINDS = [["decision", "Decision"], ["information", "Information"], ["date", "Date"]];
export const kindWord = (k) => (KINDS.find((x) => x[0] === k) || ["", ""])[1];

// Every word the section shows or says. A test reads each one: no jargon, and no sentence that starts with the product name.
export const WORDS = {
  title: "Needs from you",
  what: "What is needed",
  from: "From",
  by: "By",
  kind: "Kind",
  none: "Nothing needed from you yet.",
  overdue: "Overdue",
  noDate: "No date",
  addRow: "Add a row",
  add: "Add",
  save: "Save",
  cancel: "Cancel",
  edit: "Edit",
  remove: "Remove",
  hide: "Leave out",
  show: "Include",
  left: "Left out of the published page",
  datePlaceholder: "DD-MM-YYYY",
  added: "Row added.",
  saved: "Row saved.",
  removed: "Row removed.",
  hidden: "Row left out of the published page.",
  shown: "Row included in the published page.",
  full: `A list can have ${MAX_ROWS} rows at most. Remove one to add another.`,
  problems: {
    whatMissing: "Say what is needed.",
    whatLong: `What is needed can be ${WHAT_MAX} characters at most.`,
    kind: "Choose whether it is a decision, information or a date.",
    fromLong: `From can be ${FROM_MAX} characters at most.`,
    by: `By must be a real day written DD-MM-YYYY, between ${YEARS[0]} and ${YEARS[1]}, or empty.`,
  },
};
export const ALL_WORDS = () => {
  const out = [];
  const walk = (o) => { for (const v of Object.values(o)) { if (typeof v === "string") out.push(v); else walk(v); } };
  walk(WORDS);
  for (const k of KINDS) out.push(k[1]);
  return out;
};

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
const DMY = /^(\d{2})-(\d{2})-(\d{4})$/;

// A typed or published date as YYYY-MM-DD, or "" when it is empty, or null when it is not a real day in range.
export function isoOf(text) {
  const t = String(text == null ? "" : text).trim();
  if (!t) return "";
  const m = DMY.exec(t);
  const iso = m ? `${m[3]}-${m[2]}-${m[1]}` : ISO.test(t) ? t : "";
  const day = dayNumber(iso);
  if (day === null) return null;
  const y = +iso.slice(0, 4);
  return y >= YEARS[0] && y <= YEARS[1] ? iso : null;
}

// The rows a section holds, as one shape (`hidden` 0 or 1, `by` YYYY-MM-DD or ""). `fromFile`: the file's own rows (shown only, `by`
// as DD-MM-YYYY). Otherwise the stored body, which is text; text that can't be read, or has no rows, is no rows. Never throws.
export function rowsOf(section, fromFile) {
  let list = [];
  if (fromFile) list = Array.isArray(section && section.rows) ? section.rows : [];
  else {
    try {
      const v = JSON.parse(section && typeof section.body === "string" && section.body ? section.body : "{}");
      list = v && typeof v === "object" && Array.isArray(v.rows) ? v.rows : [];
    } catch (e) { list = []; }
  }
  const out = [];
  for (const r of list) {
    if (!r || typeof r !== "object" || typeof r.what !== "string" || !r.what) continue;
    const by = isoOf(r.by);
    out.push({ what: r.what, kind: KINDS.some((k) => k[0] === r.kind) ? r.kind : "information", from: typeof r.from === "string" ? r.from : "",
      by: by === null ? "" : by, hidden: r.hidden === 1 ? 1 : 0 });
  }
  return out;
}

// The rows a reader sees: a left-out row is absent, not dimmed.
export const shownRows = (rows) => rows.filter((r) => !r.hidden);

// The words a row carries for its date: { text: "DD-MM-YYYY" or "No date", overdue: boolean }. A day before `today` (YYYY-MM-DD) is overdue.
export function dueOf(row, today) {
  if (!row.by) return { text: WORDS.noDate, overdue: false };
  const n = dayNumber(row.by), t = dayNumber(today);
  return { text: showDate(row.by), overdue: n !== null && t !== null && n < t };
}

// What a row needs to be saved, as a plain sentence, or "". `draft` is { what, kind, from, by } as typed (`by` DD-MM-YYYY or YYYY-MM-DD).
export function problem(draft) {
  const what = String(draft.what == null ? "" : draft.what).trim(), who = String(draft.from == null ? "" : draft.from).trim();
  const chars = (s) => Array.from(s).length;
  if (!what) return WORDS.problems.whatMissing;
  if (chars(what) > WHAT_MAX) return WORDS.problems.whatLong;
  if (!KINDS.some((k) => k[0] === draft.kind)) return WORDS.problems.kind;
  if (chars(who) > FROM_MAX) return WORDS.problems.fromLong;
  if (isoOf(draft.by) === null) return WORDS.problems.by;
  return "";
}

// A typed row as it is saved.
export function made(draft, hidden = 0) {
  return { what: String(draft.what).trim(), kind: draft.kind, from: String(draft.from == null ? "" : draft.from).trim(), by: isoOf(draft.by) || "", hidden: hidden ? 1 : 0 };
}

// The body text for a list of rows: what the one change sends. (clark keeps it in its own canonical form; the order of keys here is not kept.)
export const bodyOf = (rows) => JSON.stringify({ v: 1, rows: rows.map((r) => ({ what: r.what, kind: r.kind, from: r.from, by: r.by, hidden: r.hidden ? 1 : 0 })) });

// The list after one change: add at the end, replace row `i`, flip its `hidden`, or remove it. Each returns the new list, or null when
// it can't be done (no such row, or the list is full).
export const withAdded = (rows, row) => (rows.length >= MAX_ROWS ? null : [...rows, row]);
export const withReplaced = (rows, i, row) => (i >= 0 && i < rows.length ? rows.map((r, j) => (j === i ? row : r)) : null);
export const withFlipped = (rows, i) => (i >= 0 && i < rows.length ? rows.map((r, j) => (j === i ? { ...r, hidden: r.hidden ? 0 : 1 } : r)) : null);
export const withoutRow = (rows, i) => (i >= 0 && i < rows.length ? rows.filter((_, j) => j !== i) : null);
