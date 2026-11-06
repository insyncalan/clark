// Test-only (tests/test_gantt_table.py): the Gantt table drawn on a page with the brand and shell styles, never part of clark's bundle.
// The wrapper keeps the lines the way the real page will (the table hands back the whole new list; the wrapper stores it) and records every
// callback in T.calls. T.press sends a key to whatever has focus; T.paste and T.copy go through the real clipboard events.
import { render } from "preact";
import { useState } from "preact/hooks";
import { GanttTable } from "@src/gantt/components/GanttTable.jsx";
import * as grid from "@src/gantt/logic/grid.js";

const T = { grid, calls: [], lines: [], props: {} };
window.T = T;

function Wrapper({ first }) {
  const [lines, setLines] = useState(first);
  const [props, setProps] = useState({ edit: true, hidden: grid.DEFAULT_HIDDEN, filter: "all" });
  T.lines = lines;
  T.setProps = (p) => setProps((q) => ({ ...q, ...p }));
  T.setLines = setLines;
  return (
    <GanttTable lines={lines} today="2026-11-06" {...props}
      onChange={(next, change) => { T.calls.push(["change", change.type, change.ids]); T.lines = next; setLines(next); }}
      onAdd={(a) => T.calls.push(["add", a.id])}
      onDelete={(ids) => T.calls.push(["delete", ids])}
      onHiddenChange={(keys) => { T.calls.push(["hidden", keys]); setProps((q) => ({ ...q, hidden: keys })); }} />
  );
}

T.mount = (lines, props) => {
  document.getElementById("root").innerHTML = '<div id="gt" style="padding:16px;max-width:100%"></div>';
  T.calls = [];
  render(<Wrapper first={lines} />, document.getElementById("gt"));
  if (props) T.setProps(props);
};

const box = () => document.querySelector(".gt-scroll");
const target = () => (document.activeElement && document.activeElement !== document.body ? document.activeElement : box());
T.press = (key, o = {}) => {
  const e = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, metaKey: !!o.meta, shiftKey: !!o.shift, altKey: !!o.alt });
  target().dispatchEvent(e);
  return e.defaultPrevented;
};
T.typeIn = (text) => { const el = document.activeElement; el.value = text; el.dispatchEvent(new Event("input", { bubbles: true })); };
T.cell = (r, c) => document.querySelector(`td[data-r="${r}"][data-c="${c}"]`);
T.mouse = (el, type, o = {}) => el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, shiftKey: !!o.shift, clientX: o.x || 0, clientY: o.y || 0, button: o.button || 0 }));
T.click = (r, c, o = {}) => { const td = T.cell(r, c); T.mouse(td, "mousedown", o); T.mouse(td, "mouseup", o); };
T.paste = (text) => { const dt = new DataTransfer(); dt.setData("text/plain", text); box().dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true })); };
T.copy = () => { const dt = new DataTransfer(); box().dispatchEvent(new ClipboardEvent("copy", { clipboardData: dt, bubbles: true, cancelable: true })); return dt.getData("text/plain"); };
T.state = () => {
  const act = document.querySelector("td.gt-act");
  return {
    act: act ? [+act.dataset.r, +act.dataset.c] : null,
    sel: document.querySelectorAll("td.gt-sel, td.gt-act").length,
    editing: !!document.querySelector("td.gt-ed"),
    msg: (document.querySelector(".gt-msg") || {}).textContent || "",
    bad: (document.querySelector(".gt-msg") || {}).dataset ? document.querySelector(".gt-msg").dataset.gtMsg : "",
    rows: document.querySelectorAll("tbody tr").length,
    heads: [...document.querySelectorAll("thead th[data-k]")].map((h) => h.dataset.k),
    rowNumbers: [...document.querySelectorAll(".gt-rn")].map((n) => n.textContent),
  };
};
