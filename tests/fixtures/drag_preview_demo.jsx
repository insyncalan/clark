// Test-only (tests/test_drag_preview_1214.py): the real Dashboard and Section on a bare page, never part of clark's bundle. The test sets the
// signals edit/drag.js will set (dragFrom, dragList) and the page is drawn from them. window.T.noteRects is components/glide.js.
import { render } from "preact";
import * as store from "@src/stores/report.js";
import { noteRects } from "@src/components/glide.js";
import { Dashboard } from "@src/components/Dashboard.jsx";

const tools = { Gutter: () => null, Title: ({ section }) => <span>{section.title}</span>, richOn: () => false, clean: (h) => h };
window.T = { store, noteRects };
window.mount = (sections, width) => {
  store.data.value = { project: { name: "Example Programme" }, report_sections: sections };
  store.fromFile.value = false;
  store.mode.value = "edit";
  store.dragFrom.value = undefined;
  store.dragList.value = undefined;
  store.dropAt.value = undefined;
  const root = document.getElementById("root");
  render(null, root);
  root.innerHTML = "";
  render(<div id="host" style={{ width: `${width}px` }}><Dashboard tools={tools} /></div>, root);
};
