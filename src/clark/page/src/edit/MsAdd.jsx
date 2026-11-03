// Add milestone (#458; the prototype's "+" on the Milestones page, views.js). It adds "New milestone", agreed 30 days from today, in
// the project's first workstream, and opens it in the peek; the toast says so, with Undo. Edit's page only (edit/index.js `tools`): a
// published file has no button and nothing here.
import { data, openPeek } from "../stores/report.js";
import { NewTile } from "../components/NewTile.jsx";
import { addDays, todayIso } from "../logic/milestones.js";
import { addRow } from "./newRows.js";
import { ADD_MILESTONE, NEW_MILESTONE, TOAST_MILESTONE } from "./movementWords.js";

let busy = false;

async function add() {
  if (busy) return;
  busy = true;
  try {
    const ws = ((data.value && data.value.workstreams) || []).find((w) => w.status !== "Closed" && !w.archived);
    const values = { name: NEW_MILESTONE, baseline_date: addDays(todayIso(), 30) };
    if (ws && ws.name) values.workstream = ws.name;
    const reply = await addRow("milestones", values, () => TOAST_MILESTONE);
    if (reply && reply.ref) openPeek(reply.ref, "milestone");
  } finally {
    busy = false;
  }
}

export function MsAdd() {
  return <NewTile word={ADD_MILESTONE} kind="milestone" id="addMs" onAdd={add} />;
}
