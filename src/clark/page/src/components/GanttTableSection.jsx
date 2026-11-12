// The Gantt table as a Dashboard section (row 1068), store type "gantttable": its view part. The plan as the Gantt page's table alone, no
// timeline and no bars, from the report's Gantt lines, read only, full or half width (the table scrolls sideways in a half). Only the lines
// put in the client view (eye on) are drawn, and only the columns not hidden from the client; the table is the one the Gantt page draws
// (gantt/components/GanttTable.jsx) with edit off, so it has no editing controls (the zoom buttons are the table's own). The lines and the
// hidden columns are read as the Gantt tab reads them (gantt/logic/ganttFileHost.js: the served page from the project's lines and settings,
// a published file from data.gantt, where a column the file does not carry is hidden), so the served View and the published file read
// alike; nothing is fetched. It is a template section like the others, not the Gantt tab's: it does not ask the project's client switch
// (publish.py puts the eye-on lines in the file for it with or without the tab). isEmpty is the Gantt section's: no eye-on line leaves the
// section out of the served View and the published file, as the server leaves it out.
import { data as reportData, fromFile, asAt } from "../stores/report.js";
import { GanttTable } from "../gantt/components/GanttTable.jsx";
import { readFile, readStore } from "../gantt/logic/ganttFileHost.js";
import { toTable, hiddenForTable, onlyHideable } from "../gantt/logic/ganttPage.js";
import { isEmptyData } from "../gantt/logic/section.js";
import { todayIso } from "../workItems.js";

export const READY = true;

export const isEmpty = (section, data) => isEmptyData(data);

export function View({ data }) {
  const d = data || reportData.value;
  const { settings, lines } = fromFile.value ? readFile(d) : readStore(d);
  const today = fromFile.value && asAt.value ? asAt.value : todayIso();      // a published file is as at the day it was published
  return (
    <div class="tpl-gantttable" data-tpl="gantttable">
      <GanttTable lines={toTable(lines)} edit={false} today={today} hidden={hiddenForTable(onlyHideable(settings.gantt_hidden_columns))} />
    </div>
  );
}
