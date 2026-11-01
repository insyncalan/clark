// Show archived on Work items (B-5, #126; Edit parts only, so a published file has none: it carries no archived row).
// The pill sits in the bar beside the layout switch with the count and the archive icon; the choice is remembered in this browser
// (stores/archived.js). On, a box called Archived lists the archived actions, risks, issues and decisions in muted text, each marked
// Archived. A row opens in the side peek, read only, with one Restore (edit/ArchivedPeek.jsx), as the prototype does
// (system/prototype/views.js archHtml and peek.js archHtml); nothing is expanded in place and the row has no Restore of its own.
// The rows are read from GET /api/data?archived=only when the page opens the project and again whenever the project's data is read
// again (after a restore or an undo), into stores/archived.js and never into the project's data, so an archived row cannot reach the
// live lists, the counts, a published file, the export or Ask. If a read fails the rows last read for this project stay; with none yet
// there is no pill rather than a wrong count.
import { useEffect } from "preact/hooks";
import { project, data, openPeek, peek } from "../stores/report.js";
import { getArchived } from "../api.js";
import { rowsFor } from "../logic/board.js";
import { archivedItems, archivedRows, showArchived, setShowArchived } from "../stores/archived.js";
import { Icon } from "../components/Icon.jsx";
import { KIND_WORDS, dueCell, ownerOf, metaOf, todayIso } from "../workItems.js";

// The archived rows as work item rows. The names of milestones and use cases come from the live data plus the archived milestones
// that came with the read (an archived item keeps its link to an archived milestone). `latest_update` is kept for the peek.
function build(archived, live) {
  const named = { ...archived, milestones: [...((live && live.milestones) || []), ...(archived.milestones || [])], use_cases: (live && live.use_cases) || archived.use_cases || [] };
  const update = {};
  for (const r of archived.actions || []) update[r.id] = r.latest_update || "";
  return rowsFor(named).map((r) => ({ ...r, latest_update: update[r.id] || "" })).sort((a, b) => a.id.localeCompare(b.id));
}

// The Show archived button for the bar. Nothing until the rows have been read for this project.
export function ArchivedPill() {
  const code = project.value, a = archivedItems.value;
  if (!a || a.code !== code) return null;
  const on = showArchived.value;
  return (
    <button type="button" class="arch-pill" id="showArchived" aria-pressed={on ? "true" : "false"} aria-controls={on ? "archived-list" : undefined} onClick={() => setShowArchived(!on)}>
      <Icon name="archive" />{"Show archived "}<em class="num">{a.rows.length}</em>
    </button>
  );
}

// Reads the archived rows, and draws the list when Show archived is on.
export function ArchivedItems() {
  const code = project.value, d = data.value;
  useEffect(() => {
    let live = true;
    getArchived(code).then((r) => {
      if (!live) return;
      if (r.ok) archivedItems.value = { code, rows: build(r.data, data.value) };
      else if (archivedItems.value && archivedItems.value.code !== code) archivedItems.value = null;
    });
    return () => { live = false; };
  }, [code, d]);
  const a = archivedItems.value;
  if (!a || a.code !== code || !showArchived.value) return null;
  const rows = archivedRows(code), n = rows.length, today = todayIso(), open = peek.value && peek.value.id;
  const go = (id) => openPeek(id, "item");
  return (
    <div class="archived arch-box" id="archived-list" data-edit-only role="region" aria-label="Archived work items">
      <h2 class="arch-h">Archived <span>{`${n} ${n === 1 ? "item" : "items"}`}</span></h2>
      {n === 0 ? <p class="muted">No archived items.</p> : (
        <table class="items arch">
          <thead><tr><th class="c-type">Type</th><th class="c-item">Item</th><th class="c-owner">Owner</th><th class="c-due">Due</th><th class="c-status">Status</th><th class="c-arch"><span class="sr">Archived</span></th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} data-id={r.id} class={`arch${open === r.id ? " sel" : ""}`} tabIndex={0} aria-label={`Open ${r.id}, archived`}
                onClick={() => go(r.id)} onKeyDown={(e) => { if (e.key === "Enter" && e.target === e.currentTarget) { e.preventDefault(); go(r.id); } }}>
                <td class="c-type"><span class={`type k-${r.kind}`}>{KIND_WORDS[r.kind] || r.kind}</span></td>
                <td class="c-item"><span class="t">{r.title}</span><span class="meta">{metaOf(r)}</span></td>
                <td class="c-owner">{ownerOf(r.owner).text}</td>
                <td class="c-due num">{dueCell(r, today).date}</td>
                <td class="c-status">{r.status}</td>
                <td class="c-arch"><span class="tag arch"><Icon name="archive" />Archived</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
