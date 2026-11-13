// The Gantt table section (row 1068), store type "gantttable": its Edit part. The same read-only table the reader sees, and the Gantt section's
// note that the lines are chosen on the Gantt page. With no eye-on line (the View's isEmpty, the Gantt section's rule) the chart's own sentence
// stands in for the table, as the Gantt section's Edit says it. Nothing here changes a line. Given { section, tools }.
import { data } from "../../stores/report.js";
import { View, isEmpty } from "../../components/GanttTableSection.jsx";
import { WORDS } from "../../gantt/logic/gantt.js";
import { NOTE } from "./GanttSection.jsx";

export const LEFT_OUT = "No Gantt line has its eye on, so this section is left out of the published page. Turn an eye on on the Gantt page to include it.";

export function Edit({ section }) {
  return (
    <div class="tple" data-tpl="gantttable">
      {isEmpty(section, data.value) ? <p class="gt-none" data-g-none>{WORDS.noLines}</p> : <View section={section} data={data.value} />}
      {isEmpty(section, data.value) ? <p class="quiet tple-empty" data-tpl-gantt-left-out>{LEFT_OUT}</p> : null}
      <p class="quiet tple-empty" data-tpl-gantt-note>{NOTE}</p>
    </div>
  );
}
