// "+ Add a milestone from your project record (N)" under the Dashboard's Milestones block (Edit only; system/prototype/views.js:355).
// N is how many milestones are off the page (taken off with the eye, or not for the client). The line opens the project-record picker
// with the milestones only; Add brings the chosen ones back in one step with one Undo (actions.js addMilestonesBack). Nothing is
// kept here but whether the picker is open: N and the list come from the project's data, which is read again after every change
// and every Undo. The picker itself is drawn by MsPickerLayer (edit/MsLayers.jsx), beside the peek, outside the page it covers.
import { useRef } from "preact/hooks";
import { signal } from "@preact/signals";
import { data } from "../stores/report.js";
import { pickable, idsOf } from "../logic/picker.js";

export const pickerFrom = signal(null);          // null, or the button that opened the picker (focus goes back to it)

// The ids the eye has left out of the published page, from the data's `report_hidden`.
export function leftOutIds(d) {
  return (d && Array.isArray(d.report_hidden) ? d.report_hidden : []).map((h) => (h && h.item_id) || h);
}

// The milestones off the page, as the picker offers them: { milestones } only, so the picker lists no other kind.
export function offThePage(d) {
  const only = { milestones: (d && d.milestones) || [] }, left = leftOutIds(d);
  return { only, left, n: idsOf(pickable(only, left, "")).length };
}

export function MsAddBack() {
  const line = useRef(null);
  const { n } = offThePage(data.value);
  if (!n) return null;
  return (
    <div class="ms-addback">
      <button type="button" class="link add-from" data-ms-back ref={line} onClick={() => { pickerFrom.value = { line: line.current, list: line.current && line.current.closest(".msv") }; }}>{`+ Add a milestone from your project record (${n})`}</button>
    </div>
  );
}
