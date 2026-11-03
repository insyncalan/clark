// The list the peek steps through: the rows the Work items page shows now (filters and order as drawn), as ids. A peek opened by
// an address (a reload, a link) steps through the same list. A milestone steps through the project's milestones in their order.
import { filterState, filterCtx, data, fromFile, asAt } from "../stores/report.js";
import { sortRows, todayIso } from "../workItems.js";
import { applyFilters, isPublished } from "../filters.js";
import { lineApi } from "../stores/lineSlot.js";
import { work, itemRows, contextFor } from "../stores/work.js";
import { boardGroup, columnsFor, cellOf, isCollapsed } from "../logic/board.js";

// The order is the one drawn: grouped as the list is (a collapsed group's rows are not on the page, so not stepped through).
export function itemIds() {
  const today = todayIso(), w = work.value, L = lineApi.current;
  // A published file keeps the older filter bar (its Due filter has "Earlier"), so it steps with that bar's rows; the app steps with the line's.
  const old = isPublished() || fromFile.value || !L;
  const st = old ? filterState.value : L.toState(itemRows.value, filterCtx());
  const rows = old ? applyFilters(itemRows.value, st, fromFile.value && asAt.value ? asAt.value : today) : L.apply(itemRows.value, filterCtx());
  const g = w.view === "board" ? boardGroup(w.group) : w.group;
  if (g === "nothing") return sortRows(rows, today).map((r) => r.id);
  const ctx = contextFor(today, st.type);
  return columnsFor(g, rows, ctx).flatMap((c) => (isCollapsed(w, g, c.key) ? [] : sortRows(rows.filter((r) => cellOf(g, r, ctx) === c.key), today))).map((r) => r.id);
}

export function milestoneIds() {
  return ((data.value && data.value.milestones) || []).map((m) => m.id);
}

/** {prev, next} ids around `id` in `ids`; either is "" at an end, and both are "" when `id` isn't in the list. */
export function around(ids, id) {
  const i = ids.indexOf(id);
  return i < 0 ? { prev: "", next: "" } : { prev: ids[i - 1] || "", next: ids[i + 1] || "" };
}

/** {at, count}: where `id` is in `ids` (0-based; -1 when it is not there) and how many there are. */
export function placeIn(ids, id) {
  return { at: ids.indexOf(id), count: ids.length };
}
