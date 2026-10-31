// The Use cases page (the editor's page, in the main navigation beside Milestones): every use case of the project, selected for the
// dashboard or not, and one use case's own page when the address names one (#usecases&p=CODE&uc=1.2, drawn by UseCaseDetail).
// A row: its reference, its name (the button that opens it), where it stands, the status in words with a dot, the linked work items
// and how many are open, the linked milestones, and the eye in words. The eye is the dashboard's own switch (use_cases.client_visible),
// changed through the one change path with its Undo toast, in Edit; in View the same words are shown and nothing changes.
// The list is ONE tab stop (the current row's name): Up and Down move between rows, Home and End to the first and last, Right to the
// row's eye and Left back to its name. The search, the Status choice, the On the dashboard switch and the sort are remembered for each
// project in this browser (logic/useCasesList.js), never in the address, so they add no Back entry.
import { signal, computed } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { data, rows as allRows, project, uc, mode, openUseCase } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { cameBackFrom } from "../stores/useCaseFocus.js";
import { listOf, ucFor, tidy, recalled, keep, shownOf, onCounts, narrowed, countWords, rowSay, STATUS_WORDS, ON_WORDS, OFF_WORDS, SORTS } from "../logic/useCasesList.js";
import { UseCaseDetail } from "../components/UseCaseDetail.jsx";
import { Menu } from "../components/Menu.jsx";
import { Icon } from "../components/Icon.jsx";

const RAG = { "On track": "g", Flag: "a", "High risk": "r" };
const kept = {};                                              // project -> state: a browser that refuses storage still narrows the list
const tick = signal(0);
const state = computed(() => { void tick.value; const code = project.value; return kept[code] || recalled(code); });
const all = computed(() => (data.value ? listOf(data.value, allRows.value) : []));
const current = signal("");                                   // the id of the row that is the list's one tab stop
const statusOpen = signal(false);
let returning = "";                                           // the use case just left by Back: its row takes the focus when the list comes back

function set(patch) {
  const code = project.value;
  kept[code] = tidy({ ...state.value, ...patch });
  keep(code, kept[code]);
  tick.value++;
}

function setEye(r, rowsShown) {
  const on = !r.on, at = rowsShown.findIndex((x) => x.id === r.id), next = (rowsShown[at + 1] || rowsShown[at - 1] || {}).id;
  const name = r.ref || "Use case";
  change({ kind: "use_cases", op: "update", id: r.id, changes: { client_visible: on ? 1 : 0 } },
    `${name} is ${on ? "on the dashboard" : "no longer on the dashboard"}.`).then(() => setTimeout(() => {
    // the row stays (or leaves the list, when the switch is narrowed to the other kind): the focus stays with it or goes to its neighbour
    const q = (id, sel) => document.querySelector(`#usecases [data-uc="${CSS.escape(id)}"] ${sel}`);
    const el = q(r.id, ".ucl-eye") || (next && (q(next, ".ucl-eye") || q(next, ".ucl-go")));
    if (el) el.focus({ preventScroll: true });
  }, 60));
}

