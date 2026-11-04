// Item 449: the working titles Add gives a new work item (edit/addItem.js), kept in this one place, and the items the client would
// see that still have one. Every work item is client-visible by default (D-3), so the Publish dialog (edit/Publish.jsx) warns while
// any such item is left: a warning, not a block. Pure: no DOM, no Preact.
import { rulesOf } from "../templates/raid.js";
import { publishable } from "./publishable.js";

export const PLACEHOLDER_TITLES = { action: "New action", risk: "New risk", issue: "New issue", decision: "New decision" };
const TABLE_OF = { action: "actions", risk: "raid", issue: "raid", decision: "decisions" };

/** The work items in `d` (the project's data) that would be published with their kind's placeholder title, in the data's order. */
export function placeholderItems(d) {
  const rules = rulesOf(d), out = [];
  const add = (kind, row, title) => {
    if (TABLE_OF[kind] && title === PLACEHOLDER_TITLES[kind] && publishable(row, TABLE_OF[kind], rules)) out.push({ id: row.id, title });
  };
  for (const r of (d && d.actions) || []) add("action", r, r.description);
  for (const r of (d && d.raid) || []) add(String(r.type || "").toLowerCase(), r, r.description);
  for (const r of (d && d.decisions) || []) add("decision", r, r.decision);
  return out;
}

/** The Publish dialog's line about them, or "" when there are none. */
export function placeholderWarning(items) {
  const n = items.length;
  if (!n) return "";
  return n === 1
    ? `1 work item still has a placeholder title (${items[0].title}) and will be shown to the client. Rename it or turn off its eye first.`
    : `${n} work items still have a placeholder title (such as ${items[0].title}) and will be shown to the client. Rename them or turn off their eye first.`;
}
