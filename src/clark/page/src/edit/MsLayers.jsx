// The two things the Milestones page opens over itself, drawn beside the page's own peek and outside #main (so the page behind them
// can be made inert): the project-record picker for milestones ("+ Add a milestone from your project record", edit/MsAddBack.jsx)
// and an archived milestone's read-only peek (edit/ArchivedPeek.jsx). Edit only: a published file has neither.
import { useEffect } from "preact/hooks";
import { data, mode } from "../stores/report.js";
import { Picker } from "../components/Picker.jsx";
import { pickerFrom, offThePage } from "./MsAddBack.jsx";
import { addMilestonesBack } from "./actions.js";
import { ArchivedPeek } from "./ArchivedPeek.jsx";

const BEHIND = ["#main", ".top"];                       // made inert while the picker is open, as the Add a section box does

function PickerBox({ from }) {
  const { only, left } = offThePage(data.value);
  const close = () => {
    pickerFrom.value = null;
    // Focus goes back to the line; when the last milestone came back the line is gone, so it goes to the list it joined.
    setTimeout(() => {
      const b = from.line;
      if (b && b.isConnected) b.focus();
      else { const l = from.list && from.list.isConnected ? from.list : null; const c = l && l.querySelector(".msl-cells"); if (c) c.focus(); }
    }, 0);
  };
  useEffect(() => {
    const held = BEHIND.map((q) => document.querySelector(q)).filter(Boolean);
    held.forEach((el) => el.setAttribute("inert", ""));
    return () => held.forEach((el) => el.removeAttribute("inert"));
  }, []);
  return (
    <div class="ad-scrim" data-ms-picker onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <Picker data={only} hiddenIds={left} onAdd={(ids) => { close(); addMilestonesBack(ids); }} onClose={close} title="Add a milestone from your project record" />
    </div>
  );
}

export function MsLayers() {
  const from = pickerFrom.value;
  return (
    <>
      {from && mode.value === "edit" ? <PickerBox key="picker" from={from} /> : null}
      <ArchivedPeek />
    </>
  );
}
