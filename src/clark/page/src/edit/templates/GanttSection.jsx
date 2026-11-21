// The Gantt section (#926 part 3), store type "gantt": its Edit part. The same read-only chart the reader sees, and a note that the lines are
// chosen on the Gantt page. Nothing here changes a line. Given { section, tools }.
import { data } from "../../stores/report.js";
import { StartPrompt } from "../StartPrompt.jsx";
import { View, isEmpty } from "../../components/GanttSection.jsx";

export const NOTE = "Lines are chosen on the Gantt page.";

export function Edit({ section }) {
  return (
    <div class="tple" data-tpl="gantt">
      {isEmpty(section, data.value) ? <StartPrompt id="gantt" /> : null}
      <View section={section} data={data.value} />
      <p class="quiet tple-empty" data-tpl-gantt-note>{NOTE}</p>
    </div>
  );
}
