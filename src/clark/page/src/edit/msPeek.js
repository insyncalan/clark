// Row 828: the milestone peek's editable fields (plain functions, no DOM): what a pick sends. Every field is one change with one
// Undo (changeMilestone); nothing here writes. The words are the build's own (Help: the milestone peek); no new sentence.
import { stateOf } from "../logic/milestones.js";

// The states a person can pick. Overdue comes from the dates alone, so its button is drawn but is not one to press.
export const PICKABLE = ["Forecast", "On track", "At risk", "Slipped", "Achieved"];
export const ALL_STATES = ["Forecast", "On track", "At risk", "Slipped", "Overdue", "Achieved"];

// The state a milestone shows now (the dates' own suggestion unless a state was set by hand).
export const shownState = (m, today) => stateOf(m, today);

// The change a state button sends. Achieved is Done with its achieved date (today, unless it has one); any other state on a Done milestone
// reopens it (Planned, no achieved date). Pressing the state that was set by hand again clears it, so the dates decide again.
export function stateChange(m, pick, today) {
  const set = !!(m.state_set && m.state);
  const done = m.status === "Done";
  if (pick === "Achieved") {
    if (done) return { status: "Planned", state: null, state_set: 0, actual_date: null };      // pressed again: reopened, the dates decide
    return { status: "Done", state: "Achieved", state_set: 1, actual_date: m.actual_date || today };
  }
  if (set && m.state === pick && !done) return { state: null, state_set: 0 };
  return done ? { status: "Planned", actual_date: null, state: pick, state_set: 1 } : { state: pick, state_set: 1 };
}

// A text field's change: null when it is the same as it was (nothing is sent), else the one-field change. A blank clears an optional
// field; a blank name is refused here (the old name stays), as the server would.
export function textChange(field, was, typed, { required = false } = {}) {
  const next = String(typed == null ? "" : typed).trim();
  const old = String(was == null ? "" : was).trim();
  if (next === old) return null;
  if (!next) return required ? null : { [field]: null };
  return { [field]: next };
}

// Progress: a whole number from 0 to 100, or null when it is not one (nothing is sent).
export function progressChange(was, typed) {
  const text = String(typed == null ? "" : typed).trim();
  if (text === "") return was == null ? null : { percent_complete: null };
  if (!/^\d{1,3}$/.test(text)) return null;
  const n = Number(text);
  if (n > 100 || n === was) return null;
  return { percent_complete: n };
}
