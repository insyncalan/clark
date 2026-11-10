// The Gantt table section (row 1068), store type "gantttable": its Edit part. The same read-only table the reader sees, and the Gantt section's
// note that the lines are chosen on the Gantt page. Nothing here changes a line. Given { section, tools }.
import { data } from "../../stores/report.js";
import { View } from "../../components/GanttTableSection.jsx";
import { NOTE } from "./GanttSection.jsx";

export function Edit({ section }) {
  return (
    <div class="tple" data-tpl="gantttable">
      <View section={section} data={data.value} />
      <p class="quiet tple-empty" data-tpl-gantt-note>{NOTE}</p>
    </div>
  );
}
