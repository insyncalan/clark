// Test-only (tests/test_gantt_section.py): the Gantt section's view part and its Edit part on a bare page, never part of clark's bundle.
// window.mountSection(data, {edit, type}) draws the section as Section.jsx would: the view part from templateFor, the Edit part from
// templateEdit; `type` is "gantt" (default) or "gantttable" (row 1068, the Gantt table section).
import { render } from "preact";
import * as gantt from "@src/gantt/logic/gantt.js";
import * as section from "@src/gantt/logic/section.js";
import { data, fromFile, asAt } from "@src/stores/report.js";
import { templateFor, templateEmpty } from "@src/templates/index.js";
import { templateEdit } from "@src/edit/templates/index.js";

window.K = { gantt, section, templateEmpty, templateFor };
window.mountSection = (d, opts = {}) => {
  data.value = d;
  fromFile.value = !!opts.file;
  asAt.value = opts.asAt || "";
  const type = opts.type || "gantt";
  const sec = { id: "S-1", type, title: type === "gantt" ? "Gantt" : "Table", body: "" };
  const root = document.getElementById("root");
  render(null, root);
  root.innerHTML = "";
  const Part = opts.edit ? templateEdit(type) : templateFor(type).view;
  render(<div id="host" style={{ width: `${opts.width || 1000}px` }}><Part section={sec} data={d} tools={{}} /></div>, root);
};
