// Show archived on Work items (B-5, #126, #450 row 38; Edit parts only, so a published file has none: it carries no archived row and
// never reads the choice). As in the prototype (views.js, the Work items bar): a "Show archived N" pill in the bar, beside View,
// that remembers the choice for each project in this browser (localStorage, wrapped: it can throw or be blocked, and the page then
// keeps the choice for the visit only). On, a muted list under the table of the archived actions, risks, issues and decisions, each
// marked Archived. A row opens read-only (its fields as they were, nothing to type into) with Restore, which puts the item back in
// one step with Undo.
// The list is read from GET /api/data?archived=only when the page opens the project and again whenever the project's data is
// read again (after a restore or an undo), so the count is always the database's. ArchivedItems, under the list, does the read;
// ArchivedPill, in the bar, shows its count.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { project, data } from "../stores/report.js";
import { getArchived } from "../api.js";
import { restoreItem } from "../stores/changes.js";
import { rowsFor } from "../logic/board.js";
import { KIND_WORDS, dueCell, ownerOf, metaOf, todayIso } from "../workItems.js";

const KEY = (code) => `clark.workArchived.${code}`;
const kept = signal({});                   // project code -> on, once read or set in this visit
const read = signal({ code: "", rows: null }); // the archived rows of one project; rows null until read, [] when there is none

function storedOn(code) {
  try { return window.localStorage.getItem(KEY(code)) === "on"; } catch (e) { return false; }
}
export function archivedOn(code) {
  const k = kept.value;
  return Object.prototype.hasOwnProperty.call(k, code) ? k[code] : storedOn(code);
}
function setOn(code, on) {
  kept.value = { ...kept.value, [code]: on };
  try { if (on) window.localStorage.setItem(KEY(code), "on"); else window.localStorage.removeItem(KEY(code)); } catch (e) { /* kept for the visit only */ }
}
const rowsOf = (code) => (read.value.code === code ? read.value.rows : null);

export function ArchivedPill() {
  const code = project.value, rows = rowsOf(code);
  if (!code || rows === null) return null;
  const on = archivedOn(code);
  return (
    <button type="button" class="arch-pill" id="showArchived" aria-pressed={on ? "true" : "false"} aria-controls="archived" onClick={() => setOn(code, !on)}>
      Show archived <em class="num" key={rows.length}>{rows.length}</em>
    </button>
  );
}

export function ArchivedItems({ pill }) {
  const code = project.value, d = data.value;
  const [open, setOpen] = useState("");
  useEffect(() => {
    let live = true;
    getArchived(code).then((r) => { if (live) read.value = { code, rows: r.ok ? rowsFor(r.data) : [] }; });
    return () => { live = false; };
  }, [code, d]);
  const rows = rowsOf(code);
  if (rows === null) return null;
  const n = rows.length, today = todayIso(), on = archivedOn(code);
  return (
    <div class="archived" id="archived" data-edit-only>
      {pill ? <div class="wbar"><ArchivedPill /></div> : null}   {/* no live items, so no bar: the pill stands on its own */}
      {on ? (
        <div id="archived-list" class="arch-box" role="region" aria-label="Archived work items">
          <h2 class="arch-h">Archived <span class="muted">{`${n} item${n === 1 ? "" : "s"}`}</span></h2>
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
