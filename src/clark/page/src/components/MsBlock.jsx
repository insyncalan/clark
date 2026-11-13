// The milestones block (#44a): the Timeline / Calendar switcher (icon and word, top right), the open view, the rail list and the
// Legend. The same block is the Milestones page, the Dashboard's Milestones section and, in a published file, both places; there
// it starts on Timeline (or the Calendar if its address says mv=cal), shows only what the file holds (its rows are already the client's), and says the client's words.
import { useState } from "preact/hooks";
import { data, asAt, fromFile, openPeek, mv, setMsView } from "../stores/report.js";
import { milestoneRows, todayIso } from "../logic/milestones.js";
import { leftOutIds } from "../logic/picker.js";
import { recall, remember } from "../logic/remember.js";
import { Icon } from "./Icon.jsx";
import { isEditing } from "../logic/editing.js";
import { MsTimeline } from "./MsTimeline.jsx";
import { MsCalendar } from "./MsCalendar.jsx";
import { MsList } from "./MsList.jsx";
import { MsLegend } from "./MsLegend.jsx";

// `tools` is what Edit adds (edit/index.js): the eye on each row, and under the Dashboard's block the line that brings one back. A
// published file, a page in View and a page with no tools have none.
// The Dashboard's block (every place but the Milestones page) holds only what is on the page: a milestone taken off it with the eye
// (report_hidden) or not for the client is not drawn, in View and in Edit, in the timeline, the Calendar and the list alike
// (system/prototype/views.js:355). The Milestones page keeps every milestone, a left-out one marked in words.
export function MsBlock({ place, tools }) {
  const client = fromFile.value, today = client && asAt.value ? asAt.value : todayIso();
  const dash = !client && place !== "page";
  const Eye = !client && tools && tools.MsEye && isEditing() ? tools.MsEye : null;
  const left = dash || Eye ? new Set(leftOutIds(data.value)) : null;      // #520: the ids left out of the published page, built once (the Dashboard's rows and the Eye's marks both read it)
  const rows = milestoneRows(data.value.milestones, today, client).filter((r) => !dash || (r.clientVisible && !left.has(r.id)));
  const CW = Eye && tools.colWidths ? tools.colWidths : null;      // row 1104: the Edit part's column widths hook; the published file and View have none
  const AddBack = dash && tools && tools.MsAddBack && isEditing() ? tools.MsAddBack : null;
  const [kept, setView] = useState(() => (client ? "line" : recall(`msv.${place}`, "line") === "cal" ? "cal" : "line"));
  const view = client ? (mv.value === "cal" ? "cal" : "line") : kept;      // a published file keeps the choice in its address (storage on file:// is not reliable); the editor keeps it in storage
  const choose = (v) => { if (client) setMsView(v); else { remember(`msv.${place}`, v); setView(v); } };
  const open = (id) => openPeek(id, "milestone");   // row 1114: a published file's marks, labels, chips and rows open the file's read only peek, as the editor's open theirs
  if (!rows.length) return <><p class="muted" data-no-milestones>No milestones are shown yet.</p>{AddBack ? <AddBack /> : null}</>;
  return (
    <div class="msv" data-view={view} data-place={place} onClickCapture={Eye && tools.msKeepFocus ? (e) => tools.msKeepFocus(e, dash) : undefined}>
      <div class="msv-sw" role="group" aria-label="Milestone view">
        {[["line", "Timeline"], ["cal", "Calendar"]].map(([v, t]) => (
          <button type="button" key={v} class="msv-b" data-msvb={v} aria-label={t} aria-current={String(view === v)} onClick={() => choose(v)}><Icon name={v === "line" ? "tline" : "cal"} /><span>{t}</span></button>
        ))}
      </div>
      <div class="msv-swap" key={view} data-swap={view}>      {/* a new key on a switch: the new view rises a little and fades in */}
        {view === "cal" ? <MsCalendar rows={rows} today={today} open={open} place={place} client={client} /> : <MsTimeline rows={rows} today={today} place={place} open={open} />}
      </div>
      <MsList CW={CW} rows={rows} place={place} open={open} canFold={!client} internalTag={!client} Eye={Eye} left={left} legend={<MsLegend client={client} id={place} />} />
      {AddBack ? <AddBack /> : null}
    </div>
  );
}
