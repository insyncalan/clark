// Checklist's rules (#96, G4): pure, no DOM and no Preact, shared by the view part and the Edit part. A line is typed (words and a
// ticked box) or linked to a work item by its id; a linked line's words and whether it is done are read live from the work item.
import { rowsOf, isOpen } from "../workItems.js";
import { keptRows, rulesFor } from "../logic/publishable.js";

export const MAX_ITEMS = 20;
export const TEXT_MAX = 200;
const LEFT_OUT = ["Cancelled", "Withdrawn"];      // a line for a work item that was called off has nothing left to do, so it is not drawn

export function itemsOf(section) {
  let list = null;
  if (section && typeof section.body === "string" && section.body) {
    try { const v = JSON.parse(section.body); list = v && Array.isArray(v.items) ? v.items : null; } catch (e) { list = null; }
  } else if (section && Array.isArray(section.items)) list = section.items;
  return (list || []).filter((i) => i && typeof i === "object" && (typeof i.item === "string" || typeof i.text === "string"));
}

export const bodyOf = (items) => JSON.stringify({ v: 1, items });

// The work items this page may show, by id: in the file every one it holds (publish kept them); in the served View the ones publish
// would keep (logic/publishable.js), so what View shows is what the client reads (FR-11).
export function shownWork(data, fromFile) {
  if (fromFile) return new Set(rowsOf(data || {}).map((r) => r.id));
  const rules = rulesFor({ code: data && data.project && data.project.code, hidden: ((data && data.report_hidden) || []).map((h) => (h && h.item_id) || h), labelRules: data && data.label_rules, labels: data && data.labels, sections: data && data.report_sections });
  return new Set(["actions", "raid", "decisions"].flatMap((k) => keptRows(data, k, rules).map((r) => r.id)));
}

// The lines to draw, in their stored order: { key, text, done, linked, id, n }. A linked line whose work item is not shown is left out.
export function linesOf(section, data, { fromFile = false } = {}) {
  const ok = shownWork(data, fromFile);
  const rows = new Map(rowsOf(data || {}).map((r) => [r.id, r]));
  const out = [];
  itemsOf(section).forEach((i, n) => {
    if (typeof i.item === "string") {
      const r = rows.get(i.item);
      if (!r || !ok.has(r.id) || LEFT_OUT.includes(r.status)) return;
      out.push({ key: i.item, text: r.title || r.id, done: !isOpen(r), linked: true, id: r.id, n });
    } else out.push({ key: `t${n}`, text: i.text, done: i.done === 1, linked: false, id: "", n });
  });
  return out;
}

export const countWords = (lines) => `${lines.filter((l) => l.done).length} of ${lines.length} done`;

export const problem = {
  text: `A line needs 1 to ${TEXT_MAX} characters. Type what is to be done.`,
  full: `A checklist can hold ${MAX_ITEMS} lines. Remove one first, then add the new one.`,
};
