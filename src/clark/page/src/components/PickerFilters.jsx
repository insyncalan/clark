// Row 1234: the filter panel of the add-a-use-case picker. Two panes: the fields on the left (Status, Commitment, then the More fields group),
// the chosen field's values on the right with "is any of" / "is not any of", Select all, Clear and Done. It holds no state of its own about the
// filters: the state (logic/useCasePicker.js) lives in PickerTable and comes in as `s`, changes go out through `set`.
import { useRef, useEffect, useState } from "preact/hooks";
import { UC_PICKER } from "../logic/useCasePicker.js";

// Words the owner has not ruled on yet (row 1234). Each is one constant so a ruling is one edit; none is typed anywhere else.
export const UNRULED_FILTERS = "Filters";
export const UNRULED_MORE = "More fields";
export const UNRULED_NOT = "is not any of";
export const UNRULED_SEARCH = "Search by name, ID or status";
const IS_ANY = "is any of";                 // existing: the Work items filter says it (WorkFilters.jsx)

export function PickerFilters({ id, rows, s, set, onDone, L = UC_PICKER, kind = {} }) {
  const { fields: FIELDS, optionsOf, setMode, toggleValue, selectAllValues, clearField } = L;
  const [find, setFind] = useState("");
  const [key, setKey] = useState(FIELDS[0].key);
  const first = useRef(null);
  useEffect(() => { if (first.current) first.current.focus(); }, []);
  const f = s.filters[key] || { mode: "is", values: [] };
  const not = f.mode === "not";
  const opts = optionsOf(rows, key);
  const lit = (x) => !find.trim() || x.label.toLowerCase().includes(find.trim().toLowerCase());
  const main = FIELDS.filter((x) => !x.more && lit(x)), more = FIELDS.filter((x) => x.more && lit(x));
  const head = (x) => (
    <li key={x.key}>
      <button type="button" class="pkt-field" data-field={x.key} aria-pressed={x.key === key ? "true" : "false"} ref={x.key === FIELDS[0].key ? first : null}
        onClick={() => setKey(x.key)}>{x.label}{kind.mark && (s.filters[x.key] || { values: [] }).values.length ? <span class="pkt-set" data-set>{kind.mark}</span> : null}</button>
    </li>
  );
  return (
    <div class="pkt-panel" id={id} role="group" aria-label={UNRULED_FILTERS}
      onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onDone(); } }}>
      <ul class="pkt-fields">
        {kind.findField ? <li class="pkt-find"><input type="search" data-find placeholder={kind.findField} aria-label={kind.findField} autocomplete="off" value={find} onInput={(e) => setFind(e.currentTarget.value)} /></li> : null}
        {main.map(head)}
        {more.length ? <li class="pkt-more" aria-hidden="true">{UNRULED_MORE}</li> : null}
        {more.map(head)}
      </ul>
      <div class="pkt-values">
        {kind.isNotButtons ? (
          <div class="isnot" role="group" aria-label="Match">
            <button type="button" data-not="0" aria-pressed={!not ? "true" : "false"} onClick={() => set(setMode(s, key, "is"))}>is</button>
            <button type="button" data-not="1" aria-pressed={not ? "true" : "false"} onClick={() => set(setMode(s, key, "not"))}>is not</button>
            <span class="pkt-any">any of</span>
          </div>
        ) : (
          <div class="isnot" role="group" aria-label="Match">
            <button type="button" data-not="0" aria-pressed={!not ? "true" : "false"} onClick={() => set(setMode(s, key, "is"))}>{IS_ANY}</button>
            <button type="button" data-not="1" aria-pressed={not ? "true" : "false"} onClick={() => set(setMode(s, key, "not"))}>{UNRULED_NOT}</button>
          </div>
        )}
        <div class="fact">
          <button type="button" class="pk-btn" data-all onClick={() => set(selectAllValues(s, key, rows))}>Select all</button>
          <button type="button" class="pk-btn" data-none onClick={() => set(clearField(s, key))}>Clear</button>
        </div>
        <div class="pkt-opts">
          {opts.map((o) => (
            <label key={o.value} class={o.count || f.values.includes(o.value) ? "" : "zero"}>
              <input type="checkbox" value={o.value} checked={f.values.includes(o.value)} disabled={!o.count && !f.values.includes(o.value)} onChange={() => set(toggleValue(s, key, o.value))} />
              <span>{o.value}</span><span class="c num">{o.count}</span>
            </label>
          ))}
        </div>
        <div class="pkt-done"><button type="button" class="pk-btn pri" data-done onClick={onDone}>Done</button></div>
      </div>
    </div>
  );
}
