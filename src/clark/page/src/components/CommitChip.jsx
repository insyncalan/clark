// issue 709: the commitment chip, read only: the word beside the status, drawn only when the use case has one (no placeholder, no "None").
// Its look is neutral on purpose (outline or ink), so it is never read as a status colour. Used by View, the Use cases page and the
// published file; Edit's menu button (edit/CommitMenu.jsx) draws the same chip.
import { commitWord, commitClass } from "../logic/commitment.js";

export function CommitChip({ u }) {
  const w = commitWord(u);
  return w ? <span class={`cchip ${commitClass(w)}`} data-commit={w} title="Commitment">{w}</span> : null;
}
