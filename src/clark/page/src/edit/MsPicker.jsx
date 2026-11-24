// Row 1230 (picker PR): the Add a milestone box. A table of the milestones that are not on the page (taken off with the eye, or not for
// the client) with a tick on each row, a filter panel (Status, Due, On the page, Client-visible: is / is not any of) and one Add for the
// ticked ones. It only picks: the caller gets the ids through onAdd(ids) (edit/actions.js addMilestonesBack). The rules are in
// logic/msPicker.js; every word from the data is a text node. The shared components/Picker.jsx is untouched (other kinds use it).
import { useState, useRef, useEffect } from "preact/hooks";
import { MsMark } from "../components/MsMark.jsx";
import { Icon } from "../components/Icon.jsx";
import { todayIso, agreedText, expectedCell } from "../logic/milestones.js";
import { toggle } from "../logic/picker.js";
import { offered, shownRows, counts, filtersOn, options, resultWords, selectedWords, addWords, FIELDS, MORE, FIELD_NAME } from "../logic/msPicker.js";

const TITLE = "Add a milestone from your project record";

function Panel({ rows, today, filter, setFilter, total, shown, onDone }) {
  const [field, setField] = useState("status");
  const [find, setFind] = useState("");
  const q = find.trim().toLowerCase(), pick = (a) => a.filter((k) => !q || FIELD_NAME[k].toLowerCase().includes(q));
  const on = (f) => (filter.sel[f] || []).length > 0;
  const setSel = (f, v) => setFilter({ ...filter, sel: { ...filter.sel, [f]: v } });
  const row = (k) => <button type="button" key={k} class={`frow${k === field ? " sel" : ""}`} data-pkf={k} aria-pressed={String(k === field)} onClick={() => setField(k)}>{FIELD_NAME[k]}{on(k) ? <span>set</span> : null}</button>;
  const cs = counts(rows, filter, field, today), vals = filter.sel[field] || [];
  return (
    <div class="fpan" role="dialog" aria-label="Filters">
      <div class="fl-l">
        <input type="search" placeholder="Find a field..." autocomplete="off" aria-label="Find a field" value={find} onInput={(e) => setFind(e.currentTarget.value)} />
        {pick(FIELDS).map(row)}
        {pick(MORE).length ? <h4>More fields</h4> : null}
        {pick(MORE).map(row)}
      </div>
      <div class="fl-r">
        <h3>{FIELD_NAME[field]}</h3>
        <div class="isnot">
          <button type="button" data-pkn="0" aria-pressed={String(!filter.not[field])} onClick={() => setFilter({ ...filter, not: { ...filter.not, [field]: false } })}>is</button>
          <button type="button" data-pkn="1" aria-pressed={String(!!filter.not[field])} onClick={() => setFilter({ ...filter, not: { ...filter.not, [field]: true } })}>is not</button>
          <span>any of</span>
        </div>
        <div class="fact">
          <button type="button" class="pk-btn" data-pks onClick={() => setSel(field, options(field).map((o) => o[0]))}>Select all</button>
          <button type="button" class="pk-btn" data-pkz onClick={() => setSel(field, [])}>Clear</button>
        </div>
        <div class="fopts">
          {options(field).map(([v, label]) => {
            const c = (cs.find((x) => x[0] === v) || [0, 0])[1], has = vals.includes(v);
            return (
              <label key={v} class={c || has ? "" : "zero"}>
                <input type="checkbox" data-pkv={v} checked={has} disabled={!c && !has} onChange={() => setSel(field, toggle(vals, v))} />
                <span>{label}</span><span class="c">{c}</span>
              </label>
            );
          })}
        </div>
        <div class="fres"><span>{resultWords(shown, total)}</span><button type="button" class="pk-btn pri" data-pkd onClick={onDone}>Done</button></div>
      </div>
    </div>
  );
}

