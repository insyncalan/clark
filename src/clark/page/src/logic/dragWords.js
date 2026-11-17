// Row 1214: the words for a section drag, pure (no DOM). `dragWords(sections, id, target)` gives { line, said } for the target the
// drag shows now (null: nothing would change). `line` is the status line under the page while the pointer is down ("Release to ...");
// `said` is what a screen reader hears after the drop. X is the dragged section's title, Y the section it goes beside, above or below.
// Which of "above" and "below" is said: a drop in front of a section is above that section (the line sits before its row, so this is
// true whichever edge the pointer is near); a drop at the very end is below the last section.
import { place, applied, name } from "./placement.js";

export function dragWords(sections, id, target) {
  const me = sections.find((s) => s.id === id);
  const x = name(me);
  const p = target && me ? place(sections, id, target) : null;
  if (!p || !p.ok) return { line: `Release to leave "${x}" where it is.`, said: `"${x}" stays where it is.` };
  if ("beside" in target) {
    const y = name(sections.find((s) => s.id === target.beside));
    return { line: `Release to put "${x}" beside "${y}", half width each.`, said: `Moved "${x}" beside "${y}", half width each.` };
  }
  const after = applied(sections, p.payload);
  if (after.every((s, i) => s.id === sections[i].id)) return { line: `Release to make "${x}" full width.`, said: `"${x}" is now full width.` };
  const at = after.findIndex((s) => s.id === id), prev = after[at - 1], next = after[at + 1];
  if (!next) return { line: `Release to put "${x}" below "${name(prev)}".`, said: `Moved "${x}" below "${name(prev)}".` };
  return { line: `Release to put "${x}" above "${name(next)}".`, said: `Moved "${x}" above "${name(next)}".` };
}
