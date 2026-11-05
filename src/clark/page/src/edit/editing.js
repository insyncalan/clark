// Whether the page being drawn lets the person change things now. The Dashboard keeps the View | Edit switch; every other page is live
// and has no switch (rulings 02-11-2026 and row 824), so there it is always true.
import { mode, view } from "../stores/report.js";

export function isEditing() {
  return mode.value === "edit" || view.value !== "dashboard";
}
