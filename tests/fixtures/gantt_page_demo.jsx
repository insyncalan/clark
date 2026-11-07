// Test-only (tests/test_gantt_page.py): the Gantt page on a bare page, never part of clark's bundle. window.P.mount(options) draws GanttPage on the
// in-memory host (logic/ganttHost.js) with fictional lines in the stored shape, with the real Toggle pill and title box as the Edit tools. The host
// records every call in host.calls; P.ops/P.lines read what it holds. The slots hold two marked boxes so a test can see where they sit.
import { render } from "preact";
import { mode, fromFile, data } from "@src/stores/report.js";
import { Toggle } from "@src/edit/Toggle.jsx";
import { GanttTitle } from "@src/edit/GanttTitle.jsx";
import { modeKey } from "@src/edit/keys.js";
import { GanttPage } from "@src/gantt/components/GanttPage.jsx";
import { createMemoryHost } from "@src/gantt/logic/ganttHost.js";
import * as page from "@src/gantt/logic/ganttPage.js";

const P = { page };
window.P = P;
document.addEventListener("keydown", modeKey);

const line = (id, name, type, start, end, pct, more = {}) => ({
  id, name, type, parent: "", start, end, pct, health: "", depends: [], owner: "", workstream: "", priority: "", baseline_start: "", baseline_end: "",
  effort: "", budget: "", deliverable: "", show: 0, note: "", sort_order: 0, ...more,
});

// Fictional. Two phases, a clash (GNT-006 starts before GNT-005 ends), a milestone; the eye is on for the phases and the milestone.
P.LINES = [
  line("GNT-001", "Discovery", "phase", "2026-09-01", "2026-10-20", 100, { show: 1, sort_order: 1 }),
  line("GNT-002", "Scan paper files", "task", "2026-09-01", "2026-10-14", 100, { parent: "GNT-001", sort_order: 2 }),
  line("GNT-003", "Records audit complete", "milestone", "2026-10-20", "2026-10-20", 100, { parent: "GNT-001", depends: ["GNT-002"], show: 1, sort_order: 3 }),
  line("GNT-004", "Migration", "phase", "2026-10-22", "2027-02-26", 30, { show: 1, sort_order: 4 }),
  line("GNT-005", "Staff training", "task", "2026-10-22", "2026-12-04", 60, { parent: "GNT-004", depends: ["GNT-003"], sort_order: 5, note: "Room booked" }),
  line("GNT-006", "Move applications", "task", "2026-11-20", "2027-02-12", 20, { parent: "GNT-004", depends: ["GNT-005"], sort_order: 6 }),
];

P.mount = (opts = {}) => {
  const host = createMemoryHost({ project: { name: "Demo project", client_name: "Example client", week_ending: "2026-11-06" }, lines: P.LINES, settings: opts.settings || {}, today: "2026-11-06" });
  P.host = host;
  data.value = { project: host.read().project };      // keys.js acts only with a report open
  fromFile.value = !!opts.fromFile;
  mode.value = opts.mode || "view";
  const root = document.getElementById("root");
  render(null, root);
  root.innerHTML = "";
  window.__exports = 0;
  const tools = opts.fromFile ? null : { Toggle, GanttTitle, exportExcel: () => { window.__exports += 1; } };
  render(<div id="host" style={{ width: `${opts.width || 1000}px` }}>
    <GanttPage host={host} tools={tools} today="2026-11-06"
      above={opts.slots === false ? null : <div id="slot-above-box">Above</div>} below={opts.slots === false ? null : <div id="slot-below-box">Below</div>} />
  </div>, root);
};
P.lines = () => P.host.read().lines;
P.settings = () => P.host.read().settings;
