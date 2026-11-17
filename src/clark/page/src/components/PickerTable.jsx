// Row 1234: "Add a use case from your project record" as a table: a search, a filter icon with a count badge that opens the filter panel
// (PickerFilters.jsx), one row per use case that is not on the page, ticks to choose, "Result: N of M shown", Cancel and "Add N".
// It only picks: the caller gets the ids through onAdd(ids) and saves them. The rules are in logic/useCasePicker.js. Words from the data are text nodes.
import { useState, useRef, useEffect } from "preact/hooks";
import { listOf } from "../logic/useCasesList.js";
import { rowsOf } from "../workItems.js";
import { UC_PICKER, UNRULED_OPEN_STEPS } from "../logic/useCasePicker.js";
import { countWords, NO_MATCH, ALL_ON_PAGE } from "../logic/picker.js";
import { Icon } from "./Icon.jsx";
import { MsMark } from "./MsMark.jsx";
import { PickerFilters, UNRULED_FILTERS, UNRULED_SEARCH } from "./PickerFilters.jsx";

const COLUMNS = [["ref", "Ref"], ["name", "Use case"], ["headline", "Headline"], ["status", "Status"], ["commitment", "Commitment"], ["steps", UNRULED_OPEN_STEPS], ["total", "Work items"], ["id", "ID"]];
const NUM = ["steps", "total", "progress"];

/** The use case picker's kind: its rules (logic/useCasePicker.js), columns, rows and words. Row 1230's milestone picker hands its own (logic/msPicker.js) to the same table. */
export const UC_KIND = { L: UC_PICKER, columns: COLUMNS, search: UNRULED_SEARCH, tick: false };

/** The use cases the page does not show yet (the eye is off), as the logic's rows: `steps` is the open work items linked to the use case. */
export const offered = (d) => listOf(d, rowsOf(d)).filter((r) => !r.on).map((r) => ({ ...r, steps: r.open }));

export function PickerTable({ data, onAdd, onClose, title = "Add a use case from your project record", kind = UC_KIND, rows: given }) {
  const { L, columns, search: placeholder, tick, filtersLabel = (n) => UNRULED_FILTERS, tickLabel = (r) => r.name } = kind;
  const rows = given || offered(data);
  const [s, setS] = useState(L.emptyState());
  const [panel, setPanel] = useState(false);
  const search = useRef(null), icon = useRef(null);
  useEffect(() => { if (search.current) search.current.focus(); }, []);
  const shown = L.visible(rows, s), c = L.counts(rows, s), n = c.picked, on = new Set(s.picked);
  const all = useRef(null);
  useEffect(() => { if (all.current) all.current.indeterminate = L.someShownPicked(rows, s) && !L.allShownPicked(rows, s); });
  const closePanel = () => { setPanel(false); if (icon.current) icon.current.focus(); };
  const submit = (e) => { e.preventDefault(); const ids = L.pickedIds(s, rows); if (ids.length && onAdd) onAdd(ids); };
  const keys = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); if (onClose) onClose(); } };
  const na = L.activeCount(s);
  return (
    <form class="picker pkt" role="dialog" aria-modal="true" aria-label={title} onSubmit={submit} onKeyDown={keys}>
      <div class="pk-head">
        <h2>{title}</h2>
        {rows.length ? <p class="muted">Choose what to add to the page.</p> : <p class="muted" data-empty>{ALL_ON_PAGE}</p>}
      </div>
      <div class="pk-search">
        <label class="pk-q"><span class="sr">Search</span>
          <input ref={search} type="search" placeholder={placeholder} autocomplete="off" value={s.q} onInput={(e) => setS({ ...s, q: e.currentTarget.value })} />
        </label>
        <button type="button" class="pk-btn pkt-filter" ref={icon} data-filter aria-expanded={panel ? "true" : "false"} aria-controls="pkt-panel" onClick={() => (panel ? closePanel() : setPanel(true))}>
          <Icon name="filter" /><span class="sr">{filtersLabel(na)}</span>{na ? <span class="pkt-badge" data-badge>{na}</span> : null}
        </button>
        {tick ? null : <button type="button" class="pk-btn" disabled={!shown.length} onClick={() => setS(L.pickAllShown(s, rows))}>Select all shown</button>}
      </div>
      {panel ? <PickerFilters id="pkt-panel" L={L} kind={kind} rows={rows} s={s} set={setS} onDone={closePanel} /> : null}
      <div class="pk-body">
        <table class="pkt-table">
          <thead><tr>
            <th class="pkt-tick">{tick ? <input ref={all} type="checkbox" data-all-shown aria-label="Select all shown" disabled={!shown.length} checked={L.allShownPicked(rows, s)} onChange={() => setS(L.toggleAllShown(s, rows))} /> : null}</th>
            {columns.map(([k, w]) => <th key={k} scope="col" class={NUM.includes(k) ? "num" : ""}>{w}</th>)}
          </tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id} data-id={r.id} class={on.has(r.id) ? "on" : ""} onClick={(e) => { if (!e.target.closest("input")) setS(L.toggleRow(s, r.id)); }}>
                <td><input type="checkbox" value={r.id} aria-label={tickLabel(r)} checked={on.has(r.id)} onChange={() => setS(L.toggleRow(s, r.id))} /></td>
                {columns.map(([k]) => <td key={k} class={NUM.includes(k) ? "num" : ""}>{k === "name" && kind.marks ? <span class="pkt-name"><MsMark name={r.mark} />{r.name}</span> : r[k]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length && !shown.length ? <p class="muted pk-none">{NO_MATCH}</p> : null}
      </div>
      <div class="pk-foot">
        <span class="muted pk-count" data-result aria-live="polite">{L.resultWords(c)}</span>
        <span class="muted" aria-live="polite">{countWords(n)}</span>
        <button type="button" class="pk-btn" onClick={() => { setS(L.clearPicked(s)); if (onClose) onClose(); }}>Cancel</button>
        <button type="submit" class="pk-btn pri" disabled={!n}>{L.addWords(c)}</button>
      </div>
    </form>
  );
}
