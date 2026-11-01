// Show archived on Work items (B-5, #126; Edit parts only, so a published file has none: it carries no archived row). A button
// with the count; on, a muted list of the archived actions, risks, issues and decisions, each marked Archived. A row opens
// read-only (its fields as they were, nothing to type into) with Restore, which puts the item back in one step with Undo.
// The list is read from GET /api/data?archived=only when the page opens the project and again whenever the project's data is
// read again (after a restore or an undo), so the count is always the database's.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { project, data } from "../stores/report.js";
import { getArchived } from "../api.js";
import { restoreItem } from "../stores/changes.js";
import { rowsFor } from "../logic/board.js";
import { KIND_WORDS, dueCell, ownerOf, metaOf, todayIso } from "../workItems.js";

const shown = signal(false);               // Show archived is on (kept for the visit, not in the database)

export function ArchivedItems() {
  const code = project.value, d = data.value;
  const [rows, setRows] = useState(null);  // null until read; [] when there is none
  const [open, setOpen] = useState("");
  useEffect(() => {
    let live = true;
    getArchived(code).then((r) => { if (live) setRows(r.ok ? rowsFor(r.data) : []); });
    return () => { live = false; };
  }, [code, d]);
  if (rows === null) return null;
  const n = rows.length, today = todayIso();
  return (
    <div class="archived" id="archived" data-edit-only>
      <button type="button" class="btn sm arch-pill" id="showArchived" aria-pressed={shown.value ? "true" : "false"} aria-controls="archived-list" onClick={() => { shown.value = !shown.value; }}>
        {`Show archived (${n})`}
      </button>
      {shown.value ? (
        <div id="archived-list" class="arch-box" role="region" aria-label="Archived work items">
          {n === 0 ? <p class="muted">No archived work items.</p> : (
            <ul class="arch-rows">
              {rows.map((r) => {
                const due = dueCell(r, today), isOpen = open === r.id;
                return (
                  <li key={r.id} data-id={r.id} class="arch-row">
                    <button type="button" class="arch-open" aria-expanded={isOpen ? "true" : "false"} onClick={() => setOpen(isOpen ? "" : r.id)}>
                      <span class="type">{KIND_WORDS[r.kind] || r.kind}</span>
                      <span class="t">{r.title}</span>
                      <span class="meta">{metaOf(r)}</span>
                      <span class="tag">Archived</span>
                    </button>
                    {isOpen ? (
                      <dl class="arch-read" aria-label={`${r.id}, read only`}>
                        <dt>Owner</dt><dd>{ownerOf(r.owner).text}</dd>
                        <dt>Due</dt><dd>{due.date}</dd>
                        <dt>Priority</dt><dd>{r.priority || "—"}</dd>
                        <dt>Status</dt><dd>{r.status}</dd>
                      </dl>
                    ) : null}
                    <button type="button" class="btn sm arch-restore" aria-label={`Restore ${r.id}`} onClick={() => restoreItem(r.table, r.id)}>Restore</button>
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
