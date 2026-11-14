// Item 1182: the risk peek's rating, as plain functions with no DOM. A risk's (or issue's) priority follows from its impact and
// likelihood (clark/store.py): High and High is Urgent, any High is High, Low and Low is Low, the rest Medium. Urgent and High are
// Red, Medium Amber, Low Green. The matrix sets both fields in one change, so one Undo, one toast and one line per field in Activity.
import { colourOf } from "../workItems.js";

export const LEVELS = ["High", "Medium", "Low"];
export const MATRIX_ROWS = LEVELS;                      // Impact, top to bottom
export const MATRIX_COLS = ["Low", "Medium", "High"];   // Likelihood, left to right
export const RATING_TIP = "Priority from impact and likelihood";

/** The priority word two levels give (the store's own rule), or "" when either is missing. */
export function levelOf(impact, likelihood) {
  if (!LEVELS.includes(impact) || !LEVELS.includes(likelihood)) return "";
  if (impact === "High" && likelihood === "High") return "Urgent";
  if (impact === "High" || likelihood === "High") return "High";
  if (impact === "Low" && likelihood === "Low") return "Low";
  return "Medium";
}

/** The colour word (Red, Amber, Green) a level has, or "Not rated". */
export const colourWord = (level) => colourOf(level).word;

/** What a risk or issue shows: {colour, level, text}. Not rated: colour "Not rated", level "". */
export function ratingOf(row) {
  const level = row && row.priority ? String(row.priority) : "", colour = colourWord(level);
  return { colour, level, text: level ? `${colour} · ${level}` : colour };
}

/** The line under the matrix: "High impact, Medium likelihood: High (Red)". */
export function matrixLine(impact, likelihood) {
  const level = levelOf(impact, likelihood);
  return level ? `${impact} impact, ${likelihood} likelihood: ${level} (${colourWord(level)})` : "";
}

/** The Details row's words: "Rating: Red · High (impact High, likelihood Medium)"; "Rating: Not rated" when there is none. */
export function detailsRating(row) {
  const r = ratingOf(row);
  if (!r.level) return `Rating: ${r.colour}`;
  return row.impact && row.likelihood ? `Rating: ${r.text} (impact ${row.impact}, likelihood ${row.likelihood})` : `Rating: ${r.text}`;
}

/** The sub-line of a closed or cancelled risk or issue ("Red kept"); "" when it is open or has none. `open` is isOpen(row). */
export function keptWord(row, open) {
  return (row.kind === "risk" || row.kind === "issue") && !open ? `${colourOf(row.priority).word} kept` : "";
}

/**
 * The change a click on a matrix cell makes: null when both fields are already that, else
 * {changes: {impact, likelihood}, words, back, one: true} for changeRating (stores/changes.js). Both fields are always sent.
 */
export function matrixChange(row, impact, likelihood) {
  if (!LEVELS.includes(impact) || !LEVELS.includes(likelihood)) return { error: "Impact and likelihood are each High, Medium or Low, so nothing was changed. Pick a cell from the matrix." };
  if (row.impact === impact && row.likelihood === likelihood) return null;
  const was = (v) => v || "blank";
  return {
    changes: { impact, likelihood },
    words: `Impact and likelihood of ${row.id} changed to ${impact} and ${likelihood}.`,
    back: `Impact and likelihood of ${row.id} are back to ${was(row.impact)} and ${was(row.likelihood)}.`,
    one: true,
  };
}
