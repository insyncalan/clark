// The Milestones page's Plan / Movement switch (C-M2). Edit only: it is one of the `tools` (edit/index.js), so the published page, which
// is given none, has no switch and no Movement. In View the page is the Plan alone. The choice is remembered in this browser.
import { useState } from "preact/hooks";
import { mode } from "../stores/report.js";
import { recall, remember } from "../logic/remember.js";
import { Movement } from "./Movement.jsx";
import { HEADING } from "./movementWords.js";

const MOVE_HINT = "Each move changes the milestone straight away. You can Undo it.";
const PLAN_HINT = "Every milestone is on the timeline. The list shows where each one stands.";

export function MilestonesPage({ plan }) {
  const [view, setView] = useState(() => (recall("msp.view", "plan") === "move" ? "move" : "plan"));
  if (mode.value !== "edit") return plan;
  const choose = (v) => { remember("msp.view", v); setView(v); };
  return (
    <>
      <div class="wbar" data-mspage-switch>
        <div class="seg" role="group" aria-label="Milestones view">
          {[["plan", "Plan"], ["move", HEADING]].map(([v, t]) => <button type="button" key={v} data-mspv={v} aria-pressed={view === v ? "true" : "false"} onClick={() => choose(v)}>{t}</button>)}
        </div>
        <span class="muted" data-mspage-hint>{view === "move" ? MOVE_HINT : PLAN_HINT}</span>
      </div>
      {view === "move" ? <Movement /> : plan}
    </>
  );
}
