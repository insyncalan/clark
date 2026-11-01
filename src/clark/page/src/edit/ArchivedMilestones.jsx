// Show archived on Milestones (C-M4, #126; Edit parts only, so a published file has none: it carries no archived row). A button
// with the count; on, a box called Archived with the archived milestones in muted text, each marked Archived, with its agreed date
// and how many work items are still linked to it. A row is read only: its name is a button that opens the milestone read only in a
// peek (edit/ArchivedPeek.jsx, #436 row 23), and Restore is there, not on the row: one step with one Undo. Restore is offered in
// Edit only (View changes nothing, and its changes have no Undo to offer), so in View the peek says to switch to Edit.
// The rows are read from GET /api/data?archived=only, into this block's own state and never into the page's data, so an archived
// row cannot reach the Plan, the published file, the export or Ask. They are read again whenever the project's data is read again
// (after a restore or an undo). If a read fails, the rows last read for this project stay; with none yet, the button is left out
// rather than say 0. A project change clears the rows.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { project, data, peek, closePeek } from "../stores/report.js";
import { getArchivedMilestones } from "../api.js";
import { plural, showDate } from "../logic/milestones.js";
import { archivedOpen, linkedCount } from "./archivedState.js";

export { linkedCount };
const shown = signal(false);               // Show archived is on (kept for the visit, not in the database)

export function ArchivedMilestones() {
  const code = project.value, d = data.value;
  const [got, setGot] = useState(null);     // null, or { code, list } as last read
  useEffect(() => {
    let live = true;
    getArchivedMilestones(code).then((r) => {
      if (!live) return;
      if (r.ok) setGot({ code, list: r.rows });
      else setGot((g) => (g && g.code === code ? g : null));
    });
    return () => { live = false; };
  }, [code, d]);
  useEffect(() => () => { archivedOpen.value = null; }, []);       // leaving the page shuts the peek of an archived milestone
  const rows = got && got.code === code ? got.list : null;
  if (rows === null) return null;
  const n = rows.length, on = shown.value;
  const look = (r, e) => {
    if (peek.value) closePeek();                                  // the page's own peek and this one never stand together
    archivedOpen.value = { code, row: r, opener: e.currentTarget };
  };
  return (
    <div class="ma" id="ms-archived">
      <button type="button" class="btn sm ma-pill" id="ms-archived-pill" aria-pressed={on ? "true" : "false"} aria-controls={on ? "ms-archived-list" : undefined} onClick={() => { shown.value = !on; }}>
        {`Show archived (${n})`}
      </button>
      {on ? (
        <div id="ms-archived-list" class="ma-box" role="region" aria-label="Archived milestones">
          <h2 class="ma-h">Archived <span class="muted">{plural(n, "milestone")}</span></h2>
          {n === 0 ? <p class="muted">No archived milestones.</p> : (
            <ul class="ma-rows">
              {rows.map((r) => {
                const linked = linkedCount(d, r.id);
                return (
                  <li key={r.id} data-id={r.id} class="ma-row">
                    <button type="button" class="link ma-name" data-ma-open={r.id} aria-label={`${r.name}, archived`} onClick={(e) => look(r, e)}>{r.name}</button>
                    <span class="tag">Archived</span>
                    <span class="ma-meta">{`${r.baseline_date ? `Agreed ${showDate(r.baseline_date)}` : "No agreed date"} · ${plural(linked, "work item")} still linked`}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
