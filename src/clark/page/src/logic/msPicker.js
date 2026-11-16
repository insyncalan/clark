// Row 1230: the add-a-milestone picker's rows and rules. It is the use-case picker's machine (logic/useCasePicker.js makePicker) with the milestone's
// fields. The milestones on offer are the ones off the page (taken off with the eye, or not for the client), as MsAddBack.offThePage finds them.
import { makePicker } from "./useCasePicker.js";
import { milestoneRows, showDate, todayIso, STATES, CANCELLED } from "./milestones.js";
import { DUE, CLIENT_WORDS } from "../filters.js";
import { dayNumber } from "../workItems.js";
import { pickable, idsOf } from "./picker.js";

// The words of row 1230. The ones marked ruled have been ruled by the owner. One constant each so a later ruling is one edit.
export const WORDS = {
  title: "Add a milestone from your project record",   // #1230 'Add picker' text
  search: "Search by name, ID or state",               // ruled
  where: "Where it is",                                // ruled (column head)
  off: "Taken off with the eye",                       // ruled: the 'Where it is' cell and the On the page filter value
  notOn: "Not on the page",                            // ruled: the 'Where it is' cell and the On the page filter value (on the page, not for the client)
  noDate: "No agreed date",                            // existing: logic/milestones.js, ArchivedPeek.jsx
  onPage: "On the page",                               // the field's name, from the mock-up (not in the ruling: UNRULED)
  clientVisible: "Client visible",                     // ruled, no hyphen
  due: "Due",                                          // the field's name, from the mock-up (UNRULED)
  findField: "Find a field…",                          // ruled (panel search)
  set: "set",                                          // ruled (marker on a field that has a filter)
};
// Aria words (ruled): the filter button's name, with the badge's count when filters are on; a row's tick.
export const filtersLabel = (n) => (n ? `Filters, ${n} on` : "Filters");
export const tickLabel = (r) => `Add ${r.name}`;
export const COLUMNS = [["name", "Milestone"], ["state", "State"], ["agreed", "Agreed"], ["expected", "Expected or achieved"], ["progress", "Progress"], ["where", WORDS.where], ["id", "ID"]];

const dueWords = Object.fromEntries(DUE);   // the Work items filter's Due buckets: Overdue, Due in 7 days, No date, Later (filters.js)

export const FIELDS = [
  { key: "state", label: "Status", get: (r) => r.state, fixed: [...STATES, CANCELLED] },       // every state, as the mock-up lists them (0 where none)
  { key: "agreed", label: WORDS.due, get: (r) => r.due, fixed: DUE.map(([, w]) => w) },
  { key: "onPage", label: WORDS.onPage, more: true, get: (r) => r.where, fixed: [WORDS.notOn, WORDS.off] },
  { key: "client", label: WORDS.clientVisible, more: true, get: (r) => (r.clientVisible ? CLIENT_WORDS.yes : CLIENT_WORDS.no), fixed: [CLIENT_WORDS.yes, CLIENT_WORDS.no] },
];
export const MS = makePicker({ fields: FIELDS, hay: (r) => [r.name, r.id, r.state], addWord: "Add selected" });

/** The milestones off the page, as table rows: the display row of milestoneRows plus the words each column shows. `left` is the ids taken off with the eye. */
export function offered(data, left, today = todayIso()) {
  const only = { milestones: (data && data.milestones) || [] };
  const ids = new Set(idsOf(pickable(only, left, "")));
  const taken = new Set(Array.from(left || []));
  return milestoneRows(only.milestones, today).filter((r) => ids.has(r.id)).map((r) => {
    const onPage = !taken.has(r.id);
    const date = r.state === "Achieved" ? r.achieved : r.expected || r.forecast || r.baseline;
    const due = !r.baseline ? "none" : r.state === "Achieved" || r.state === CANCELLED ? "later" : dayNumber(r.baseline) < dayNumber(today) ? "overdue" : dayNumber(r.baseline) - dayNumber(today) <= 7 ? "soon" : "later";   // the mock-up's rule
    return {
      ...r, onPage, due: dueWords[due],
      agreed: r.baseline ? showDate(r.baseline) : WORDS.noDate,
      expected: r.state === "Achieved" && !r.achieved ? "Achieved, date not recorded" : date ? showDate(date) : "",
      progress: r.percent === null || r.percent === undefined ? "" : `${Math.max(0, Math.min(100, Math.round(r.percent)))}%`,
      where: onPage ? WORDS.notOn : WORDS.off,
    };
  });
}

/** What the table needs to be the milestone picker (components/PickerTable.jsx `kind`): the rules, the columns, the search words, and a tick in the header in place of a Select all shown button. */
export const MS_KIND = {
  L: MS, columns: COLUMNS, search: WORDS.search, tick: true, marks: true,
  isNotButtons: true,                       // the match is "is" and "is not" as two buttons with "any of" after them (mock-up f6)
  findField: WORDS.findField, mark: WORDS.set, filtersLabel, tickLabel,
};
