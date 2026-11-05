// One test for "may this page be edited now?" (row 804): the View | Edit switch exists only on the Dashboard, so there the mode
// decides; on every other page the editing is live and there is no mode to ask.
import { mode, view } from "../stores/report.js";

export function isEditing() {
  return mode.value === "edit" || view.value !== "dashboard";
}
