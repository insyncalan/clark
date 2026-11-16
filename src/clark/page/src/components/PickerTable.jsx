// Row 1234: "Add a use case from your project record" as a table: a search, a filter icon with a count badge that opens the filter panel
// (PickerFilters.jsx), one row per use case that is not on the page, ticks to choose, "Result: N of M shown", Cancel and "Add N".
// It only picks: the caller gets the ids through onAdd(ids) and saves them. The rules are in logic/useCasePicker.js. Words from the data are text nodes.
import { useState, useRef, useEffect } from "preact/hooks";
import { listOf } from "../logic/useCasesList.js";
import { rowsOf } from "../workItems.js";
import { emptyState, visible, counts, resultWords, addWords, UNRULED_OPEN_STEPS, activeCount, toggleRow, pickAllShown, clearPicked, pickedIds } from "../logic/useCasePicker.js";
import { countWords, NO_MATCH } from "../logic/picker.js";
import { Icon } from "./Icon.jsx";
import { PickerFilters, UNRULED_FILTERS, UNRULED_SEARCH } from "./PickerFilters.jsx";

const COLUMNS = [["ref", "Ref"], ["name", "Use case"], ["headline", "Headline"], ["status", "Status"], ["commitment", "Commitment"], ["steps", UNRULED_OPEN_STEPS], ["total", "Work items"], ["id", "ID"]];

/** The use cases the page does not show yet (the eye is off), as the logic's rows: `steps` is the open work items linked to the use case. */
export const offered = (d) => listOf(d, rowsOf(d)).filter((r) => !r.on).map((r) => ({ ...r, steps: r.open }));

export function PickerTable({ data, onAdd, onClose, title = "Add a use case from your project record" }) {
  const rows = offered(data);
  const [s, setS] = useState(emptyState());
  const [panel, setPanel] = useState(false);
  const search = useRef(null), icon = useRef(null);
  useEffect(() => { if (search.current) search.current.focus(); }, []);
  const shown = visible(rows, s), c = counts(rows, s), n = c.picked, on = new Set(s.picked);
  const closePanel = () => { setPanel(false); if (icon.current) icon.current.focus(); };
  const submit = (e) => { e.preventDefault(); const ids = pickedIds(s, rows); if (ids.length && onAdd) onAdd(ids); };
  const keys = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); if (onClose) onClose(); } };
  const na = activeCount(s);
  return (
    <form class="picker pkt" role="dialog" aria-modal="true" aria-label={title} onSubmit={submit} onKeyDown={keys}>
      <div class="pk-head">
        <h2>{title}</h2>
        <p class="muted">Choose what to add to the page.</p>
      </div>
      <div class="pk-search">
        <label class="pk-q"><span class="sr">Search</span>
          <input ref={search} type="search" placeholder={UNRULED_SEARCH} autocomplete="off" value={s.q} onInput={(e) => setS({ ...s, q: e.currentTarget.value })} />
        </label>
        <button type="button" class="pk-btn pkt-filter" ref={icon} data-filter aria-expanded={panel ? "true" : "false"} aria-controls="pkt-panel" onClick={() => (panel ? closePanel() : setPanel(true))}>
          <Icon name="filter" /><span class="sr">{UNRULED_FILTERS}</span>{na ? <span class="pkt-badge" data-badge>{na}</span> : null}
        </button>
        <button type="button" class="pk-btn" disabled={!shown.length} onClick={() => setS(pickAllShown(s, rows))}>Select all shown</button>
      </div>
      {panel ? <PickerFilters id="pkt-panel" rows={rows} s={s} set={setS} onDone={closePanel} /> : null}
      <div class="pk-body">
        <table class="pkt-table">
          <thead><tr><th></th>{COLUMNS.map(([k, w]) => <th key={k} scope="col">{w}</th>)}</tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id} data-id={r.id} class={on.has(r.id) ? "on" : ""} onClick={(e) => { if (!e.target.closest("input")) setS(toggleRow(s, r.id)); }}>
                <td><input type="checkbox" value={r.id} aria-label={r.name} checked={on.has(r.id)} onChange={() => setS(toggleRow(s, r.id))} /></td>
                {COLUMNS.map(([k]) => <td key={k} class={k === "steps" || k === "total" ? "num" : ""}>{r[k]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length && !shown.length ? <p class="muted pk-none">{NO_MATCH}</p> : null}
      </div>
      <div class="pk-foot">
        <span class="muted pk-count" data-result aria-live="polite">{resultWords(c)}</span>
        <span class="muted" aria-live="polite">{countWords(n)}</span>
        <button type="button" class="pk-btn" onClick={() => { setS(clearPicked(s)); if (onClose) onClose(); }}>Cancel</button>
        <button type="submit" class="pk-btn pri" disabled={!n}>{addWords(c)}</button>
      </div>
    </form>
  );
}
