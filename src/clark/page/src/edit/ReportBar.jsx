// The bar above the page (A-D2): the week the report covers, and where it stands (Draft, or when it was published). Only a page
// clark serves has it (the published file is never given this part). View shows the week as text and the chip; Edit adds the date
// field, the note that each change saves on its own and, the first time only, the drag hint. Never an input in View.
import { useEffect } from "preact/hooks";
import { signal } from "@preact/signals";
import { recall, remember } from "../logic/remember.js";
import { data, project, mode } from "../stores/report.js";
import { change, say } from "../stores/changes.js";
import { parseDay, problem } from "../templates/keydates.js";
import { latest, refreshLatest } from "./publishState.js";
import { lastLine } from "./Publish.jsx";
import { todayIso } from "../workItems.js";
import { weekEndOf } from "../logic/board.js";

// The drag hint shows the first time this browser enters Edit and stays until Edit is left; after that it is not shown again.
const hintOpen = signal(!recall("dragHintSeen", false));
const shownDate = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

// The Friday this week's report is for, as YYYY-MM-DD in the person's own day: only offered, never saved on its own.
// #570: the same helper as the board's This week (board.js fridayOnOrAfter): Monday to Friday it is this week's Friday (today on a
// Friday); on a Saturday or Sunday it is the COMING Friday. Today comes from the one place that reads the clock (workItems.js).
export function fridayOfThisWeek(today = todayIso()) {
  return weekEndOf(today);
}

// #570: Friday is the week end. The Friday on or after a day (a weekend day rolls forward), the same one the server's refusal names.
export const isFriday = (iso) => new Date(iso + "T00:00:00Z").getUTCDay() === 5;
export const notFriday = (iso) => `Week ending is a Friday. Pick Friday ${shownDate(fridayOfThisWeek(iso))}.`;

export function ReportBar() {
  useEffect(() => { refreshLatest(); }, [project.value]);
  if (!data.value || !data.value.project) return null;
  const week = data.value.project.week_ending || "";
  const editing = mode.value === "edit";
  useEffect(() => {
    if (editing && hintOpen.value) remember("dragHintSeen", true);
    if (!editing && hintOpen.value && recall("dragHintSeen", false)) hintOpen.value = false;
  }, [editing]);
  const published = lastLine(latest.value);
  const save = (e, confirmed) => {       // typed as DD-MM-YYYY, as Key dates takes it: clark's own way, never the browser's calendar
    const el = e.currentTarget, raw = el.value.trim(), iso = parseDay(raw);
    if (!raw && !week && confirmed) {       // an empty box with no week yet: Enter confirms the Friday shown as the starting value
      const friday = fridayOfThisWeek();
      change({ kind: "projects", op: "update", changes: { week_ending: friday }, place: "cell" }, `Week ending changed to ${shownDate(friday)}.`);
      return;
    }
    if (!raw || iso === week) { el.value = shownDate(week); return; }
    if (!iso) { say("problem", problem.day + " The old week ending date was kept."); el.value = shownDate(week); return; }       // not a day: the old one comes back
    if (!isFriday(iso)) { say("problem", notFriday(iso) + " The old week ending date was kept."); el.value = shownDate(week); return; }       // #570: the server says the same
    change({ kind: "projects", op: "update", changes: { week_ending: iso }, place: "cell" }, `Week ending changed to ${shownDate(iso)}.`)
      .then((reply) => { if (!reply) { const x = document.getElementById("week-ending"); if (x) x.value = shownDate(week); } });
  };
  return (
    <div class="rbar" id="report-bar">
      {editing ? (
        <label class="rbar-week">Week ending <input type="text" inputMode="numeric" placeholder={week ? "DD-MM-YYYY" : shownDate(fridayOfThisWeek())} title={week ? undefined : "Press Enter to use this Friday, or type a Friday"} id="week-ending" key={week} defaultValue={shownDate(week)} onBlur={save} onKeyDown={(e) => { if (e.key === "Enter") { if (!week && !e.currentTarget.value.trim()) save(e, true); else e.currentTarget.blur(); } }} /></label>
      ) : (
        <span class="rbar-week" id="week-ending-text">{week ? `Week ending ${shownDate(week)}` : "No week ending date yet"}</span>
      )}
      <span class="rbar-state" id="report-state">{editing ? "Editing · each change saves on its own" : published || "Draft · not published yet"}</span>
      {editing && hintOpen.value ? <span class="rbar-hint" id="report-hint">Drag to move, + to add a template</span> : null}
    </div>
  );
}
