// Row 1074: the icon each drop-down choice shows beside its words. Plain functions, no DOM and no clock (the caller hands in today).
// Every icon is one of the page's existing ones (components/Icon.jsx) and every tone is one of r a g b n (iconColours.js), so no
// colour is written here. A choice is {icon, tone}: the words beside it always say the same thing, the icon never replaces them.
import { pillOf } from "./workItems.js";
import { priorityTone } from "./iconColours.js";

const FIELD_ICON = { workstream: "board", milestone: "flag", use_case: "doc" };
export const NAMES = ["half", "bars", "cal", "board", "flag", "doc", "circleminus"];
const RATING_TONE = { Red: "r", Amber: "a", Green: "g" };

/** A status choice: the half circle, in the tone the pill would take if the item had that status. */
export function statusIcon(row, status, today) { return { icon: "half", tone: pillOf({ ...row, status }, today).class }; }

/** A rating choice (Red, Amber, Green) of a risk or an issue, in its own colour. */
export function ratingIcon(word) { return { icon: "half", tone: RATING_TONE[word] || "n" }; }

/** A priority or level choice: the bars, in the tone the peek gives that priority. */
export function priorityIcon(priority) { return { icon: "bars", tone: priorityTone(priority) }; }

/** A workstream, milestone or use case choice (grey); the choice that clears the field takes the minus. */
export function fieldIcon(field, clears) { return { icon: clears ? "circleminus" : FIELD_ICON[field] || "circleminus", tone: "n" }; }

/** A date choice in the date picker. */
export function dueIcon() { return { icon: "cal", tone: "n" }; }
