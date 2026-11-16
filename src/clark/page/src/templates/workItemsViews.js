// Work items list (row 1268, slice saved-view tabs): the pure rules of the tabs row in Edit. Pure: no DOM, no store.
// A saved view is { id, name, line } as on the Work items page (logic/filterLine.js, page "workitemslist"); the line is the words of
// templates/workItemsLine.js. Clicking a tab puts the view's choices on the list's filter (Most rows, columns, sort and caption stay);
// the filter is saved at once as always, so the view only says which choices to start from and whether the list has moved off them.
import { lineOf, readLine } from "./workItemsLine.js";

export const PAGE = "workitemslist";
export const NEEDS_NAME = "Give the view a name.";

const norm = (s) => String(s == null ? "" : s).split(/\s+/).filter(Boolean).join(" ").toLowerCase();

// The filter a view gives, built on the current one; { filter } or { problem } (a view whose words the list cannot read).
export function applyView(view, current, known = []) {
  return readLine(view ? view.line : "", current, known);
}

// The line the filter reads as, in the form views are compared in.
export const lineKey = (filter, nameOf) => norm(lineOf(filter, nameOf));

// Which tab is on and whether it has the dot: `activeId` is the tab the person picked (kept by the page); with none, the first view whose
// line the filter reads as is on. The dot shows when the on tab's line is not the filter's line.
export function tabState(views, filter, activeId, nameOf) {
  const now = lineKey(filter, nameOf);
  const picked = (views || []).find((v) => v.id === activeId);
  const active = picked || (views || []).find((v) => norm(v.line) === now) || null;
  return { active, dot: !!active && norm(active.line) !== now };
}
