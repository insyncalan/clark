// The Gantt page (#926, #928): the banner, the toolbar, the plan as a chart or a table, and two empty slots for sections.
// It owns no data. `host` (logic/ganttHost.js) holds the plan and the settings and takes every change; the page asks it, turns the chart's and the
// table's callbacks into steps (logic/ganttPage.js) and hands them back. View and Edit are the Dashboard's own (the `mode` signal, the Toggle pill
// and the plain keys V and E in edit/keys.js), so the page looks and behaves like it.
//
//   host      the page's host (createMemoryHost for now, createStoreHost later)
//   tools     the Edit tools (edit/index.js); without them (a published file) the page is View only and has no title box or pill
//   above     the slot above the plan: a later step mounts the Dashboard's sections here (page scope on the sections table)
//   below     the slot below the plan
//   today     today as YYYY-MM-DD (default: the computer's)
import { useEffect, useState } from "preact/hooks";
import { mode, fromFile } from "../../stores/report.js";
import { Cover } from "../../components/Cover.jsx";
import { Icon } from "../../components/Icon.jsx";
import { coverLine } from "../../logic/cover.js";
import { todayIso } from "../../workItems.js";
import { GanttChart } from "./GanttChart.jsx";
import { GanttTable } from "./GanttTable.jsx";
import { addBelow, filtersFor, filterWord, visibleRows, tidyAll } from "../logic/gantt.js";
import {
  PAGE_WORDS as W, CHART_COLUMNS, toChart, toTable, fromTable, fromChartLine, applyChart, diff, without, renumber, sortLines, hiddenForTable, hiddenFromTable,
} from "../logic/ganttPage.js";

const busy = (el) => !!el && el.nodeType === 1 && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || !!el.closest("[role=textbox],[role=dialog],[role=menu]"));

function useHost(host) {
  const [state, setState] = useState(() => host.read());
  useEffect(() => { setState(host.read()); return host.subscribe(() => setState(host.read())); }, [host]);
  return state;
}

