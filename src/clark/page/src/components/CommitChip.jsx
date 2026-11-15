// issue 709: the commitment chip, read only: the word beside the status, drawn only when the use case has one (no placeholder, no "None").
// Its look is neutral on purpose (outline or ink), so it is never read as a status colour. Used by View, the Use cases page and the
// published file; Edit's menu button (edit/CommitMenu.jsx) draws the same chip.
import { commitWord, commitClass } from "../logic/commitment.js";

// Row 1234: with `dash` (View's use case rows) an empty commitment draws a dash, not a chip. Edit draws "Set commitment" instead (edit/CommitMenu.jsx).
export function CommitChip({ u, dash }) {
  const w = commitWord(u);
  if (w) return <span class={`cchip ${commitClass(w)}`} data-commit={w} title="Commitment">{w}</span>;
  return dash ? <span class="cdash muted" data-commit-none title="Commitment">{"\u2014"}</span> : null;
}