function Row({ r, edit, stop, shown }) {
  const open = () => { returning = r.id; openUseCase(r.id); };
  const ms = r.ms.length ? r.ms.map((m) => m.name).join("; ") : "";
  const eyeWords = r.on ? ON_WORDS : OFF_WORDS;
  return (
    <li class={`ucl-row${r.on ? "" : " off"}`} data-uc={r.id}
      onClick={(e) => { if (e.target.closest("button, a, input") || String(getSelection()).trim()) return; open(); }}>
      <span class="ucl-ref num">{r.ref || "Use case"}</span>
      <span class="ucl-name">
        <button type="button" class="ucl-go" tabIndex={stop ? 0 : -1} aria-label={rowSay(r)} title={`Open ${r.name}`} onFocus={() => { current.value = r.id; }} onClick={open}>{r.name}</button>
        <small>{r.headline || "No headline yet"}</small>
        {ms ? <small class="ucl-ms-s">Milestones: {ms}</small> : null}
      </span>
      <span class="ucl-head" title={r.headline}>{r.headline || "No headline yet"}</span>
      <span class="ucl-st"><span class={`pill ${RAG[r.status] || "n"}`} data-status>{r.status}</span></span>
      <span class="ucl-wi num">{r.total ? <><b>{r.total}</b> linked<small>{r.open} open</small></> : "None linked"}</span>
      <span class="ucl-ms">{ms || <span class="muted">None</span>}</span>
      {edit
        ? <button type="button" class="ucl-eye" tabIndex={-1} data-eye aria-label={`${r.ref || "Use case"} ${r.name}: ${eyeWords}. ${r.on ? "Take it off the dashboard" : "Put it on the dashboard"}`}
            onFocus={() => { current.value = r.id; }} onClick={() => setEye(r, shown)}><Icon name={r.on ? "eye" : "eyeoff"} /><span>{eyeWords}</span></button>
        : <span class="ucl-eye ucl-eye-ro" data-eye-words><Icon name={r.on ? "eye" : "eyeoff"} /><span>{eyeWords}</span></span>}
    </li>
  );
}

// The list's keys, taken only when focus is on a row's name or eye, so the search box and the filters keep their own keys.
function keys(e) {
  const t = e.target, k = e.key;
  if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.isComposing || e.defaultPrevented || !t.closest) return;
  const row = t.closest(".ucl-row");
  if (!row || !t.matches(".ucl-go, .ucl-eye")) return;
  const eye = t.classList.contains("ucl-eye"), rows = [...e.currentTarget.querySelectorAll(".ucl-list .ucl-row")], at = rows.indexOf(row);
  const focus = (el) => { if (el) { e.preventDefault(); el.focus(); } };
  if (k === "ArrowRight") return focus(row.querySelector(".ucl-eye"));
  if (k === "ArrowLeft") return focus(row.querySelector(".ucl-go"));
  const to = { ArrowUp: at - 1, ArrowDown: at + 1, Home: 0, End: rows.length - 1 }[k];
  if (to === undefined) return;
  e.preventDefault();
  const r = rows[Math.max(0, Math.min(rows.length - 1, to))];
  (eye ? r.querySelector(".ucl-eye") || r.querySelector(".ucl-go") : r.querySelector(".ucl-go")).focus();
}

function StatusFilter({ f }) {
  const box = useRef(null), wrap = useRef(null), open = statusOpen.value;
  useEffect(() => {
    if (!open) return;
    const first = box.current && box.current.querySelector("input");
    if (first) first.focus({ preventScroll: true });
    const away = (e) => { if (wrap.current && !wrap.current.contains(e.target)) statusOpen.value = false; };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [open]);
  const toggle = (w) => set({ st: f.st.includes(w) ? f.st.filter((x) => x !== w) : [...f.st, w] });
  const close = () => { statusOpen.value = false; const b = wrap.current && wrap.current.querySelector("button"); if (b) b.focus(); };
  return (
    <span class="fwrap" ref={wrap} onFocusOut={(e) => { if (open && e.relatedTarget && !wrap.current.contains(e.relatedTarget)) statusOpen.value = false; }}>
      <button type="button" class={`btn ucl-pill${f.st.length ? " on" : ""}`} id="ucl-status" aria-haspopup="true" aria-expanded={open ? "true" : "false"} onClick={() => { statusOpen.value = !open; }}>
        {f.st.length ? `Status: ${f.st.join(", ")}` : "Status: All"} <Icon name="chevdown" />
      </button>
      {open ? (
        <div class="fbox ucl-pop" role="group" aria-label="Status" ref={box} onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } }}>
          {STATUS_WORDS.map((w) => (
            <label key={w}><input type="checkbox" value={w} checked={f.st.includes(w)} onChange={() => toggle(w)} /><span class={`pill ${RAG[w]}`}>{w}</span></label>
          ))}
          <div class="fact ucl-pop-f"><button type="button" class="btn sm" data-clear onClick={() => set({ st: [] })}>Clear</button></div>
        </div>
      ) : null}
    </span>
  );
}

