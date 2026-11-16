// Row 1230: the add-a-milestone picker's rows and rules. It is the use-case picker's machine (logic/useCasePicker.js makePicker) with the milestone's
// fields. The milestones on offer are the ones off the page (taken off with the eye, or not for the client), as MsAddBack.offThePage finds them.
import { makePicker } from "./useCasePicker.js";
import { milestoneRows, showDate, todayIso } from "./milestones.js";
import { pickable, idsOf } from "./picker.js";

// Words the owner has not ruled on yet (row 1230). One constant each so a ruling is one edit.
export const WORDS = {
  title: "Add a milestone from your project record",
  search: "Search by name, ID or state",
  where: "Where it is",
  off: "Taken off the page",
  noClient: "On the page, not shown to the client",
  onPage: "On the page",
  clientVisible: "Client-visible",
  due: "Due",
  yes: "Yes",
  no: "No",
};
export const COLUMNS = [["name", "Milestone"], ["state", "State"], ["agreed", "Agreed"], ["expected", "Expected or achieved"], ["progress", "Progress"], ["where", WORDS.where], ["id", "ID"]];

const yes = (b) => (b ? WORDS.yes : WORDS.no);
// A date to sort by: DD-MM-YYYY written backwards, so the Due list runs from the earliest day.
const byDay = (v) => String(v).split("-").reverse().join("-");

export const FIELDS = [
  { key: "state", label: "Status", get: (r) => r.state },
  { key: "agreed", label: WORDS.due, get: (r) => (r.baseline ? r.agreed : ""), sort: byDay },
  { key: "onPage", label: WORDS.onPage, more: true, get: (r) => yes(r.onPage) },
  { key: "client", label: WORDS.clientVisible, more: true, get: (r) => yes(r.clientVisible) },
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
    return {
      ...r, onPage,
      agreed: r.baseline ? showDate(r.baseline) : "No agreed date",
      expected: r.state === "Achieved" && !r.achieved ? "Achieved, date not recorded" : date ? showDate(date) : "",
      progress: r.percent === null || r.percent === undefined ? "" : `${Math.max(0, Math.min(100, Math.round(r.percent)))}%`,
      where: onPage ? WORDS.noClient : WORDS.off,
    };
  });
}

/** What the table needs to be the milestone picker (components/PickerTable.jsx `kind`): the rules, the columns, the search words, and a tick in the header in place of a Select all shown button. */
export const MS_KIND = { L: MS, columns: COLUMNS, search: WORDS.search, tick: true };
