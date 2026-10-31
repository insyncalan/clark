// The coloured icons in the peek (#78). Plain functions, no DOM and no clock: each returns a tone, one of r a g b n (the same
// letters as the list's pills). shell.css gives each tone an icon class (ic-r ...) and that class takes its colour from a design
// token (--icon-red ...), so no colour is written anywhere here. A tone is never the only signal: the status, the priority and the
// date are always written beside their icon.
import { dayNumber, dueField, isOpen, pillOf } from "./workItems.js";

export const TONES = ["r", "a", "g", "b", "n"];
const PRIORITY_TONE = { Urgent: "r", High: "a", Medium: "b", Low: "n" };

/** The status icon takes the state's own colour: the one the list's pill shows. */
export function statusTone(row, today) { return pillOf(row, today).class; }

/** Urgent red, High amber, Medium blue; Low and no priority grey. */
export function priorityTone(priority) { return PRIORITY_TONE[priority] || "n"; }

/** The date: red when it is past and the item is open, amber when it is within 7 days (today counts), blue for a later date or a closed item's date, grey for no date. */
export function dateTone(row, today) {
  const a = dayNumber(dueField(row)), b = dayNumber(today);
  if (a === null) return "n";
  if (b === null || !isOpen(row)) return "b";
  if (a < b) return "r";
  return a - b <= 7 ? "a" : "b";
}

/** The class an icon carries (for example "ic-r"); an unknown tone is grey. */
export function iconClass(tone) { return `ic-${TONES.includes(tone) ? tone : "n"}`; }
