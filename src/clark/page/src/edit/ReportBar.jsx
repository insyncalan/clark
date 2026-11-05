// The bar above the page (A-D2): the week the report covers, and where it stands (Draft, or when it was published). Only a page
// clark serves has it (the published file is never given this part). The week is a typed DD-MM-YYYY box in View and in Edit alike (never the browser's calendar),
// showing the coming Friday when the project keeps no week yet (prototype views.js:507; shown, saved only on Enter). item 570: Friday is the
// week end, so a day that is not a Friday keeps the old date and names the Friday (the server says the same). Edit adds the
// note that each change saves on its own and, the first time only, the drag hint.
import { useEffect } from "preact/hooks";
import { signal } from "@preact/signals";
import { recall, remember } from "../logic/remember.js";
import { data, project, mode } from "../stores/report.js";
import { change, say } from "../stores/changes.js";
import { parseDay, problem } from "../templates/keydates.js";
import { todayIso } from "../workItems.js";
import { weekOf, shownDay } from "../logic/week.js";
import { weekEndOf } from "../logic/board.js";
import { latest, refreshLatest } from "./publishState.js";
import { lastLine } from "./Publish.jsx";
import { ownToast } from "./BarToast.jsx";
import { Toggle } from "./Toggle.jsx";
import { WeekPicker } from "./WeekPicker.jsx";

// The drag hint shows the first time this browser enters Edit and stays until Edit is left; after that it is not shown again.
const hintOpen = signal(!recall("dragHintSeen", false));

// item 570: Friday is the week end. The Friday on or after a day (a weekend day rolls forward, as the board's This week does), the one the server's refusal names.
export const isFriday = (iso) => new Date(iso + "T00:00:00Z").getUTCDay() === 5;
export const notFriday = (iso) => `Week ending is a Friday. Pick Friday ${shownDay(weekEndOf(iso))}.`;

export function ReportBar() {
  const editing = mode.value === "edit";
  useEffect(() => { refreshLatest(); }, [project.value]);
  useEffect(() => {       // both hooks sit above the early return below (#534): every render calls the same hooks in the same order
    if (editing && hintOpen.value) remember("dragHintSeen", true);
    if (!editing && hintOpen.value && recall("dragHintSeen", false)) hintOpen.value = false;
  }, [editing]);
  if (!data.value || !data.value.project) return null;
  const stored = data.value.project.week_ending || "";
  const week = weekOf(stored, todayIso());       // the project's own week, else the coming Friday (shown, never saved until a day is picked)
  const published = lastLine(latest.value);
  const save = (e, confirmed) => {       // typed as DD-MM-YYYY, as Key dates takes it: clark's own way, never the browser's calendar
    const el = e.currentTarget, raw = el.value.trim(), iso = parseDay(raw);
    if (iso && iso === week && !stored && confirmed) {       // no week kept yet and Enter on the Friday shown: that day is what the person picked
      change({ kind: "projects", op: "update", changes: { week_ending: iso }, place: "cell" }, `Week ending changed to ${shownDay(iso)}.`).then(ownToast);
      return;
    }
    if (!raw || iso === week) { el.value = shownDay(week); return; }
    if (!iso) { say("problem", problem.day + " The old week ending date was kept."); ownToast(); el.value = shownDay(week); return; }       // not a day: the old one comes back
    if (!isFriday(iso)) { say("problem", notFriday(iso) + " The old week ending date was kept."); ownToast(); el.value = shownDay(week); return; }       // item 570: the server says the same
    change({ kind: "projects", op: "update", changes: { week_ending: iso }, place: "cell" }, `Week ending changed to ${shownDay(iso)}.`)
      .then((reply) => { ownToast(); if (!reply) { const x = document.getElementById("week-ending"); if (x) x.value = shownDay(week); } });
  };
  const enter = (e) => {       // Enter on the Friday shown, with no week kept, saves it; Enter on anything else leaves the box, and leaving saves
    if (e.key !== "Enter") return;
    if (!stored && parseDay(e.currentTarget.value.trim()) === week) save(e, true); else e.currentTarget.blur();
  };
  return (
    <div class="rbar" id="report-bar">
      <Toggle pill />{/* #665: View | Edit, at the left of the bar on the Dashboard (prototype views.js:509) */}
      <label class="rbar-week">Week ending <input type="text" inputMode="numeric" placeholder="DD-MM-YYYY" title={stored ? undefined : "Not saved yet. Press Enter to use this Friday, or type a Friday"} id="week-ending" key={week} defaultValue={shownDay(week)} onBlur={save} onKeyDown={enter} /></label>
      <WeekPicker />{/* item 344: the published weeks, beside Week ending in View and Edit; it only opens one, read only */}
      <span class="rbar-state" id="report-state">{editing ? "Editing · each change saves on its own" : published || "Draft · not published yet"}</span>
      {editing && hintOpen.value ? <span class="rbar-hint" id="report-hint">Drag to move, + to add a template</span> : null}
    </div>
  );
}
