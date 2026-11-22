// Row 1222: which columns a work item table or a milestone table shows. The choice is made from a menu on the table's heading row (edit/ColumnsMenu.jsx).
// It is kept for each table and each project, on this computer only (logic/remember.js: a blocked store means nothing is remembered and the table
// still draws), never in the project's data, and the Excel export does not read it. The standard set is what a table showed before this row.
// A column marked `locked` is always shown: the title (or name) and the status, so a row can always be understood. Row 1499: on Work items only the title is locked (the Status can be unticked in the Classic look; Cards keeps it always shown, edit/ColumnsMenu.jsx).
import { recall, remember, forget } from "./remember.js";

export const TABLE_COLUMNS = {
  work: [
    { id: "status", label: "Status", standard: true },
    { id: "item", label: "Item", locked: true, standard: true },
    { id: "owner", label: "Owner", standard: true },
    { id: "due", label: "Due", standard: true },
    { id: "prio", label: "Priority", standard: true },
    { id: "id", label: "Id", standard: true }, { id: "type", label: "Type" }, { id: "workstream", label: "Workstream" }, { id: "milestone", label: "Milestone" },
    { id: "raised", label: "Raised" }, { id: "closed", label: "Closed" }, { id: "usecase", label: "Use case" }, { id: "labels", label: "Labels" },
    { id: "latest", label: "Latest update" }, { id: "wording", label: "Client wording" },
  ],
  // Row 1325: the Use cases page. Use case and Status are locked; the order here is the order of the columns and of the menu; Commitment, Release and On the dashboard start off.
  uc: [
    { id: "item", label: "Use case", locked: true, standard: true },
    { id: "where", label: "Where it stands", standard: true },
    { id: "status", label: "Status", locked: true, standard: true },
    { id: "owner", label: "Owner", standard: true },
    { id: "steps", label: "Next steps", standard: true },
    { id: "ms", label: "Milestone", standard: true },
    { id: "cm", label: "Commitment" }, { id: "rel", label: "Release" }, { id: "dash", label: "On the dashboard" },
  ],
  // Row 1230 ruling: the Milestones page keeps its list as it was ("milestones"); only the Dashboard section's is the five column table ("msDash").
  milestones: [
    { id: "date", label: "Date", standard: true },
    { id: "name", label: "Milestone", locked: true, standard: true },
    { id: "state", label: "State", locked: true, standard: true },
    { id: "prog", label: "Progress", standard: true },
    { id: "id", label: "Id" }, { id: "description", label: "Description" }, { id: "workstream", label: "Workstream" }, { id: "owner", label: "Owner" },
    { id: "agreed", label: "Agreed" }, { id: "forecast", label: "Forecast" }, { id: "order", label: "Order" }, { id: "reason", label: "State reason" },
  ],
  msDash: [
    { id: "name", label: "Milestone", locked: true, standard: true },
    { id: "state", label: "State", locked: true, standard: true },
    { id: "agreed", label: "Agreed", standard: true },
    { id: "date", label: "Expected or achieved", standard: true },
    { id: "prog", label: "Progress", standard: true },
    { id: "id", label: "Id" }, { id: "description", label: "Description" }, { id: "workstream", label: "Workstream" }, { id: "owner", label: "Owner" },
    { id: "forecast", label: "Forecast" }, { id: "order", label: "Order" }, { id: "reason", label: "State reason" },
  ],
};

export const defsOf = (table) => TABLE_COLUMNS[table] || [];
export const standardIds = (table) => defsOf(table).filter((c) => c.standard).map((c) => c.id);

/** The ids to draw, in the table's own order: what was chosen, plus the locked ones; anything unknown is ignored. Nothing usable chosen: the standard set. */
export function shownIds(table, chosen) {
  if (!Array.isArray(chosen)) return standardIds(table);
  const set = new Set(chosen.filter((c) => typeof c === "string"));
  const got = defsOf(table).filter((c) => c.locked || set.has(c.id)).map((c) => c.id);
  return got.length ? got : standardIds(table);
}

/** The ids after pressing `id` in the menu: on becomes off and off becomes on; a locked column does not change. */
export function toggled(table, shown, id) {
  const def = defsOf(table).find((c) => c.id === id);
  if (!def || def.locked) return shownIds(table, shown);
  const now = new Set(shownIds(table, shown));
  if (now.has(id)) now.delete(id); else now.add(id);
  return shownIds(table, [...now]);
}

export const isStandard = (table, shown) => {
  const a = shownIds(table, shown), b = standardIds(table);
  return a.length === b.length && a.every((id, i) => id === b[i]);
};

const keyOf = (table, project) => `cols.show.${table}.${project || "none"}`;
export const readChoice = (table, project) => shownIds(table, recall(keyOf(table, project), null));
/** Kept for this table and this project in this browser; the standard set is kept as nothing at all (the key is taken away), so the table follows any later change of the standard. */
export const writeChoice = (table, project, shown) => (isStandard(table, shown) ? forget(keyOf(table, project)) : remember(keyOf(table, project), shownIds(table, shown)));
