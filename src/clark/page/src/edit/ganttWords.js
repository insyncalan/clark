// The Gantt page's words that only Edit uses (#926, #928): the pill, the toasts, Export and Import, the title's label. Every one is in the spec's word list
// (#926 section 4) unless it says "added". The page gets them as tools.ganttWords, so a published file holds none of them.
export const GANTT_EDIT_WORDS = {
  edit: "Edit", view: "View",
  editTip: "Edit the plan", viewTip: "Back to the view (what the client sees)",
  exportXl: "Export to Excel", importXl: "Import from Excel",
  undo: "Undo",
  addBelow: "Add a line below",                                                          // the add button beside a row (chart and table) and the first line of an empty plan
  editNote: "Editing · each change saves on its own",                                  // the Dashboard's own words, reused
  titleLabel: "Title",                                                                   // added: the title box's accessible name
  titleChanged: "Title changed.",                                                        // added: the title's Undo toast
  planChanged: "Plan changed.",                                                         // added: a fill, a clear or a paste, which has no one line to name
  changed: (id) => `${id} changed.`,                                                     // added: a line edited in the chart
  added: "A line was added with the next free ID.",
  deleted: (id) => `Line ${id} deleted.`,
  deletedMany: (n) => `${n} lines deleted.`,                                             // added
  eyeTipOn: "Shown on the dashboard. Press to take it off", eyeTipOff: "Not on the dashboard. Press to put it on", eyeHead: "Show on the dashboard", eyeDetail: "On the dashboard",      // the chart's eye column: Edit only
  eyeOn: (name) => `Shown on the dashboard: ${name}.`,
  eyeOff: (name) => `Taken off the dashboard: ${name}.`,
  colOn: (col) => `${col}: shown to the client.`,
  colOff: (col) => `${col}: hidden from the client.`,
  rows: (n, m) => `Plan height saved: ${n} of ${m} rows. Viewers can still change their own.`,
  rowsAll: "Plan height: all rows shown.",
  columnsChanged: "Hidden columns changed.",                                             // added: the table's column eye
};

// The server's plain-words refusals of a Gantt change (row 926), the approved list. The page shows these as they are, because they are already
// plain and already say that nothing was changed by saying why; any other message gets the page's own general words (stores/report.js plainChange).
// Edit registers this with report.js (sayings), so a published file carries none of it.
import { EXAMPLE_DATE } from "../gantt/logic/ganttWords.js";
import { NAME_MAX } from "../gantt/ganttTab.js";
import { sayings } from "../stores/report.js";

export const NAME_REFUSED = `Give the tab a name of 1 to ${NAME_MAX} characters. Nothing was changed.`;

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
sayings.push(ganttSaid);
