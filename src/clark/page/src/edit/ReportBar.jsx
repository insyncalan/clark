// The bar above the page (A-D2): the week the report covers, and where it stands (Draft, or when it was published). Only a page
// clark serves has it (the published file is never given this part). The week is a date field in View and in Edit alike, as the
// prototype has it (views.js:509), and it shows the coming Friday when the project keeps no week yet (views.js:507). Edit adds the
// note that each change saves on its own and, the first time only, the drag hint (and the first section's grip and plus pulse once).
import { useEffect } from "preact/hooks";
import { signal } from "@preact/signals";
import { recall, remember } from "../logic/remember.js";
import { data, project, mode } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { todayIso } from "../workItems.js";
import { weekOf, shownDay } from "../logic/week.js";
import { latest, refreshLatest } from "./publishState.js";
import { lastLine } from "./Publish.jsx";
import { begin as pulseFirst } from "./firstEdit.js";

// The drag hint shows the first time this browser enters Edit and stays until Edit is left; after that it is not shown again.
const hintOpen = signal(!recall("dragHintSeen", false));

export function ReportBar() {
  useEffect(() => { refreshLatest(); }, [project.value]);
  if (!data.value || !data.value.project) return null;
  const stored = data.value.project.week_ending || "";
  const week = weekOf(stored, todayIso());       // the project's own week, else the coming Friday (shown, never saved until a day is picked)
  const editing = mode.value === "edit";
  useEffect(() => {
    if (editing && hintOpen.value) { remember("dragHintSeen", true); pulseFirst(); }
    if (!editing && hintOpen.value && recall("dragHintSeen", false)) hintOpen.value = false;
  }, [editing]);
  const published = lastLine(latest.value);
  const save = (e) => {       // a native date: YYYY-MM-DD, or "" when the box was cleared (the old day comes back)
    const el = e.currentTarget, iso = el.value;
    if (!/^\d{4}-\d\d-\d\d$/.test(iso) || iso === week) { el.value = week; return; }
    change({ kind: "projects", op: "update", changes: { week_ending: iso }, place: "cell" }, `Week ending changed to ${shownDay(iso)}.`)
      .then((reply) => { if (!reply) { const x = document.getElementById("week-ending"); if (x) x.value = week; } });
  };
  return (
    <div class="rbar" id="report-bar">
      <label class="rbar-week">Week ending <input type="date" id="week-ending" key={week} defaultValue={week} onChange={save} /></label>
      <span class="rbar-state" id="report-state">{editing ? "Editing · each change saves on its own" : published || "Draft · not published yet"}</span>
      {editing && hintOpen.value ? <span class="rbar-hint" id="report-hint">Drag to move, + to add a template</span> : null}
    </div>
  );
}
