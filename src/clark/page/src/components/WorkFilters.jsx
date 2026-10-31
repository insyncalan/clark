// The Work items controls (#64a, option A): the type and Open / Closed / All switches with counts, one "Filter by" row with a
// dot on each active filter, and each filter's box. The rules are in ../filters.js. These controls are never re-created by a
// filter change (only their words and pressed states change), so a click on a second filter while one is open lands first time.
import { useEffect, useLayoutEffect, useRef } from "preact/hooks";
import { rows as allRows, filterState, setFilterState, openFilter, refusals } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { offeredFields, NAMES, MODES, TYPES, counts, typeCounts, isActive, options, setMode, setType, toggleValue, setNot, removeFilter } from "../filters.js";
import { Icon } from "./Icon.jsx";

export function Switches({ children }) {
  const st = filterState.value, today = todayIso(), rows = allRows.value;
  const n = counts(rows, st, today), t = typeCounts(rows, st, today);
  return (
    <div class="wbar">
      <div class="seg" role="group" aria-label="Type">
        {TYPES.map(([v, w]) => <button type="button" key={v} data-type={v} aria-pressed={st.type === v ? "true" : "false"} onClick={() => setFilterState(setType(filterState.value, v))}>{w} <em class="num">{t[v]}</em></button>)}
      </div>
      <div class="seg" role="group" aria-label="Open or closed">
        {MODES.map(([v, w]) => <button type="button" key={v} data-show={v} aria-pressed={st.mode === v ? "true" : "false"} onClick={() => setFilterState(setMode(filterState.value, v))}>{w} <em class="num">{n[v]}</em></button>)}
      </div>
      {children ? <div class="vctl">{children}</div> : null}
    </div>
  );
}

function FilterBox({ field, onClose }) {
  const st = filterState.value, today = todayIso(), box = useRef(null);
  void refusals.value;                                  // a refused tick redraws the box, so the tick goes back
  const opts = options(allRows.value, field, st, today);
  const not = !!st.not[field];
  useEffect(() => { const first = box.current && box.current.querySelector("input"); if (first) first.focus({ preventScroll: true }); }, []);
  useLayoutEffect(() => {      // keep the box inside the window: turn it to the right edge when it would run off
    const el = box.current; if (!el) return;
    el.classList.remove("right");
    if (el.getBoundingClientRect().right > window.innerWidth - 8) el.classList.add("right");
  });
  const set = (next) => setFilterState(next);
  return (
    <div class="fbox" role="group" aria-label={`Filter by ${NAMES[field]}`} id={`fbox-${field}`} ref={box}
      onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(true); } }}>
      <div class="isnot" role="group" aria-label="Match">
        <button type="button" data-not="0" aria-pressed={!not ? "true" : "false"} onClick={() => set(setNot(filterState.value, field, false))}>is any of</button>
        <button type="button" data-not="1" aria-pressed={not ? "true" : "false"} onClick={() => set(setNot(filterState.value, field, true))}>is not</button>
      </div>
      <div class="fact">
        <button type="button" class="btn sm" data-all onClick={() => set(opts.reduce((s, o) => (o.chosen ? s : toggleValue(s, field, o.value)), filterState.value))}>Select all</button>
        <button type="button" class="btn sm" data-none onClick={() => set(removeFilter(filterState.value, field))}>Clear</button>
      </div>
      {opts.map((o) => (
        <label key={o.value}>
          <input type="checkbox" value={o.value} checked={o.chosen} onChange={() => set(toggleValue(filterState.value, field, o.value))} />
          <span>{o.label}</span><span class="c num">{o.count}</span>
        </label>
      ))}
    </div>
  );
}

export function FilterBar() {
  const st = filterState.value, open = openFilter.value, bar = useRef(null);
  const close = (back) => {
    const was = openFilter.value; openFilter.value = "";
    if (back && was && bar.current) { const b = bar.current.querySelector(`[data-fb="${was}"]`); if (b) b.focus(); }
  };
  useEffect(() => {
    if (!open) return;
    const away = (e) => { if (bar.current && !bar.current.contains(e.target)) openFilter.value = ""; };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [open]);
  return (
    <div class="fbar" role="group" aria-label="Filter by" ref={bar}
      onFocusOut={(e) => { if (open && e.relatedTarget && !e.relatedTarget.closest(".fwrap")) openFilter.value = ""; }}>
      <span class="fl">Filter by</span>
      {offeredFields(allRows.value, st).map((f) => (
        <span class="fwrap" key={f}>
          <button type="button" class={`fbtn${isActive(st, f) ? " on" : ""}`} data-fb={f} aria-expanded={open === f ? "true" : "false"} aria-controls={open === f ? `fbox-${f}` : undefined}
            aria-label={NAMES[f] + (isActive(st, f) ? ": filtered" : "")}
            onKeyDown={(e) => { if (e.key === "Escape" && open === f) { e.stopPropagation(); close(true); } }}
            onClick={() => { openFilter.value = openFilter.value === f ? "" : f; }}>
            {NAMES[f]} <Icon name="chevdown" />
          </button>
          {open === f ? <FilterBox field={f} onClose={close} /> : null}
        </span>
      ))}
    </div>
  );
}