function UseCasesList() {
  const edit = mode.value === "edit", f = state.value, rows = all.value, shown = shownOf(rows, f), n = onCounts(rows, f);
  const stop = shown.some((r) => r.id === current.value) ? current.value : shown.length ? shown[0].id : "";
  const list = useRef(null);
  useEffect(() => {      // coming back from a use case: its row takes the focus
    const from = returning || cameBackFrom.value;       // Back (this page noted it) or the detail's crumb and Esc (the detail left it)
    returning = "";
    cameBackFrom.value = "";
    if (!from) return;
    const el = list.current && list.current.querySelector(`[data-uc="${CSS.escape(from)}"] .ucl-go`);
    if (el) el.focus({ preventScroll: true });
  }, []);
  const sortWord = (SORTS.find(([k]) => k === f.sort) || SORTS[0])[1];
  const clear = () => set({ st: [], on: "all", q: "" });
  return (
    <section class="frame ucl" id="usecases">
      <div class="head">
        <div>
          <h1>Use cases</h1>
          <p class="muted ucl-sub">Every use case of this project. The home dashboard shows the ones marked {ON_WORDS}.</p>
        </div>
      </div>
      {rows.length ? (
        <div class="wbar ucl-bar" role="group" aria-label="Narrow the list">
          <label class="ucl-search"><span class="sr">Search use cases</span><Icon name="search" /><input type="search" id="ucl-q" placeholder="Search use cases" autocomplete="off" value={f.q} onInput={(e) => set({ q: e.currentTarget.value })} /></label>
          <StatusFilter f={f} />
          <div class="seg" role="group" aria-label="On the dashboard or not">
            {[["all", "All"], ["on", ON_WORDS], ["off", OFF_WORDS]].map(([v, w]) => <button type="button" key={v} data-on={v} aria-pressed={f.on === v ? "true" : "false"} onClick={() => set({ on: v })}>{w} <em class="num">{n[v]}</em></button>)}
          </div>
          <Menu label={`Sort: ${sortWord}`} id="ucl-sort" menuLabel="Sort by" left items={SORTS.map(([k, w]) => ({ id: k, name: w, checked: f.sort === k }))} onPick={(k) => set({ sort: k })} />
          <span class="ucl-count num" id="ucl-count" role="status">{countWords(shown.length, rows)}</span>
        </div>
      ) : null}
      {!rows.length ? <p class="muted ucl-none" data-empty>No use cases yet.</p>
        : !shown.length ? (
          <div class="ucl-none" data-empty>
            <p class="muted">No use cases match {f.q.trim() ? `“${f.q.trim()}”` : "these filters"}{f.q.trim() && (f.st.length || f.on !== "all") ? " with these filters" : ""}.</p>
            {narrowed(f) ? <button type="button" class="btn" data-clear-all onClick={clear}>Clear the filters</button> : null}
          </div>
        ) : (
          <div class="ucl-box" ref={list} onKeyDown={keys}>
            <div class="ucl-row ucl-hd" aria-hidden="true"><span>Ref</span><span>Use case</span><span class="ucl-head">Where it stands</span><span>Status</span><span>Work items</span><span class="ucl-ms">Milestones</span><span>Home dashboard</span></div>
            <ul class="ucl-list" aria-label="Use cases">
              {shown.map((r) => <Row key={r.id} r={r} edit={edit} stop={r.id === stop} shown={shown} />)}
            </ul>
          </div>
        )}
    </section>
  );
}

export function UseCasesPage() {
  const key = uc.value, found = key && data.value ? ucFor(data.value, key) : null;
  return found ? <UseCaseDetail id={found.id} /> : <UseCasesList />;
}
