// Key dates' rules (#96, G4): pure, no DOM and no Preact, shared by the view part and the Edit part. A key date is a milestone (named by
// its id; what it is called, its date and its state are read live) or a typed date (a label and a day).
import { milestoneRows, todayIso } from "../logic/milestones.js";
import { keptRows, rulesFor } from "../logic/publishable.js";
import { dayNumber } from "../workItems.js";
import { dateWords } from "./safe.js";

export const MAX_ITEMS = 12;
export const LABEL_MAX = 120;

// The stored items of a section: its body (the page clark serves) or its published `items` (the file). Anything unreadable is no items.
export function itemsOf(section) {
  let list = null;
  if (section && typeof section.body === "string" && section.body) {
    try { const v = JSON.parse(section.body); list = v && Array.isArray(v.items) ? v.items : null; } catch (e) { list = null; }
  } else if (section && Array.isArray(section.items)) list = section.items;
  return (list || []).filter((i) => i && typeof i === "object" && ((typeof i.milestone === "string") || (typeof i.label === "string" && typeof i.date === "string")));
}

export const bodyOf = (items) => JSON.stringify({ v: 1, items });

// The milestones this page may show: in the file every milestone it holds (publish kept them); in the served View the same rows
// publish would keep (logic/publishable.js), so what View shows is what the client reads (FR-11).
export function shownMilestones(data, fromFile) {
  const all = (data && data.milestones) || [];
  if (fromFile) return all;
  const rules = rulesFor({ code: data && data.project && data.project.code, hidden: data && data.hidden, labelRules: data && data.label_rules, labels: data && data.labels, sections: data && data.report_sections });
  return keptRows(data, "milestones", rules);
}

// The lines to draw, soonest first (a line with no date last), as { key, label, date, words, tone, milestone }.
// `date` is the day as stored ("" for none); `words` is the milestone's state in the client's words ("" for a typed date).
export function linesOf(section, data, { fromFile = false, today = todayIso() } = {}) {
  const rows = new Map(milestoneRows(shownMilestones(data, fromFile), today, true).map((r) => [r.id, r]));
  const out = [];
  itemsOf(section).forEach((i, n) => {
    if (typeof i.milestone === "string") {
      const r = rows.get(i.milestone);
      if (!r) return;
      const date = r.achieved || r.expected || r.baseline || r.forecast || "";
      out.push({ key: i.milestone, label: r.name, date, words: r.word, tone: r.state === "Overdue" || r.state === "Slipped" ? "late" : r.state === "At risk" ? "risk" : "", milestone: true, n });
    } else if (dayNumber(i.date) !== null) {
      out.push({ key: `t${n}`, label: i.label, date: i.date, words: "", tone: "", milestone: false, n });
    }
  });
  return out.map((l, k) => ({ ...l, k })).sort((a, b) => (a.date === b.date ? a.k - b.k : !a.date ? 1 : !b.date ? -1 : a.date < b.date ? -1 : 1));
}

export const showDay = (iso) => (iso ? dateWords(iso) : "No date set");

// A typed day as a person writes it, DD-MM-YYYY (or DD/MM/YYYY, or the stored YYYY-MM-DD), as the stored day; "" when it is not a real day.
export function parseDay(text) {
  const t = String(text == null ? "" : text).trim();
  let iso = "";
  let m = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/.exec(t);
  if (m) iso = `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
  else if (/^\d{4}-\d{2}-\d{2}$/.test(t)) iso = t;
  return dayNumber(iso) === null ? "" : iso;
}

export const problem = {
  label: `A date needs a label of 1 to ${LABEL_MAX} characters. Type what the date is for.`,
  day: "That isn't a day clark can read. Type it as DD-MM-YYYY, for example 15-01-2030.",
  full: `Key dates can hold ${MAX_ITEMS} dates. Remove one first, then add the new one.`,
};
