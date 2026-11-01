// The AI list for one editor: what the bubble's AI zone, the toolbar's AI button and Alt+/ all show. ONE function gives it,
// so every place that opens the list shows the same thing. Plain JS, no DOM. The menu itself is logic/aiMenu.js.
//   aiEntries(place, { paragraphs, selected, canMake, hasText })
//     -> [{ key, type: "option" | "make" | "ask", id, name, line, group }] in the menu's order, Ask… last.
//   Format notes only for several paragraphs; Make into only for a chosen passage (and only where the page can make an item).
import { menu } from "./aiMenu.js";

export function aiEntries(place, { paragraphs = 1, selected = false, canMake = false } = {}) {
  const m = menu(place);
  if (!m) return [];
  const out = [];
  for (const g of m.groups) for (const i of g.items) out.push({ key: i.id, type: "option", id: i.id, name: i.name, line: i.line, group: g.label });
  if (m.format_notes && paragraphs > 1) out.push({ key: m.format_notes.id, type: "option", id: m.format_notes.id, name: m.format_notes.name, line: m.format_notes.line, group: "" });
  if (selected && canMake) for (const i of m.make_into) out.push({ key: "make-" + i.id, type: "make", id: i.id, name: i.name, line: "", group: "Make into" });
  out.push({ key: m.ask.id, type: "ask", id: m.ask.id, name: m.ask.name, line: m.ask.line, group: "" });
  return out;
}
