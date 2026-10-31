// Add milestone (+) on the Milestones page (C-M3; prototype views.js #addMs). Edit only: it is one of the `tools` (edit/index.js), so
// a published file and View have none of it. One click adds a milestone called "New milestone", agreed 30 days from today (the local
// date), through the one writer (a `new` change for milestones: one step, one Undo, one line in the history), then puts focus on its
// name in the list with the name selected. The milestone peek (#42) is not on the page yet; once it is, open it here
// (openPeek(id, "milestone")) instead of focusing the row.
// It is a separate element so the Milestones header (C-M1) can take it: it sits at the header's right, beside the h1.
import { mode, fromFile, project } from "../stores/report.js";
import { addMilestone } from "../stores/changes.js";
import { NewTile } from "../components/NewTile.jsx";

export const WORD = "Add milestone";
export const NAME = "New milestone";
export const DAYS_OUT = 30;

// The local date `n` days from `from` (a Date, default now), as YYYY-MM-DD.
export function daysOut(n = DAYS_OUT, from = new Date()) {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate() + n);
  return `${String(d.getFullYear()).padStart(4, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Focus the new milestone's row in the list and select its name. The list shows 5 rows to start with, so the full list is opened if the row is not there.
function focusName(id, tries = 0) {
  const row = document.querySelector(`.msl-row[data-ms="${CSS.escape(id)}"]`);
  if (!row) {
    const all = document.querySelector('#milestones [data-msall="page"]');
    if (all && /^Show all/.test(all.textContent)) all.click();
    if (tries < 20) setTimeout(() => focusName(id, tries + 1), 50);
    return;
  }
  const cells = row.querySelector(".msl-cells"), name = row.querySelector(".msl-name");
  if (cells) cells.focus();
  if (name && window.getSelection) window.getSelection().selectAllChildren(name);
  if (row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
}

export async function add() {
  const id = await addMilestone({ name: NAME, baseline_date: daysOut() }, "Milestone added.");
  if (id) setTimeout(() => focusName(id), 0);
}

export function AddMilestone() {
  if (mode.value !== "edit" || fromFile.value || !project.value) return null;
  return <div class="ms-add" data-edit-only><NewTile word={WORD} kind="milestone" onAdd={add} id="addMs" /></div>;
}
