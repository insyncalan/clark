// The At a glance tiles on the Dashboard (#79; rules as in glance.py, the reference, and the prototype's glanceData): plain
// functions with no DOM and no clock (today is passed in). Each tile counts with the SAME filter state it opens Work items with
// (filters.js applyFilters), so the number on a tile is always the number of rows in the list it opens.
import { applyFilters, initial, setType, setFilter } from "./filters.js";
import { isOpen, dueField, showDate, dayNumber, plural } from "./workItems.js";

const state = (type, field, values) => setFilter(setType(initial(), type), field, values, false);

// Overdue actions: open actions due before today. High risks and issues: open risks, issues, assumptions and dependencies rated
// Urgent or High. Decisions needed: decisions still Pending.
export const FILTERS = {
  overdue: state("action", "due", ["overdue"]),
  risks: state("risk", "priority", ["Urgent", "High"]),
  decisions: state("decision", "status", ["Pending"]),
};
export const HEALTH_WORDS = { "On track": "g", "At risk": "a", "Off track": "r" };

/** The tiles after Project health, in order: [{key, label, value, detail, rag ("g" "a" "r"), filter}]. */
export function tiles(rows, today) {
  const n = (s) => applyFilters(rows, s, today).length;
  const open = (type) => rows.filter((r) => isOpen(r) && (type === "action" ? r.kind === "action" : r.kind !== "action" && r.kind !== "decision")).length;
  const over = n(FILTERS.overdue), high = n(FILTERS.risks), dec = applyFilters(rows, FILTERS.decisions, today);
  const dates = dec.map((r) => dueField(r)).filter((d) => dayNumber(d) !== null).sort();
  const risksOpen = open("risk");
  return [
    { key: "overdue", label: "Overdue actions", value: over, detail: `of ${plural(open("action"), "open action")}`, rag: over ? "r" : "g", filter: FILTERS.overdue },
    { key: "risks", label: "High risks and issues", value: high, detail: high ? `of ${risksOpen} open` : risksOpen ? "None high" : "None open", rag: high ? "r" : risksOpen ? "a" : "g", filter: FILTERS.risks },
    { key: "decisions", label: "Decisions needed", value: dec.length, detail: dates.length ? `Oldest ${showDate(dates[0])}` : dec.length ? "No date set" : "None waiting", rag: dec.length ? "a" : "g", filter: FILTERS.decisions },
  ];
}
