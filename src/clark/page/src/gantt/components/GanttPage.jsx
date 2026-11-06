// The Gantt tab's page (#926). This is a stand-in with the page's props, so the tab, its address and its name work now; the real Gantt page
// (chart and table, View and Edit) replaces this file and keeps the props: `tools` is what Edit adds (edit/index.js), as every page gets it.
import { data, mode, fromFile } from "../../stores/report.js";
import { tabName } from "../ganttTab.js";

export function GanttPage({ tools }) {      // eslint-disable-line no-unused-vars
  const name = tabName(data.value && data.value.project);
  const editing = !fromFile.value && mode.value === "edit";
  return (
    <section class="frame gantt-page" id="gantt" data-mode={editing ? "edit" : "view"}>
      <h1>{name}</h1>
      <p class="muted">The plan will show here.</p>
    </section>
  );
}
