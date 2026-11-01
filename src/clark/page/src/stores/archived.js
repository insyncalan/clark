// The archived work items (Edit's Show archived, #126) as the page holds them: the rows read from GET /api/data?archived=only for
// the open project, the "Show archived" choice, and the lookups the peek uses to open one read-only. They live here and never in
// the project's own data (stores/report.js `data`), so an archived row cannot reach the live lists, the counts, a published file,
// the export or Ask. Nothing in here fetches (edit/ArchivedItems.jsx reads), so report.js can import it without a cycle.
import { signal } from "@preact/signals";

const KEY = "clark.showArchived";

function saved() {
  try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; }      // storage can throw or be empty: the choice then holds for this visit only
}

// The choice is remembered in this browser (the prototype remembers it, views.js wArchOn), for every project.
export const showArchived = signal(saved());
export function setShowArchived(on) {
  showArchived.value = !!on;
  try { localStorage.setItem(KEY, on ? "1" : "0"); } catch (e) { /* kept for this visit */ }
}

// null until read; then { code, rows } as last read for that project. A row is a work item row (workItems.rowsOf) with `table`
// and `latest_update` added, sorted by id as the prototype lists them.
export const archivedItems = signal(null);

/** The archived rows of this project, or [] when none are read for it. */
export function archivedRows(code) {
  const a = archivedItems.value;
  return a && a.code === code ? a.rows : [];
}

/** One archived row of this project, or undefined. */
export function archivedRow(code, id) {
  return archivedRows(code).find((r) => r.id === id);
}
