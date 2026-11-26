// Row 1543 AP8 to AP12 (part 1): the search of a published report. The button is the editor's own (same class, same 38 by 28 box, same
// name "Go to or do" and tooltip); it opens a native <dialog> with the box "Search this report" and the results under it, found by
// logic/reportSearch.js in what the file holds and nothing else. Choosing a result opens the page it is on (the read only panel, the
// keys and Ctrl or Cmd + K are part 2). A published file only: the editor keeps its own palette.
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { data, show, TITLES, asAt } from "../stores/report.js";
import { buildIndex, searchReport } from "../logic/reportSearch.js";

export function ReportSearch() {
  const [open, setOpen] = useState(false);
  const btn = useRef(null), was = useRef(false);
  useEffect(() => { if (was.current && !open && btn.current) btn.current.focus(); was.current = open; }, [open]);      // the box is gone (a modal keeps its page inert while it is open), so focus goes back to the button
  return (
    <>
      <button type="button" class="tb-act" id="pub-search-btn" ref={btn} aria-haspopup="dialog" aria-expanded={open ? "true" : "false"} aria-label="Go to or do" title="Go to or do (Ctrl or Cmd + K)" onClick={() => setOpen(true)}>
        <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="9" cy="9" r="5.5" /><path d="M13 13l4 4" /></svg>
      </button>
      {open ? <Box onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function Box({ onClose }) {
  const el = useRef(null), input = useRef(null);
  const [q, setQ] = useState("");
  const index = useMemo(() => buildIndex(data.value, asAt.value || undefined), [data.value, asAt.value]);
  const results = searchReport(index, q);
  useEffect(() => {
    const d = el.current;
    if (d && !d.open) d.showModal();
    return () => { if (d && d.open) d.close(); };
  }, []);
  const choose = (r) => { onClose(); show(r.view); };
  return (
    <dialog id="report-search" class="dlg rs" aria-label="Go to or do" ref={el} onCancel={(e) => { e.preventDefault(); onClose(); }}>
      <div class="rs-q">
        <input type="search" id="report-search-q" placeholder="Search this report" aria-label="Search this report" autocomplete="off" spellcheck={false} ref={input} value={q} onInput={(e) => setQ(e.currentTarget.value)} />
      </div>
      <ul class="rs-list" aria-label="Results" data-for={q}>
        {results.map((r) => (
          <li key={r.id}><button type="button" class="rs-row" data-kind={r.view} data-id={r.id} onClick={() => choose(r)}>
            <span class="rs-kind">{TITLES[r.view] || r.kind}</span><span class="rs-label">{r.title}</span>
          </button></li>
        ))}
      </ul>
      <p class="rs-none muted" hidden={!q.trim() || results.length > 0}>Nothing matches.</p>
    </dialog>
  );
}
