// Items 1182 and 1183: the Rating of a risk or an issue, as the 3 x 3 matrix draws it. Plain functions, no DOM and no clock.
// The rule is clark's own (clark/store.py priority()): High impact with High likelihood is Urgent, any other High is High (both Red),
// Low with Low is Low (Green), the rest Medium (Amber). The colour is never stored (workItems.colourOf). One pick sets impact and
// likelihood in ONE change (one step, one Undo, one Activity line); a test pins this mirror to the store's rule for all nine cells.
import { colourOf } from "../workItems.js";

export const IMPACTS = ["High", "Medium", "Low"];            // the rows, top to bottom
export const LIKELIHOODS = ["Low", "Medium", "High"];        // the columns, left to right

/** The level word (Urgent, High, Medium, Low) for an impact and a likelihood, as clark works it out; null when either is not set. */
export function levelOf(impact, likelihood) {
  if (!IMPACTS.includes(impact) || !IMPACTS.includes(likelihood)) return null;
  if (impact === "High" && likelihood === "High") return "Urgent";
  if (impact === "High" || likelihood === "High") return "High";
  if (impact === "Low" && likelihood === "Low") return "Low";
  return "Medium";
}

/** What a cell of the matrix shows: {level, colour (Red, Amber, Green), tone (r a g), label}. */
export function cellOf(impact, likelihood) {
  const level = levelOf(impact, likelihood), c = colourOf(level);
  return { level, colour: c.word, tone: c.class, label: `${impact} impact, ${likelihood} likelihood: ${level} (${c.word})` };
}

/** The line under the matrix: "High impact, Medium likelihood: High (Red)". */
export const sentenceOf = (impact, likelihood) => cellOf(impact, likelihood).label;

/** The change a click on a cell makes: {changes: {impact, likelihood}, words, back} (one change, both fields), {error}, or null when the cell is the rating the row has. */
export function matrixChange(row, impact, likelihood) {
  if (!IMPACTS.includes(impact) || !IMPACTS.includes(likelihood)) return { error: "Impact and likelihood are each High, Medium or Low, so nothing was changed. Pick one from the list." };
  if (row.impact === impact && row.likelihood === likelihood) return null;
  const now = levelOf(row.impact, row.likelihood) ? cellOf(row.impact, row.likelihood) : null, to = cellOf(impact, likelihood);
  return {
    changes: { impact, likelihood },
    words: `${row.id} rated ${to.level} (${to.colour}).`,
    back: now ? `${row.id} is back to ${now.level} (${now.colour}).` : `Rating of ${row.id} is blank again.`,
  };
}
