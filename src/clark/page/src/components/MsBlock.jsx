// The milestones block (#44a): the Timeline / Calendar switcher (icon and word, top right), the open view, the rail list and the
// Legend. The same block is the Milestones page, the Dashboard's Milestones section and, in a published file, both places; there
// it starts on Timeline, shows only what the file holds (its rows are already the client's), and says the client's words.
import { useState } from "preact/hooks";
import { data, asAt, fromFile, mode, openPeek } from "../stores/report.js";
import { milestoneRows, todayIso } from "../logic/milestones.js";
import { recall, remember } from "../logic/remember.js";
import { Icon } from "./Icon.jsx";
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
  const off = dash ? new Set((Array.isArray(data.value.report_hidden) ? data.value.report_hidden : []).map((h) => (h && h.item_id) || h)) : null;
  const rows = milestoneRows(data.value.milestones, today, client).filter((r) => !dash || (r.clientVisible && !off.has(r.id)));
  const AddBack = dash && tools && tools.MsAddBack && mode.value === "edit" ? tools.MsAddBack : null;
  const [view, setView] = useState(() => (client ? "line" : recall(`msv.${place}`, "line") === "cal" ? "cal" : "line"));
  const choose = (v) => { if (!client) remember(`msv.${place}`, v); setView(v); };
  const open = client ? null : (id) => openPeek(id, "milestone");   // a published file has nothing to open: its marks, labels, chips and rows are plain text
  const Eye = !client && tools && tools.MsEye && mode.value === "edit" ? tools.MsEye : null;
  const left = Eye ? new Set((Array.isArray(data.value.report_hidden) ? data.value.report_hidden : []).map((h) => (h && h.item_id) || h)) : null;      // the ids left out of the published page
  if (!rows.length) return <><p class="muted" data-no-milestones>No milestones are shown yet.</p>{AddBack ? <AddBack /> : null}</>;
  return (
    <div class="msv" data-view={view} data-place={place}>
      <div class="msv-sw" role="group" aria-label="Milestone view">
        {[["line", "Timeline"], ["cal", "Calendar"]].map(([v, t]) => (
          <button type="button" key={v} class="msv-b" data-msvb={v} aria-label={t} aria-current={String(view === v)} onClick={() => choose(v)}><Icon name={v === "line" ? "tline" : "cal"} /><span>{t}</span></button>
        ))}
      </div>
      {view === "cal" ? <MsCalendar rows={rows} today={today} open={open} /> : <MsTimeline rows={rows} today={today} place={place} open={open} />}
      <MsLegend client={client} id={place} />
      <MsList rows={rows} place={place} open={open} internalTag={!client} Eye={Eye} left={left} />
      {AddBack ? <AddBack /> : null}
    </div>
  );
}
