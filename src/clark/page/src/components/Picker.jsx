// "Add from your project record" (FR-16): a searchable list of the rows left out of the report, several chosen at once. It
// only picks: the caller gets the ids through onAdd(ids) and saves them (#65's change path; not built here). Every word
// from the data is a text node, never markup.
import { useState, useRef, useEffect } from "preact/hooks";
import { pickable, idsOf, toggle, selectAll, clear, chosen, countWords, addWords, emptyWords, ALL_ON_PAGE } from "../logic/picker.js";

export function Picker({ data, hiddenIds, onPage, onAdd, onClose }) {
  const [query, setQuery] = useState("");
  const [selection, setSelection] = useState([]);
  const search = useRef(null);
  useEffect(() => { if (search.current) search.current.focus(); }, []);
  const groups = pickable(data, hiddenIds, query, onPage);
  const none = emptyWords(data, hiddenIds, query, onPage);
  const allOnPage = none === ALL_ON_PAGE;
  const n = selection.length;
  const submit = (e) => {
    e.preventDefault();
    const ids = chosen(selection, data, hiddenIds, onPage);
    if (ids.length && onAdd) onAdd(ids);
  };
  const keys = (e) => {
    if (e.key === "Escape") { e.stopPropagation(); if (onClose) onClose(); }
  };
  return (
    <form class="picker" role="dialog" aria-label="Add from your project record" onSubmit={submit} onKeyDown={keys}>
      <div class="pk-head">
        <h2>Add from your project record</h2>
        <p class="muted">{allOnPage ? none : "Choose what to add to the page."}</p>
      </div>
      <div class="pk-search">
        <label class="pk-q"><span class="sr">Search</span>
          <input ref={search} type="search" placeholder="Search by ID or words" autocomplete="off" value={query}
            onInput={(e) => setQuery(e.currentTarget.value)} />
        </label>
        <button type="button" class="pk-btn" disabled={!idsOf(groups).length} onClick={() => setSelection(selectAll(selection, groups))}>Select all shown</button>
      </div>
      <div class="pk-body">
        {groups.map((g) => (
          <section class="pk-group" key={g.kind} aria-label={g.label}>
            <h3>{g.label}</h3>
            <ul class="pick">
              {g.rows.map((r) => (
                <li key={r.id}>
                  <label>
                    <input type="checkbox" value={r.id} checked={selection.includes(r.id)} onChange={() => setSelection(toggle(selection, r.id))} />
                    <span class="pk-text">{r.summary}</span>
                  </label>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {none && !allOnPage ? <p class="muted pk-none">{none}</p> : null}
      </div>
      <div class="pk-foot">
        <span class="muted pk-count" aria-live="polite">{countWords(n)}</span>
        <button type="button" class="pk-btn" onClick={() => { setSelection(clear()); if (onClose) onClose(); }}>Cancel</button>
        <button type="submit" class="pk-btn pri" disabled={!n}>{addWords(n)}</button>
      </div>
    </form>
  );
}
