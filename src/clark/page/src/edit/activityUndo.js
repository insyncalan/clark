// Undo several, on the peek's Activity tab: the rules, as plain functions the tab and the tests both use. A row can be chosen when it is
// a change with a step to undo; any other row says why in words. The selection holds steps (as text), so the rows of one step are one
// choice and tick together. Nothing here reads the page or the network.
export const MOST = 100;                    // the most changes one Undo takes (the server refuses above this)
export const CONFIRM_ABOVE = 25;            // above this a second confirm is asked

export const WHY_COMMENT = "A comment has nothing to undo.";
export const WHY_UNDO = "This was an undo, so it can't be chosen here. Undo it from the message after it.";
export const WHY_NO_STEP = "This change can't be undone from here.";

/** "" when the row can be chosen, else the words that say why not. */
export function whyNot(r) {
  if (!r) return WHY_NO_STEP;
  if (r.kind === "Comment") return WHY_COMMENT;
  if (/undone$/i.test(String(r.kind || ""))) return WHY_UNDO;
  if (!Number.isInteger(r.step) || r.step < 1) return WHY_NO_STEP;
  return "";
}

/** The steps of the rows that can be chosen, in the order drawn, each once. */
export function chooseable(rows) {
  const out = [];
  for (const r of rows) if (!whyNot(r) && !out.includes(String(r.step))) out.push(String(r.step));
  return out;
}

export const stepsOf = (ids) => ids.map(Number).filter((n) => Number.isInteger(n) && n > 0).sort((a, b) => b - a);

export const countWords = (n) => `${n} change${n === 1 ? "" : "s"}`;
export const undoWords = (n) => `Undo ${n}`;
export const tooMany = (n) => `You have chosen ${n}. Choose at most ${MOST} changes at a time.`;
export const sureWords = (n) => `This will undo ${n} changes in one go. You can undo them all again afterwards. Undo all ${n}?`;

/** One line of the preview for a change that will be undone, in plain words. */
export function willLine(e) {
  const ref = String(e.ref || "");
  if (!e.field && e.change === "removed") return `${ref} will be taken away again`;
  if (!e.field && e.change === "put back") return `${ref} will be put back`;
  return e.field ? `${ref}: ${e.field} goes back` : `${ref} goes back`;
}

/** One line for a change that will be left as it is. */
export function leftLine(e) {
  const ref = String(e.ref || "");
  return `${e.field ? `${ref}: ${e.field}` : ref} stays as it is. ${String(e.why || "")}`.trim();
}