export function GanttPage({ host, tools, above = null, below = null, today }) {
  const { project, settings, lines, toast } = useHost(host);
  const now = today || host.today || todayIso();
  const [layout, setLayout] = useState("chart");              // "chart" | "table": the mode (View or Edit) is kept when this changes
  const [filter, setFilter] = useState("all");                // the chart's names: all | phases | milestones | ticked
  const [showOpen, setShowOpen] = useState(false);
  const editing = !!(tools && tools.Toggle) && mode.value === "edit" && !fromFile.value;
  const Toggle = tools && tools.Toggle && !fromFile.value ? tools.Toggle : null;
  const Title = tools && tools.GanttTitle ? tools.GanttTitle : null;
  const title = settings.gantt_title || project.name || "";
  const hidden = settings.gantt_hidden_columns || [];
  const stored = sortLines(lines);

  // Leaving Edit leaves the "Ticked lines" filter, which View does not have.
  useEffect(() => { if (!editing && filter === "ticked") setFilter("all"); }, [editing]);

  useEffect(() => {      // Cmd or Ctrl+Z, where the host does not leave it to the app's own key (a field, the editor or an open menu keeps its own undo)
    if (!host.ownUndoKey) return undefined;
    const onKey = (e) => {
      if (!editing || !(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey || (e.key !== "z" && e.key !== "Z") || busy(document.activeElement) || busy(e.target)) return;
      e.preventDefault();
      host.undoLast();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [host, editing]);

  useEffect(() => {      // the Show menu closes on a click anywhere else
    if (!showOpen) return undefined;
    const off = (e) => { if (!e.target.closest("[data-gp-showwrap]")) setShowOpen(false); };
    document.addEventListener("pointerdown", off, true);
    return () => document.removeEventListener("pointerdown", off, true);
  }, [showOpen]);

  const send = (after, words) => { const ops = diff(stored, after); if (ops.length) host.applyLines(ops, words); };

  // ── the chart's callbacks ──
  const onChange = (id, field, value) => send(stored.map((l) => (l.id === id ? applyChart(l, field, value) : l)), W.changed(id));
  const onToggleEye = (id) => {
    const line = stored.find((l) => l.id === id);
    if (!line) return;
    const on = !(line.show && line.show !== "0");
    send(stored.map((l) => (l.id === id ? { ...l, show: on ? 1 : 0 } : l)), on ? W.eyeOn(line.name) : W.eyeOff(line.name));
  };
  const onAdd = (afterId, type) => {
    const got = addBelow(toChart(stored), afterId, type);
    const byId = new Map(stored.map((l) => [l.id, l]));
    send(renumber(got.lines.map((c) => byId.get(c.id) || fromChartLine(c))), W.added);
  };
  const onDelete = (id) => send(without(stored, [id]), W.deleted(id));
  const onToggleColumn = (key) => {
    const was = hidden.includes(key);
    host.saveSettings({ gantt_hidden_columns: was ? hidden.filter((k) => k !== key) : [...hidden, key] }, was ? W.colOn(CHART_COLUMNS[key] || key) : W.colOff(CHART_COLUMNS[key] || key));
  };
  const onDefaultRows = (n) => {
    const total = visibleRows(tidyAll(toChart(stored)), { edit: true, filter }).length;
    host.saveSettings({ gantt_plan_rows: n }, n === null || n >= total ? W.rowsAll : W.rows(n, total));
  };

  // ── the table's callbacks: it hands back the whole new list ──
  const onTable = (rows, change) => {
    const after = fromTable(rows);
    const gone = diff(stored, after).filter((o) => o.op === "delete").length;
    send(after, change.type === "add" ? W.added : change.type === "delete" ? (gone === 1 ? W.deleted(change.ids[0]) : W.deletedMany(gone)) : W.changed((change.ids && change.ids[0]) || ""));
  };
  const onTableHidden = (keys) => host.saveSettings({ gantt_hidden_columns: hiddenFromTable(keys) }, W.columnsChanged);

  const saveTitle = (text) => host.saveSettings({ gantt_title: text }, W.titleChanged);
  const tableFilter = filter === "milestones" ? "phasesMilestones" : filter;
  const tableHidden = hiddenForTable(hidden);
  const filters = filtersFor(editing);

  const bar = (
    <div class="gt gp-tools" data-gp-tools>
      <div class="gt-bar" role="toolbar" aria-label="Gantt">
        {Toggle ? (
          <button type="button" class="gt-wd" data-gp-mode={editing ? "view" : "edit"} aria-label={editing ? W.view : W.edit} title={editing ? W.viewTip : W.editTip}
            onClick={() => { mode.value = editing ? "view" : "edit"; }}>
            <Icon name={editing ? "eye" : "pencil"} /> {editing ? W.view : W.edit}
          </button>
        ) : null}
        <button type="button" class="gt-wd" data-gp-layout={layout === "chart" ? "table" : "chart"} aria-label={layout === "chart" ? W.table : W.chart}
          title={layout === "chart" ? W.tableTip : W.chartTip} onClick={() => setLayout(layout === "chart" ? "table" : "chart")}>
          <Icon name={layout === "chart" ? "table" : "bars"} /> {layout === "chart" ? W.table : W.chart}
        </button>
        <span class="gt-sp" />
        {layout === "table" ? (
          <span class="gt-showwrap" data-gp-showwrap>
            <button type="button" class="gt-ib" aria-haspopup="menu" aria-expanded={showOpen} aria-label={`${W.show}: ${filterWord(filter)}`} title={`${W.show}: ${filterWord(filter)}`}
              data-gp-show onClick={() => setShowOpen(!showOpen)}><Icon name="filter" /></button>
            {showOpen ? (
              <div class="gt-pop" role="menu" aria-label={W.show} data-gp-showmenu>
                {filters.map((f) => (
                  <button type="button" key={f} role="menuitemradio" aria-checked={filter === f} data-gp-filter={f} onClick={() => { setFilter(f); setShowOpen(false); }}>
                    <span class="gt-ck" aria-hidden="true">{filter === f ? "✓" : ""}</span>{filterWord(f)}
                  </button>
                ))}
              </div>
            ) : null}
          </span>
        ) : null}
        {editing && layout === "table" ? <button type="button" class="gt-ib" disabled aria-label={W.importXl} title={W.soon} data-gp-import><Icon name="ul" /></button> : null}
        <button type="button" class="gt-ib" disabled aria-label={W.exportXl} title={W.soon} data-gp-export><Icon name="dl" /></button>
      </div>
    </div>
  );

  return (
    <section class="frame report gp" id="gantt-page" data-mode={editing ? "edit" : "view"} data-layout={layout}>
      {Toggle ? <div class="rbar" id="gantt-bar"><Toggle pill /><span class="rbar-state">{editing ? W.editNote : ""}</span></div> : null}
      <Cover title={editing && Title ? <Title text={title} label={W.titleLabel} onSave={saveTitle} /> : title} lines={coverLine(project, fromFile.value ? "" : now)} />
      {above ? <div class="gp-slot gp-above" data-slot="above">{above}</div> : null}
      <div class="gp-plan" data-gp-plan>
        {bar}
        {layout === "chart"
          ? <GanttChart lines={toChart(stored)} edit={editing} today={now} filter={filter} onFilter={setFilter} defaultRows={settings.gantt_plan_rows ?? null}
              onDefaultRows={onDefaultRows} hiddenCols={hidden} onToggleColumn={onToggleColumn} onChange={onChange} onToggleEye={onToggleEye} onAdd={onAdd} onDelete={onDelete} />
          : <GanttTable lines={toTable(stored)} edit={editing} today={now} filter={tableFilter} hidden={tableHidden} onChange={onTable} onHiddenChange={onTableHidden} />}
      </div>
      {below ? <div class="gp-slot gp-below" data-slot="below">{below}</div> : null}
      {toast && toast.text ? (
        <div class="gp-toast" role="status" data-gp-toast>
          {toast.text}
          {toast.undo && editing ? <button type="button" onClick={() => host.undoLast()} data-gp-undo>{W.undo}</button> : null}
        </div>
      ) : null}
    </section>
  );
}
