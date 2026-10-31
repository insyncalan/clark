// The bar above the page (A-D2): the week the report covers, and where it stands (Draft, or when it was published). Only a page
// clark serves has it (the published file is never given this part). View shows the week as text and the chip; Edit adds the date
// field, the note that each change saves on its own and the drag hint. Never an input in View.
import { useEffect } from "preact/hooks";
import { data, project, mode } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { latest, refreshLatest } from "./publishState.js";
import { lastLine } from "./Publish.jsx";

const shownDate = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

export function ReportBar() {
  useEffect(() => { refreshLatest(); }, [project.value]);
  if (!data.value || !data.value.project) return null;
  const week = data.value.project.week_ending || "";
  const editing = mode.value === "edit";
  const published = lastLine(latest.value);
  const save = (e) => {
    const v = e.currentTarget.value;
    if (!v || v === week) { e.currentTarget.value = week; return; }
    change({ kind: "projects", op: "update", changes: { week_ending: v }, place: "cell" }, `Week ending changed to ${shownDate(v)}.`)
      .then((reply) => { if (!reply) { const el = document.getElementById("week-ending"); if (el) el.value = week; } });
  };
  return (
    <div class="rbar" id="report-bar">
      {editing ? (
        <label class="rbar-week">Week ending <input type="date" id="week-ending" value={week} onChange={save} /></label>
      ) : (
        <span class="rbar-week" id="week-ending-text">{week ? `Week ending ${shownDate(week)}` : "No week ending date yet"}</span>
      )}
      <span class="rbar-state" id="report-state">{editing ? "Editing · each change saves on its own" : published || "Draft · not published yet"}</span>
      {editing ? <span class="rbar-hint" id="report-hint">Drag to move, + to add a template</span> : null}
    </div>
  );
}
