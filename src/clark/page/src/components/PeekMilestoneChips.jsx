// Row 1184: the milestone peek's chip row, four chips in the approved order: State, Owner, Progress, Forecast date. The same row and chip
// as the Action peek (PeekChips.jsx). The popovers come from the editor as `tools.PeekMsChipPop(m, field)`; with none (a published file, View)
// the chips are drawn read only. The State icons are the peek's own (Icon.jsx sForecast ... sClosed); the Milestones page keeps its marks (MsMark, LOOK).
import { PeekChips, PeekChip } from "./PeekChips.jsx";
import { fromFile } from "../stores/report.js";
import { stateOf } from "../logic/milestones.js";
import { dayNumber, showDate, ownerOf, todayIso } from "../workItems.js";

const DASH = "—";

/** State -> [icon name, tone]: Forecast grey, On track green, At risk amber, Slipped red, Overdue red, Achieved green. */
export const STATE_LOOK = {
  Forecast: ["sForecast", "n"], "On track": ["sTrack", "g"], "At risk": ["sRisk", "a"], Slipped: ["sSlip", "r"], Overdue: ["sOver", "r"], Achieved: ["sClosed", "g"],
};

/** The state a milestone shows: a published file carries the one it worked out; the live page works it out (logic/milestones.js). */
export const shownStateOf = (m) => (fromFile.value && m.state ? m.state : stateOf(m, todayIso()));

/** "overdue N days" for an open milestone whose forecast date has passed, else "". */
export function overdueWords(m, state, today) {
  const a = dayNumber(m.forecast_date), b = dayNumber(today);
  if (a === null || b === null || a >= b || state === "Achieved" || m.status === "Done" || m.status === "Cancelled") return "";
  const n = b - a;
  return `overdue ${n} ${n === 1 ? "day" : "days"}`;
}

/** `m`: the milestone; `tools`: the editor's tools (PeekMsChipPop, PeekChipLive); `editing`: true when the editor's chips are wanted. */
export function MilestoneChips({ m, tools, editing }) {
  const today = todayIso(), state = shownStateOf(m), look = STATE_LOOK[state] || STATE_LOOK.Forecast, who = ownerOf(m.owner);
  const pct = m.status === "Done" && m.percent_complete == null ? 100 : m.percent_complete;
  const progress = typeof pct === "number" ? `${Math.round(Math.min(100, Math.max(0, pct)))}%` : "Progress not set";
  const sub = overdueWords(m, state, today), late = !!sub;
  const pop = (field) => (editing && tools && tools.PeekMsChipPop ? tools.PeekMsChipPop(m, field) : null) || undefined;
  const Live = editing && tools && tools.PeekChipLive ? tools.PeekChipLive : undefined;
  return (
    <PeekChips>
      <PeekChip Live={Live} id={m.id} field="state" name="State" icon={look[0]} tone={look[1]} value={state} pop={pop("state")} />
      <PeekChip Live={Live} id={m.id} field="owner" name="Owner" icon="user" tone="b" value={who.text} pop={pop("owner")} />
      <PeekChip Live={Live} id={m.id} field="progress" name="Progress" icon="bars" tone="b" value={progress} pop={pop("progress")} />
      <PeekChip Live={Live} id={m.id} field="forecast" name="Forecast date" icon="cal" tone={late ? "r" : "b"} value={m.forecast_date ? showDate(m.forecast_date) : DASH} sub={sub} subTone={late ? "late" : ""} late={late} pop={pop("forecast")} />
    </PeekChips>
  );
}
