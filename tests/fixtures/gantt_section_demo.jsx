// Test-only (tests/test_gantt_section.py): the Gantt section's view part and its Edit part on a bare page, never part of clark's bundle.
// window.mountSection(data, {edit}) draws the section as Section.jsx would: the view part from templateFor, the Edit part from templateEdit.
import { render } from "preact";
import * as gantt from "@src/gantt/logic/gantt.js";
import * as section from "@src/gantt/logic/section.js";
import { data, fromFile } from "@src/stores/report.js";
import { templateFor, templateEmpty } from "@src/templates/index.js";
import { templateEdit } from "@src/edit/templates/index.js";

window.K = { gantt, section, templateEmpty };
window.mountSection = (d, opts = {}) => {
  data.value = d;
  fromFile.value = !!opts.file;
  const sec = { id: "S-1", type: "gantt", title: "Gantt", body: "" };
  const root = document.getElementById("root");
  render(null, root);
  root.innerHTML = "";
  const Part = opts.edit ? templateEdit("gantt") : templateFor("gantt").view;
  render(<div id="host" style={{ width: `${opts.width || 1000}px` }}><Part section={sec} data={d} tools={{}} /></div>, root);
};
