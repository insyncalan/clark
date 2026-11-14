// Test-only (tests/test_tpl_glance.py): the At a glance template's parts on a bare page, never part of clark's bundle.
// window.mountSection(data, {file, edit, width}) draws the section as Section.jsx would: the view part from templateFor, the Edit part from templateEdit.
import { render } from "preact";
import { data, fromFile } from "@src/stores/report.js";
import { templateFor, templateEmpty } from "@src/templates/index.js";
import { templateEdit } from "@src/edit/templates/index.js";

window.K = { templateEmpty, templateFor, templateEdit };
window.mountSection = (d, opts = {}) => {
  data.value = d;
  fromFile.value = !!opts.file;
  const sec = { id: "S-1", type: "glance", title: "At a glance", body: "" };
  const root = document.getElementById("root");
  render(null, root);
  root.innerHTML = "";
  const Part = opts.edit ? templateEdit("glance") : templateFor("glance").view;
  render(<div id="host" style={{ width: `${opts.width || 1000}px` }}><Part section={sec} data={d} tools={opts.edit ? {} : null} clean={null} /></div>, root);
};
