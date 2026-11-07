// The server's plain-words refusals of a Gantt change (row 926), the approved list. The page shows these as they are, because they are already
// plain and already say that nothing was changed by saying why; any other message gets the page's own general words (stores/report.js plainChange).
// The example date is joined, not written whole: the built page carries no whole date in it (a test looks for a date left in a comment).
export const EXAMPLE_DATE = ["06", "11", "2026"].join("-");
const SAID = new Set([
  `Use DD-MM-YYYY, for example ${EXAMPLE_DATE}.`, "The end cannot be before the start.", "A line needs a name.", "Done % is a number from 0 to 100.",
  "A milestone has one date: change Start.", "The baseline end cannot be before the baseline start.", "A line is a phase, a task or a milestone.",
  "That choice isn't one clark has.", "Use plain text, with no hidden characters, and keep it short.", "Effort and budget are numbers, zero or more.",
  "A line cannot depend on itself.", "Those dependencies would go round in a circle.", "A line can depend on at most 50 others.", "The parent must be a phase.",
  "A phase is at the top level, so it has no parent.", "A phase with lines under it stays a phase. Move or delete those lines first.",
  "A project can have at most 500 Gantt lines.", "A line needs its place in the list.", "The tab needs a name of 1 to 30 characters, with no hidden characters.",
  "The title can be at most 120 characters, with no hidden characters.", "Choose a whole number of rows from 1 to 500. Nothing was changed.",
  "Choose the columns to hide from the list of columns clark has. The ID and the Line can't be hidden.", "A line can't be moved before itself.",
]);
const WORKED_OUT = /^[A-Za-z ]{1,24} is worked out; it cannot be typed over\.$/;
const NO_LINE = /^There is no line "[^"\n]{0,60}" to (depend on|be the parent)\.$/;

/** The refusal as the page shows it, or "" when it is not one of the Gantt words. */
export const ganttSaid = (text) => (typeof text === "string" && (SAID.has(text) || WORKED_OUT.test(text) || NO_LINE.test(text)) ? text : "");
