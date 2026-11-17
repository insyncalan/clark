// The Dashboard's Milestones section, as plain functions (row 1230): which milestones it holds, and the view setting it keeps in its body.
// The section, the Configure box and the tests all call dashRows, so "of N" in Configure is the number of rows the section can draw.
import { milestoneRows } from "./milestones.js";
import { leftOutIds } from "./picker.js";
import { MILESTONES_VIEW, viewOf } from "./useCaseView.js";

// The milestones the Dashboard draws: client visible and not left out of the published page (the same filter MsBlock applies).
export function dashRows(d, today, client) {
  const left = new Set(leftOutIds(d));
  return milestoneRows(d.milestones, today, client).filter((r) => r.clientVisible && !left.has(r.id));
}

// The section's view: { set, n, scroll, tracker }; a section with no setting keeps 5, no scroll and the tracker at the bottom.
export const msViewOf = (section, fromFile) => viewOf(section, fromFile, MILESTONES_VIEW);