export function MsPicker({ data, leftOut, onAdd, onClose }) {
  const today = todayIso();
  const rows = offered(data, leftOut, today);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState({ sel: {}, not: {} });
  const [pan, setPan] = useState(false);
  const [selection, setSelection] = useState([]);
  const search = useRef(null), head = useRef(null);
  useEffect(() => { if (search.current) search.current.focus(); }, []);
  const list = shownRows(rows, { ...filter, query }, today);
  const ids = list.map((r) => r.id), k = ids.filter((id) => selection.includes(id)).length, n = selection.length;
  useEffect(() => { if (head.current) head.current.indeterminate = k > 0 && k < ids.length; });
  const nOn = filtersOn(filter);
  const submit = (e) => {
    e.preventDefault();
    const have = new Set(rows.map((r) => r.id)), go = selection.filter((id) => have.has(id));
    if (go.length && onAdd) onAdd(go);
  };
  const keys = (e) => { if (e.key === "Escape") { e.stopPropagation(); if (onClose) onClose(); } };
  const empty = !rows.length;
  return (
    <form class="picker ms-pk" role="dialog" aria-label={TITLE} onSubmit={submit} onKeyDown={keys}>
      <div class="pk-head">
        <h2>{TITLE}</h2>
        <p class="muted">{empty ? "Everything is already on the page." : "Choose what to add to the page."}</p>
      </div>
      <div class="pk-search">
        <label class="pk-q"><span class="sr">Search</span>
          <input ref={search} type="search" placeholder="Search by name, ID or state" autocomplete="off" value={query} onInput={(e) => setQuery(e.currentTarget.value)} />
        </label>
        <button type="button" class={`ficon${nOn ? " on" : ""}`} data-pkp aria-label={nOn ? `Filters, ${nOn} on` : "Filters"} aria-expanded={String(pan)} onClick={() => setPan(!pan)}>
          <Icon name="filter" />{nOn ? <i>{nOn}</i> : null}
        </button>
      </div>
      {pan ? <Panel rows={rows} today={today} filter={filter} setFilter={setFilter} total={rows.length} shown={list.length} onDone={() => setPan(false)} /> : null}
      <div class="pk-body">
        {empty ? null : !list.length ? <p class="muted pk-none">Nothing matches your search. Clear it to see what can be added.</p> : (
          <table class="pkt">
            <thead><tr>
              <th class="c1"><input ref={head} type="checkbox" data-pksa aria-label="Select all shown" checked={ids.length > 0 && k === ids.length} onChange={(e) => setSelection(e.currentTarget.checked ? [...selection, ...ids.filter((id) => !selection.includes(id))] : selection.filter((id) => !ids.includes(id)))} /></th>
              <th>Milestone</th><th>State</th><th>Agreed</th><th>Expected or achieved</th><th class="r">Progress</th><th>Where it is</th><th>ID</th>
            </tr></thead>
            <tbody>
              {list.map((r) => {
                const ex = expectedCell(r), pct = r.percent === null || r.percent === "" || !Number.isFinite(Number(r.percent)) ? "—" : `${Math.round(Number(r.percent))}%`;
                return (
                  <tr key={r.id} data-prow={r.id} onClick={(e) => { if (e.target.tagName !== "INPUT") setSelection(toggle(selection, r.id)); }}>
                    <td class="c1"><input type="checkbox" value={r.id} aria-label={`Add ${r.name}`} checked={selection.includes(r.id)} onChange={() => setSelection(toggle(selection, r.id))} /></td>
                    <td class="nm"><span class="mkc"><MsMark name={r.mark} /></span>{r.name}</td>
                    <td>{r.word}</td>
                    <td>{agreedText(r)}</td>
                    <td>{ex.date}</td>
                    <td class="r">{pct}</td>
                    <td><span class="why">{r.why}</span></td>
                    <td class="id">{r.id}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <div class="pk-foot">
        <span class="muted pk-count" aria-live="polite">{selectedWords(n)}</span>
        <button type="button" class="pk-btn" onClick={onClose}>Cancel</button>
        <button type="submit" class="pk-btn pri" disabled={false}>{addWords(n)}</button>
      </div>
    </form>
  );
}
