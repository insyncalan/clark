// Row 1230 (picker PR): the logic of the Add a milestone picker's table and filter panel. Plain functions, no DOM and no Preact, so a
// test can run them alone. The picker offers the milestones that are not on the Dashboard page: taken off with the eye (their id is
// in report_hidden) or not for the client (client_visible 0); archived ones are never offered (logic/picker.js pickable).
// Each offered row says where it is (`why`), one of two words. Nothing here saves.
import { pickable, idsOf } from "./picker.js";
import { milestoneRows, CANCELLED } from "./milestones.js";
import { dayNumber } from "../workItems.js";

export const EYE = "Taken off with the eye", NOT_ON = "Not on the page";
export const FIELDS = ["status", "due"], MORE = ["page", "client"];
export const FIELD_NAME = { status: "Status", due: "Due", page: "On the page", client: "Client-visible" };
export const DUE = [["overdue", "Overdue"], ["soon", "Due in 7 days"], ["none", "No date"], ["later", "Later"]];
export const STATUS = ["Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast", "Cancelled"];
const CLIENT = [["yes", "Shown to the client"], ["no", "Internal only"]];
const PAGE = [[NOT_ON, NOT_ON], [EYE, EYE]];

// The offered milestones as table rows: the list's own row (logic/milestones.js milestoneRows) plus `why`, in the data's own order.
export function offered(d, leftOut, today) {
  const only = { milestones: (d && d.milestones) || [] };
  const ids = new Set(idsOf(pickable(only, leftOut, "")));
  const hidden = new Set(leftOut || []);
  const rows = milestoneRows(only.milestones.filter((m) => ids.has(m.id)), today, false);
  return rows.map((r) => ({ ...r, why: hidden.has(r.id) ? EYE : NOT_ON }));
}

const closed = (r) => r.state === "Achieved" || r.state === CANCELLED;
// Due, from the Agreed date: none when there is no agreed date; a closed milestone is "later"; overdue before today; soon within 7 days.
export function dueBucket(r, today) {
  if (!r.baseline || dayNumber(r.baseline) === null) return "none";
  if (closed(r)) return "later";
  if (r.baseline < today) return "overdue";
  return dayNumber(r.baseline) - dayNumber(today) <= 7 ? "soon" : "later";
}

export function fieldValue(r, f, today) {
  if (f === "status") return r.state;
  if (f === "page") return r.why;
  if (f === "client") return r.clientVisible ? "yes" : "no";
  return dueBucket(r, today);
}
export function options(f) {
  if (f === "status") return STATUS.map((s) => [s, s]);
  return f === "due" ? DUE : f === "page" ? PAGE : CLIENT;
}

// A filter is { sel: { field: [values] }, not: { field: true }, query }. A field with nothing ticked does not filter.
function passes(r, filter, today, skip) {
  return [...FIELDS, ...MORE].every((f) => {
    if (f === skip) return true;
    const c = (filter.sel && filter.sel[f]) || [];
    if (!c.length) return true;
    const has = c.includes(fieldValue(r, f, today));
    return filter.not && filter.not[f] ? !has : has;
  });
}
const inQuery = (r, q) => {
  const t = String(q || "").trim().toLowerCase();
  return !t || `${r.name} ${r.id} ${r.word}`.toLowerCase().includes(t);
};
export function shownRows(rows, filter, today) {
  return rows.filter((r) => passes(r, filter, today) && inQuery(r, filter.query));
}
// How many rows each value of field `f` would list with every other field's filter applied (the panel's count beside each value).
export function counts(rows, filter, f, today) {
  const L = rows.filter((r) => passes(r, filter, today, f));
  return options(f).map(([v]) => [v, L.filter((r) => fieldValue(r, f, today) === v).length]);
}
export const filtersOn = (filter) => [...FIELDS, ...MORE].filter((f) => ((filter.sel && filter.sel[f]) || []).length).length;
export const resultWords = (shown, total) => `Result: ${shown} of ${total} shown`;
export const selectedWords = (n) => (n ? `${n} selected` : "None selected");
export const addWords = (n) => (n ? `Add ${n}` : "Add selected");
export const toastWords = (n) => `${n} milestone${n === 1 ? "" : "s"} added to the page.`;
