// Row 1184: the milestone peek's chip row, on the shared frame (PeekChips). Four chips: State, Owner, Progress, Forecast date (no "forecast"
// tag). This file draws only: it imports nothing from the editor, so a published file and the Dashboard in View can use it. `pop` is
// { state, owner, progress, forecast }: each a ({ anchor, close }) => element, or absent for a read-only chip (the editor passes them from
// edit/MilestoneChipPops.jsx).
import { PeekChips, PeekChip } from "./PeekChips.jsx";
import { stateOf } from "../logic/milestones.js";
import { ownerOf, showDate, todayIso, dayNumber, plural } from "../workItems.js";
import { fromFile } from "../stores/report.js";

const DASH = "—";
// State -> [icon, tone]: the glyph set of the mockup (row 1180 icons table); tone is never the only signal, the word sits beside it.
export const STATE_ICON = {
  Forecast: ["sForecast", "n"], "On track": ["sTrack", "g"], "At risk": ["sRisk", "a"], Slipped: ["sSlip", "r"], Achieved: ["sClosed", "g"], Overdue: ["sDelayed", "r"],
};

/** The percentage as shown: a Done milestone with none set is 100. */
export const percentOf = (m) => (m.status === "Done" && m.percent_complete == null ? 100 : m.percent_complete);

/** "overdue N days" when the forecast date has passed and the milestone is not Done, else "". */
export function overdueWords(m, today) {
  const a = dayNumber(m.forecast_date), b = dayNumber(today);
  if (a === null || b === null || a >= b || m.status === "Done") return "";
  return `overdue ${plural(b - a, "day")}`;
}

export function MilestoneChips({ m, pop = {} }) {
  const today = todayIso();
  const state = fromFile.value && m.state ? m.state : stateOf(m, today);
  const [icon, tone] = STATE_ICON[state] || STATE_ICON.Forecast;
  const who = ownerOf(m.owner), pct = percentOf(m), late = overdueWords(m, today);
  return (
    <PeekChips>
      <PeekChip id={m.id} field="state" name="State" icon={icon} tone={tone} value={state} pop={pop.state} />
      <PeekChip id={m.id} field="owner" name="Owner" icon="user" tone="b" value={who.text} pop={pop.owner} />
      <PeekChip id={m.id} field="progress" name="Progress" icon="bars" tone="b" value={pct == null ? DASH : `${pct}%`} pop={pop.progress} />
      <PeekChip id={m.id} field="forecast" name="Forecast date" icon="cal" tone={late ? "r" : "b"} value={m.forecast_date ? showDate(m.forecast_date) : DASH}
        sub={late} subTone={late ? "late" : ""} late={!!late} pop={pop.forecast} />
    </PeekChips>
  );
}
