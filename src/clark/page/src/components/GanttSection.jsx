// The Gantt as a Dashboard section (#926 part 3), store type "gantt": its view part. The plan drawn as bars on a timeline from the report's
// Gantt lines, read only and full width. Only the lines put on the dashboard (eye on) are drawn, and only the columns not hidden from the
// client; the chart is the one the Gantt page draws (gantt/components/GanttChart.jsx) with edit off, so it has no editing controls.
// The zoom, scale and expand buttons are the chart's own. It draws from the report's data only (no server call), so the served View and
// the published file read alike. isEmpty: true leaves the section out of the served View and the published file.
import { data as reportData, fromFile, asAt } from "../stores/report.js";
import { GanttChart } from "../gantt/components/GanttChart.jsx";
import { linesOf, hiddenOf, savedRows, isEmptyData } from "../gantt/logic/section.js";

export const READY = true;

export const isEmpty = (section, data) => isEmptyData(data);

export function View({ data }) {
  const d = data || reportData.value;
  const today = fromFile.value && asAt.value ? asAt.value : undefined;
  return (
    <div class="tpl-gantt" data-tpl="gantt">
      <GanttChart lines={linesOf(d)} edit={false} today={today} defaultRows={savedRows(d)} hiddenCols={hiddenOf(d)} />
    </div>
  );
}
