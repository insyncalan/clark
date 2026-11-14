// The bar above the page (A-D2), only on a page clark serves. Item 1177: the week, the published weeks list and the state chip left it (the week is the
// header's date button, HeaderDate.jsx; the Draft / Editing / Published words are at the top of the profile menu). It keeps View | Edit and, in Edit,
// the drag hint, shown the first time this browser enters Edit and until Edit is left. item 570: Friday is the week end (isFriday, notFriday).
import { useEffect } from "preact/hooks";
import { signal } from "@preact/signals";
import { recall, remember } from "../logic/remember.js";
import { data, mode } from "../stores/report.js";
import { shownDay } from "../logic/week.js";
import { weekEndOf } from "../logic/board.js";
import { Toggle } from "./Toggle.jsx";

// The drag hint shows the first time this browser enters Edit and stays until Edit is left; after that it is not shown again.
const hintOpen = signal(!recall("dragHintSeen", false));

// item 570: Friday is the week end. The Friday on or after a day (a weekend day rolls forward, as the board's This week does), the one the server's refusal names.
export const isFriday = (iso) => new Date(iso + "T00:00:00Z").getUTCDay() === 5;
export const notFriday = (iso) => `Week ending is a Friday. Pick Friday ${shownDay(weekEndOf(iso))}.`;

export function ReportBar() {
  const editing = mode.value === "edit";
  useEffect(() => {       // both hooks sit above the early return below (#534): every render calls the same hooks in the same order
    if (editing && hintOpen.value) remember("dragHintSeen", true);
    if (!editing && hintOpen.value && recall("dragHintSeen", false)) hintOpen.value = false;
  }, [editing]);
  if (!data.value || !data.value.project) return null;
  return (
    <div class="rbar" id="report-bar">
      <Toggle pill />{/* #665: View | Edit, at the left of the bar on the Dashboard (prototype views.js:509) */}
      {editing && hintOpen.value ? <span class="rbar-hint" id="report-hint">Drag to move, + to add a template</span> : null}
    </div>
  );
}
