// Row 1543 AP8 to AP12: the search of a published report. The button is the editor's own (same class, same 38 by 28 box, same
// name "Go to or do" and tooltip); it opens a native <dialog> with the box "Search this report" and the results under it, found by
// logic/reportSearch.js in what the file holds and nothing else. Choosing a result opens the page it is on (the read only panel). Part 2: Ctrl or Cmd + K opens
// it (one listener while the report is up), Esc closes it (the dialog's cancel), Up and Down walk the results and Enter opens the chosen one. A published file only: the editor keeps its own palette.
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { narrowHeader } from "../logic/narrowHeader.js";
import { data, show, TITLES, asAt } from "../stores/report.js";
import { buildIndex, searchReport, boxKey, isShortcut } from "../logic/reportSearch.js";

export const searchOpen = signal(false);      // the one open state: the button (wide) and the report menu entry (900 px and narrower) both set it

export function ReportSearch() {
  const open = searchOpen.value, setOpen = (v) => { searchOpen.value = v; };
  const btn = useRef(null), was = useRef(false);
  useEffect(() => {
    const onKey = (e) => { if (isShortcut(e)) { e.preventDefault(); if (!e.repeat) setOpen(true); } };      // Ctrl or Cmd + K opens it (and keeps the browser's own use of the keys away)
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, []);
  useEffect(() => { if (was.current && !open && btn.current) btn.current.focus(); was.current = open; }, [open]);      // the box is gone (a modal keeps its page inert while it is open), so focus goes back to the button
  return (
    <>
      {narrowHeader.value ? null : (
        <button type="button" class="tb-act" id="pub-search-btn" ref={btn} aria-haspopup="dialog" aria-expanded={open ? "true" : "false"} aria-label="Go to or do" title="Go to or do (Ctrl or Cmd + K)" onClick={() => setOpen(true)}>
          <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="9" cy="9" r="5.5" /><path d="M13 13l4 4" /></svg>
        </button>
      )}
      {open ? <Box onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function Box({ onClose }) {
  const el = useRef(null), input = useRef(null);
  const [q, setQ] = useState("");
  const index = useMemo(() => buildIndex(data.value, asAt.value || undefined), [data.value, asAt.value]);
  const results = searchReport(index, q);
  const [pick, setPick] = useState({ q: "", at: 0 });
  const chosen = results.length ? (pick.q === q ? Math.min(pick.at, results.length - 1) : 0) : -1;      // the first result is chosen as soon as there is one, and again for every new words (the pick remembers the words it was made for, so no effect can undo a key pressed before it runs)
  useEffect(() => { const r = el.current && el.current.querySelector(".rs-row[data-active]"); if (r && r.scrollIntoView) r.scrollIntoView({ block: "nearest" }); }, [chosen]);
  useEffect(() => {
    const d = el.current;
    if (d && !d.open) d.showModal();
    return () => { if (d && d.open) d.close(); };
  }, []);
  const choose = (r) => { onClose(); show(r.view); };
  const onKey = (e) => {
    const k = boxKey(e, results.length, chosen);
    if (!k) return;
    e.preventDefault();
    if (k.do === "move") setPick({ q, at: k.at }); else choose(results[k.at]);
  };
  return (
    <dialog id="report-search" class="dlg rs" aria-label="Go to or do" ref={el} onCancel={(e) => { e.preventDefault(); onClose(); }}>
      <div class="rs-q">
        <input type="search" id="report-search-q" placeholder="Search this report" aria-label="Search this report" autocomplete="off" spellcheck={false} style={{ boxSizing: "border-box", width: "100%", minHeight: "36px" }} ref={input} onKeyDown={onKey} role="combobox" aria-expanded={results.length ? "true" : "false"} aria-controls="report-search-list" aria-activedescendant={chosen >= 0 ? "rs-opt-" + chosen : undefined} value={q} onInput={(e) => setQ(e.currentTarget.value)} />
      </div>
      <ul class="rs-list" id="report-search-list" role="listbox" aria-label="Results" data-for={q}>
        {results.map((r, i) => (
          <li key={r.id} role="presentation"><button type="button" class="rs-row" id={"rs-opt-" + i} role="option" aria-selected={i === chosen ? "true" : "false"} data-active={i === chosen ? "1" : undefined} tabIndex={-1} data-kind={r.view} data-id={r.id} onClick={() => choose(r)}>
            <span class="rs-kind">{TITLES[r.view] || r.kind}</span><span class="rs-label">{r.title}</span>
          </button></li>
        ))}
      </ul>
      <p class="rs-none muted" hidden={!q.trim() || results.length > 0}>Nothing matches.</p>
    </dialog>
  );
}
