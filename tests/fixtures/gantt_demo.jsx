// Test-only (tests/test_gantt_logic.py and tests/test_gantt_chart.py): the Gantt chart's logic and the chart component on a bare page, never part
// of clark's bundle. window.K is the logic. window.mountGantt(lines, options) draws the chart with fictional lines and plays the part of the page that
// holds it: it keeps the lines, applies each change it is told about, and records every callback in window.calls.
import { render } from "preact";
import { useState } from "preact/hooks";
import * as gantt from "@src/gantt/logic/gantt.js";
import { GanttChart } from "@src/gantt/components/GanttChart.jsx";
import { GANTT_EDIT_WORDS as EW } from "@src/edit/ganttWords.js";

window.K = { gantt };
window.calls = [];

function Host({ first, opts }) {
  const [lines, setLines] = useState(first);
  const [rows, setRows] = useState(opts.defaultRows === undefined ? null : opts.defaultRows);
  const [hidden, setHidden] = useState(opts.hiddenCols || []);
  window.hostLines = () => lines;
  const put = (id, fn) => setLines((all) => all.map((l) => (l.id === id ? fn(l) : l)));
  return (
    <div id="host" style={{ width: `${opts.width || 1000}px` }}>
      <GanttChart eyeWords={{ head: EW.eyeHead, on: EW.eyeTipOn, off: EW.eyeTipOff, detail: EW.eyeDetail }} lines={lines} edit={!!opts.edit} today={opts.today} defaultRows={rows} hiddenCols={hidden}
        onDefaultRows={(n) => { window.calls.push(["rows", n]); setRows(n); }}
        onToggleColumn={(k) => { window.calls.push(["column", k]); setHidden((h) => (h.includes(k) ? h.filter((x) => x !== k) : [...h, k])); }}
        onChange={(id, field, value) => { window.calls.push(["change", id, field, value]); put(id, (l) => (field === "dates" ? { ...l, ...value } : { ...l, [field]: value })); }}
        onToggleEye={(id) => { window.calls.push(["eye", id]); put(id, (l) => ({ ...l, show: !l.show })); }}
        onAdd={(id, type) => { window.calls.push(["add", id, type]); setLines((all) => gantt.addBelow(all, id, type).lines); }}
        onDelete={(id) => { window.calls.push(["delete", id]); setLines((all) => all.filter((l) => l.id !== id)); }} />
    </div>
  );
}

window.mountGantt = (lines, opts = {}) => {
  window.calls.length = 0;
  const root = document.getElementById("root");
  render(null, root);
  root.innerHTML = "";
  render(<Host first={lines} opts={opts} />, root);
};
