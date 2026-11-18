// Test-only (tests/test_import_box_keys.py): the real Import workbook box on a bare page with a stub api. Never part of clark's bundle.
import { render } from "preact";
import { ImportWorkbook } from "@src/edit/ImportWorkbook.jsx";

const T = { closed: 0, plan: null, undoBody: {}, hold: false, release: null };
window.T = T;

const api = {
  sheets: async () => ({ ok: true, body: { file: "k", sheets: [] } }),
  check: async () => ({ ok: true, body: T.plan }),
  apply: () => new Promise((res) => {
    const done = () => res({ ok: true, body: { message: "Imported 1 change.", apply_id: "a1" } });
    if (T.hold) T.release = done; else done();
  }),
  undo: async () => ({ ok: true, body: T.undoBody }),
};

// The other plan fields the box reads are filled in here.
T.open = (items, o = {}) => {
  T.closed = 0; T.undoBody = o.undoBody || {}; T.hold = !!o.hold;
  T.plan = { file: "w.xlsx", plan: "p", items, counts: { new: items.length, changed: 0 }, problems: [], notes: [], refused: [] };
  document.getElementById("root").innerHTML = '<button id="opener" type="button">Open</button><div id="host"></div>';
  document.getElementById("opener").focus();
  render(<ImportWorkbook project="p" projectName="Proj" opener={document.getElementById("opener")} api={api}
    read={async () => new Uint8Array([1])} onClose={() => { T.closed += 1; render(null, document.getElementById("host")); }} onDone={() => {}} />,
  document.getElementById("host"));
};
T.choose = () => {
  const dt = new DataTransfer();
  dt.items.add(new File(["x"], "w.xlsx"));
  const i = document.getElementById("import-file");
  i.files = dt.files;
  i.dispatchEvent(new Event("change", { bubbles: true }));
};
