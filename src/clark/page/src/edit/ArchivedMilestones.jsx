// Show archived on Milestones (C-M4, #126; Edit parts only, so a published file has none: it carries no archived row). A button
// with the count; on, a box called Archived with the archived milestones in muted text, each marked Archived, with its agreed date
// and how many work items are linked to it (none said when there are none). A row is read only: its name is a button that opens the
// milestone read only in a peek (edit/ArchivedPeek.jsx, #436 row 23), and Restore is there, not on the row: one step with one Undo.
// The Milestones page is always editable (View and Edit exist only on the Dashboard), so Restore is offered in both modes.
// The rows are read from GET /api/data?archived=only, into this block's own state and never into the page's data, so an archived
// row cannot reach the Plan, the published file, the export or Ask. They are read again whenever the project's data is read again
// (after a restore or an undo). If a read fails, the rows last read for this project stay; with none yet, the button is left out
// rather than say 0. With 0 archived milestones the button and the box are both left out (row 822); the first archived milestone
// brings them back. A project change clears the rows.
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
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
  const had = useRef(0);                                          // the count last drawn: the last one restored takes the button away (row 822)
  useEffect(() => {
    const n0 = rows ? rows.length : 0;
    if (had.current > 0 && n0 === 0) {                            // focus would fall to the page body: put it on the page's heading
      const h = document.querySelector("#milestones h1");
      if (h) { h.setAttribute("tabindex", "-1"); h.focus(); }
    }
    had.current = n0;
  });
  if (rows === null) return null;
  const n = rows.length, on = shown.value;
  if (n === 0) return null;                                       // nothing archived: no button, no empty box (row 822)
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
                    <span class="ma-meta">{`${r.baseline_date ? `Agreed ${showDate(r.baseline_date)}` : "No agreed date"}${linked > 0 ? ` · ${plural(linked, "work item")} linked` : ""}`}</span>
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
