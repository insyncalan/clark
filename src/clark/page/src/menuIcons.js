// Row 1074: the icon each drop-down choice shows beside its words. Plain functions, no DOM and no clock (the caller hands in today).
// Every icon is one of the page's existing ones (components/Icon.jsx) and every tone is one of r a g b n (iconColours.js), so no
// colour is written here. A choice is {icon, tone}: the words beside it always say the same thing, the icon never replaces them.
import { pillOf } from "./workItems.js";
import { priorityToneFor } from "./iconColours.js";

const FIELD_ICON = { workstream: "board", milestone: "flag", use_case: "doc" };
export const NAMES = ["half", "bars", "cal", "board", "flag", "doc", "circleminus"];
const RATING_TONE = { Red: "r", Amber: "a", Green: "g" };

/** A status choice: the half circle, in the tone the pill would take if the item had that status. */
export function statusIcon(row, status, today) { return { icon: "half", tone: pillOf({ ...row, status }, today).class }; }

/** A rating choice (Red, Amber, Green) of a risk or an issue, in its own colour. */
export function ratingIcon(word) { return { icon: "half", tone: RATING_TONE[word] || "n" }; }

/** A priority or level choice: the bars, in the tone the peek gives that priority. `kind` is the item kind (a risk or an issue takes the rating tones, as in the peek). */
export function priorityIcon(priority, kind) { return { icon: "bars", tone: priorityToneFor(priority, undefined, kind) }; }

/** A workstream, milestone or use case choice (grey); the choice that clears the field takes the minus. */
export function fieldIcon(field, clears) { return { icon: clears ? "circleminus" : FIELD_ICON[field] || "circleminus", tone: "n" }; }

/** A date choice in the date picker. */
export function dueIcon() { return { icon: "cal", tone: "n" }; }

// Row 1138: the one place that says which icon an action takes, so the same action has the same icon in every menu (the section
// menu, the profile menu, the right-click menus, the row menu). The words beside an icon are unchanged; an action not listed here has no icon.
export const ACTION_ICON = {
  add: "plus", duplicate: "copy", up: "chevup", down: "chevdown", beside: "board", full: "arrows-out", hide: "eyeoff", show: "eye",
  delete: "trash", settings: "gear", publish: "ul", preview: "search", search: "search", ask: "sparkle", exportExcel: "dl", exportWord: "dl", published: "archive",
  help: "info", profile: "user", copy: "copy", copyLink: "ext", copyId: "doc", copyIds: "doc", clear: "circleminus", archive: "archive",
  peek: "expand", draft: "pencil", pdf: "doc", excel: "dl", moveTo: "move", outline: "board", none: "circleminus",
  lookLight: "sun", lookDark: "eyeoff", lookSystem: "gear", pastReport: "archive", commit: "check",
  status: "half", due: "cal", owner: "user", priority: "bars", impact: "bars", likelihood: "bars", workstream: "board", milestone: "flag",
  made_by: "user", close: "check", reopen: "half", project: "doc", textStyle: "tline", filterAll: "table", filterPhases: "bars", filterMilestones: "flag", filterTicked: "check", columnsStandard: "table",
};

// Row 1138: the icon for each way of grouping (Group by, the lanes, the board's Move to menu): the same field has the same icon as its own
// action above. "type" and "nothing" have no action of their own.
const GROUP_ICON = { workstream: "board", status: "half", due: "cal", owner: "user", priority: "bars", milestone: "flag", type: "tline", nothing: "circleminus", commitment: "check", on: "clock" };
export function groupIcon(id) { return GROUP_ICON[id] || "circleminus"; }

// Row 1138: the icon for each way of sorting the use case list (Sort by).
const SORT_ICON = { ref: "doc", status: "half", open: "bars" };
export function sortIcon(id) { return SORT_ICON[id] || "circleminus"; }

// Row 1222: the icon each line of the columns menu takes (edit/ColumnsMenu.jsx): a column of a field has that field's icon (as its own action above),
// any other column the table icon; the foot line "Show the standard columns" has the table icon too.
const COLUMN_ICON = { status: "half", state: "half", item: "doc", name: "flag", owner: "user", made_by: "user", due: "cal", date: "cal", agreed: "cal", forecast: "cal", raised: "cal", closed: "cal",
  prio: "bars", workstream: "board", milestone: "flag", usecase: "doc", prog: "bars" };
export function columnIcon(id) { return COLUMN_ICON[id] || "table"; }

/** The icon name for an action, or undefined when the action has none. */
export function actionIcon(action) { return ACTION_ICON[action]; }
