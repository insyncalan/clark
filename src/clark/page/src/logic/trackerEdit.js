// The author's side of the 'Progress tracker' section (#189): every word only Edit shows or says (buttons, placeholders, the field that
// holds a note, the sentences that say what is wrong with a line) and the checks that use them. It lives apart from logic/tracker.js on
// purpose: only Edit imports this file, so none of these words is in View or the published file (#451, "nothing internal"). A test
// keeps them out of page-view.html.
import { COUNT_MAX, HEALTH, COLUMNS, MAX_GROUPS, MAX_LINES, NAME_MAX, NO_MAX, NOTE_MAX, STATUSES, TEXT_MAX, WHOLE, WORDS as VIEW_WORDS, isoOf, pct } from "./tracker.js";

export const EDIT_WORDS = {
  overall: "Overall",
  health: "Health",
  group: "Group name",
  noLinesEdit: "No lines yet. Press Add a line.",
  noneEdit: "Nothing is being tracked yet. Press Add a group to start.",
  notPublished: "A tracker with no lines is not published. Add a line to show it.",
  weightHint: "Weight is how much of the whole plan the line is worth. Weight, Planned and Achieved can each add up to 100% at most across all the lines.",
  addLine: "Add a line",
  addGroup: "Add a group",
  add: "Add",
  save: "Save",
  cancel: "Cancel",
  edit: "Edit",
  remove: "Remove",
  up: "Move up",
  down: "Move down",
  rename: "Rename",
  removeGroup: "Remove group",
  columns: "Show these columns",
  datePlaceholder: "DD-MM-YYYY",
  percentPlaceholder: "Part of 100",
  noHealth: "Not set",
  templateSettings: "Template settings",
  settingsLine: "Template settings. These apply to this tracker only.",
  sizeLabel: "Size",
  autoHint: "Automatic words. Click them to write your own.",
  yourWords: "Your words.",
  useAuto: "Use the automatic words",
  wordsLabelOne: "Note under the bar. One line.",
  wordsLabelThree: "Note under the bar. Up to three lines.",
  added: "Line added.",
  saved: "Saved.",
  removed: "Line removed.",
  moved: "Moved.",
  groupAdded: "Group added.",
  groupRemoved: "Group and its lines removed.",
  fullLines: `A tracker can have ${MAX_LINES} lines in all. Remove one to add another.`,
  fullGroups: `A tracker can have ${MAX_GROUPS} groups at most. Remove one to add another.`,
};
// The sizes, in the order the settings list them: [value, name, what it looks like].
export const SIZE_OPTIONS = [
  ["large", "Large", "Big numbers and a thick bar"],
  ["medium", "Medium", "Numbers a little smaller"],
  ["small", "Small", "Smaller numbers, a thinner bar"],
  ["compact", "Compact", "One slim row, no scale"],
];
export const PROBLEMS = {
  text: "Describe each line.",
  // The words below that the store also says (text, textLong, noLong, percent, order, status, count, name, nameLong) are the store's own
  // (clark/section_bodies.py, guarded) and tests/test_tracker_logic.py holds the page to them; the page's fuller wording for the same
  // refusals is in stores/report.js (CHANGE_KNOWN).
  textLong: `A line description can be ${TEXT_MAX} characters at most. Shorten it and try again.`,
  noLong: `A line number can be ${NO_MAX} characters at most. Shorten it and try again.`,
  percent: "Type a percentage from 0 to 100, with one decimal at most.",
  date: "That date isn't right. Type it as DD-MM-YYYY, or leave it empty.",
  order: "A line can't end before it starts.",
  status: "Choose Planned, In progress, Completed or Late.",
  count: `A count must be a whole number from 0 to ${COUNT_MAX}, or empty.`,
  name: "Give each group a name.",
  nameLong: `A group name can be ${NAME_MAX} characters at most. Shorten it and try again.`,
  total: "Weight, Planned or Achieved adds up to more than 100% across all the lines. Lower one of the figures and try again.",
  noteLong: `A line about it can be ${NOTE_MAX} characters at most. Shorten it and try again.`,
};
// Every word, the reader's and the author's, as Edit uses them: `WORDS.problems` is the sentences.
export const WORDS = { ...VIEW_WORDS, ...EDIT_WORDS, problems: PROBLEMS };
export const ALL_WORDS = () => {
  const out = [];
  const walk = (o) => { for (const v of Object.values(o)) { if (typeof v === "string") out.push(v); else walk(v); } };
  walk(WORDS);
  for (const [, w] of [...STATUSES, ...HEALTH, ...COLUMNS]) out.push(w);
  for (const [, name, what] of SIZE_OPTIONS) out.push(name, what);
  return out;
};

// ── Checking a line before anything is sent ─────────────────────────────────────────────────────────────────────────────

const chars = (s) => Array.from(s).length;
const countOf = (text) => {
  const t = String(text == null ? "" : text).trim();
  if (!t) return null;
  return /^\d{1,5}$/.test(t) && +t <= COUNT_MAX ? +t : undefined;
};

// A typed line ({ no, text, start, end, status, weight, planned, achieved, tasks, agents, workflows }, every value as typed) as a
// plain sentence, the store's own words, or "" when it can be saved.
export function problem(draft) {
  const P = PROBLEMS;
  const text = String(draft.text == null ? "" : draft.text).trim();
  if (!text) return P.text;
  if (chars(text) > TEXT_MAX) return P.textLong;
  if (chars(String(draft.no == null ? "" : draft.no).trim()) > NO_MAX) return P.noLong;
  if (!STATUSES.some((s) => s[0] === draft.status)) return P.status;
  const start = isoOf(draft.start), end = isoOf(draft.end);
  if (start === null || end === null) return P.date;
  if (start && end && end < start) return P.order;
  for (const k of ["weight", "planned", "achieved"]) {
    const t = String(draft[k] == null ? "" : draft[k]).trim();
    if (t !== "" && pct(t) === null) return P.percent;
  }
  for (const k of ["tasks", "agents", "workflows"]) if (countOf(draft[k]) === undefined) return P.count;
  return "";
}

// A typed line as it is saved (an empty percentage is 0, an empty count is none).
export function made(draft) {
  const p = (k) => pct(draft[k]) || 0;
  return { no: String(draft.no == null ? "" : draft.no).trim(), text: String(draft.text).trim(), start: isoOf(draft.start) || "", end: isoOf(draft.end) || "",
    status: draft.status, weight: p("weight"), planned: p("planned"), achieved: p("achieved"),
    tasks: countOf(draft.tasks) ?? null, agents: countOf(draft.agents) ?? null, workflows: countOf(draft.workflows) ?? null };
}

// Problems with a group's name or the overall's typed words, as a sentence or "".
export function nameProblem(name) {
  const t = String(name == null ? "" : name).trim();
  return !t ? PROBLEMS.name : chars(t) > NAME_MAX ? PROBLEMS.nameLong : "";
}
export const noteProblem = (note) => (chars(String(note == null ? "" : note).trim()) > NOTE_MAX ? PROBLEMS.noteLong : "");

// "" when no column of figures (weight, planned, achieved) adds up to more than the whole across the tracker, else the store's sentence.
export function totalProblem(tracker) {
  const all = tracker.groups.flatMap((g) => g.lines);
  return ["weight", "planned", "achieved"].some((k) => all.reduce((n, l) => n + l[k], 0) > WHOLE) ? PROBLEMS.total : "";
}
