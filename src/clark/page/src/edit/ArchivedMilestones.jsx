// Show archived on Milestones (C-M4, #126; Edit parts only, so a published file has none: it carries no archived row). A button
// with the count; on, a box called Archived with the archived milestones in muted text, each marked Archived, with its agreed date
// and how many work items are still linked to it. A row is read only: Restore is its one action, and it puts the milestone back in
// one step with one Undo. Restore is offered in Edit only (View changes nothing, and its changes have no Undo to offer).
// The rows are read from GET /api/data?archived=only, into this block's own state and never into the page's data, so an archived
// row cannot reach the Plan, the published file, the export or Ask. They are read again whenever the project's data is read again
// (after a restore or an undo). If a read fails, the rows last read for this project stay; with none yet, the button is left out
// rather than say 0. A project change clears the rows.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { project, data, mode } from "../stores/report.js";
import { getArchivedMilestones } from "../api.js";
import { restoreMilestone } from "../stores/changes.js";
import { plural, showDate } from "../logic/milestones.js";

const shown = signal(false);               // Show archived is on (kept for the visit, not in the database)

export function linkedCount(d, id) {
  return [...((d && d.actions) || []), ...((d && d.raid) || [])].filter((r) => r.milestone === id).length;
}

export function ArchivedMilestones() {
  const code = project.value, d = data.value, editing = mode.value === "edit";
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
  const rows = got && got.code === code ? got.list : null;
  if (rows === null) return null;
  const n = rows.length, on = shown.value;
  const restore = (r) => restoreMilestone(r.id, r.name).then((reply) => {
    if (reply) setTimeout(() => { const b = document.getElementById("ms-archived-pill"); if (b) b.focus(); }, 0);
    return reply;
  });
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
                    <span class="ma-name">{r.name}</span>
                    <span class="tag">Archived</span>
                    <span class="ma-meta">{`${r.baseline_date ? `Agreed ${showDate(r.baseline_date)}` : "No agreed date"} · ${plural(linked, "work item")} still linked`}</span>
                    {editing ? <button type="button" class="btn sm ma-restore" data-edit-only aria-label={`Restore ${r.name}`} onClick={() => restore(r)}>Restore</button> : null}
                  </li>
                );
              })}
            </ul>
          )}
          {n > 0 && !editing ? <p class="muted ma-note">To put one back, switch to Edit.</p> : null}
        </div>
      ) : null}
    </div>
  );
}
