// The peek's warning bar (Edit only), handed over as `tools.PeekWarn`: what is wrong with the due date, and the moves that fix it.
// A move is the same one-step change as picking the date in the table (itemEdit.changeFor, then changeCell), so its toast, its
// Undo and its one polite announcement are the page's own. The bar itself is not a live region.
import { changeCell } from "../stores/changes.js";
import { todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { warningFor } from "./peekWarn.js";

export function PeekWarn({ row }) {
  const today = todayIso(), w = warningFor(row, today);
  if (!w) return null;
  const move = (iso) => {
    const c = changeFor(row, "due", iso, today);
    if (!c || c.error) return;
    changeCell(tableOf(row), row.id, c.changes, { text: c.words, back: c.back }).then(() => {
      const el = document.querySelector("#peek [data-pk-close]");           // the warning is gone, so focus goes to a stable place
      if (el) el.focus();
    });
  };
  return (
    <div class={`pk-warn ${w.tone}`} role="group" aria-label="Due date warning" data-pk-warn={w.tone}>
      <p class="pk-warn-text">{w.text}</p>
      <div class="pk-fix">
        {w.fixes.map((f) => <button key={f.iso} type="button" class="pk-fix-btn" data-move={f.iso} onClick={() => move(f.iso)}>{f.label}</button>)}
      </div>
    </div>
  );
}
