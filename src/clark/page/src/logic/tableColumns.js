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

// Row 1534: the ORDER of the Work items columns. Unlike which columns are shown (above, this browser only), the order is saved with the project
// (projects.column_orders, a JSON object {actions|risks|decisions: [ids]}) and so is the order a client sees in the published file. One order for each
// type switch (Actions, Risks and issues, Decisions); "All" mixes types, so it keeps the standard order and cannot be moved. Only the shown columns
// are ordered. When the Status is shown it is first and the Item is second; a column cannot be moved into or before those two places.
export const ORDER_KEY = { action: "actions", risk: "risks", decision: "decisions" };
export const movable = (type) => Object.prototype.hasOwnProperty.call(ORDER_KEY, type);
const parsed = (columnOrders) => {
  try {
    const g = typeof columnOrders === "string" ? JSON.parse(columnOrders) : columnOrders;
    return g && typeof g === "object" && !Array.isArray(g) ? g : {};
  } catch (e) { return {}; }
};
/** The saved ids of one type from a project's column_orders (text or object); [] when there is none or it cannot be read. Never throws. */
export function savedOrder(columnOrders, type) {
  if (!movable(type)) return [];
  const list = parsed(columnOrders)[ORDER_KEY[type]];
  return Array.isArray(list) ? list.filter((x) => typeof x === "string") : [];
}
/** `shown` (the ids to draw, as shownIds gives them) in the saved order: the Status first (if shown), the Item next, then the saved ones that are shown, then any shown column the order does not name. */
export function inOrder(shown, saved) {
  const lead = ["status", "item"].filter((id) => shown.includes(id));
  const rest = shown.filter((id) => !lead.includes(id));
  const named = (saved || []).filter((id, i, a) => rest.includes(id) && a.indexOf(id) === i);
  return lead.concat(named, rest.filter((id) => !named.includes(id)));
}
/** The Classic Columns menu's lines (`defs` = the table's columns, `ordered` = the shown ids as the table draws them): the Status stays first, ticked or not (it is the table's fixed leading column), then the shown columns in the table's order, then the hidden ones in the standard order. */
export function menuLines(defs, ordered) {
  const named = ordered.filter((id) => id !== "status").map((id) => defs.find((c) => c.id === id)).filter(Boolean);
  const hidden = defs.filter((c) => c.id !== "status" && !ordered.includes(c.id));
  return defs.filter((c) => c.id === "status").concat(named, hidden);
}
/** `shown` in the order saved for `type`: only in the Classic look (`classic`); Cards (false) gets `shown` back as it is. */
export const shownOrder = (classic, shown, columnOrders, type) => (classic ? inOrder(shown, savedOrder(columnOrders, type)) : shown);
/** The ids after moving `id` one place (delta -1 or +1) or in front of `beforeId` (delta null; beforeId null = the end). The Status and the Item do not move and nothing goes in front of them; null when nothing changes. */
export function moveColumn(ids, id, delta, beforeId = null) {
  const fixed = (x) => x === "status" || x === "item", first = ids.filter(fixed).length, at = ids.indexOf(id);
  if (at < 0 || fixed(id)) return null;
  const rest = ids.filter((x) => x !== id);
  let to;
  if (delta !== null) to = Math.max(first, Math.min(rest.length, at + delta));
  else if (beforeId === null) to = rest.length;
  else { const b = rest.indexOf(beforeId); if (b < 0) return null; to = Math.max(first, b); }
  const next = rest.slice(0, to).concat(id, rest.slice(to));
  return next.every((x, i) => x === ids[i]) ? null : next;
}
/** The project's column_orders as an object, with `type`'s order set to `ids` (the shown columns, in order). The standard order is saved as nothing (the type's key is dropped), so the table follows any later change of the standard. Status and Item always lead the saved list, as the project's own check asks. */
export function withOrder(columnOrders, type, ids) {
  const all = { ...parsed(columnOrders) }, key = ORDER_KEY[type], rest = (list) => list.filter((x) => x !== "status" && x !== "item");
  const std = defsOf("work").map((c) => c.id).filter((x) => ids.includes(x));
  if (rest(ids).every((x, i) => x === rest(std)[i])) delete all[key]; else all[key] = ["status", "item"].concat(rest(ids));
  return all;
}
