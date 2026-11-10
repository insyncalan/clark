// The Use cases page (the editor's page, in the main navigation beside Milestones): every use case of the project, selected for the
// dashboard or not, and one use case's own page when the address names one (#usecases&p=CODE&uc=1.2, drawn by UseCaseDetail).
// A row: its reference, its name (the button that opens it), where it stands, the status in words with a dot, the linked work items
// and how many are open, the linked milestones, and the eye (an icon alone; its words are the tooltip). The eye is the dashboard's own switch (use_cases.client_visible),
// changed through the one change path with its Undo toast, in View as in Edit (row 819).
// The list is ONE tab stop (the current row's name): Up and Down move between rows, Home and End to the first and last, Right to the
// row's eye and Left back to its name. The filter line (row 1085: the Work items box over this page's own fields, edit/UseCasesFilter.jsx),
// the Status choice (the line's status chip), the On the dashboard switch and the sort are remembered for each project in this browser
// (logic/useCasesList.js), never in the address, so they add no Back entry.
import { signal, computed } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { data, rows as allRows, project, uc, openUseCase, leaveUseCase } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { blink } from "../stores/motion.js";
import { readArchivedUseCase, getArchived } from "../api.js";
import { cameBackFrom } from "../stores/useCaseFocus.js";
import { listOf, ucFor, tidy, recalled, keep, shownOf, tabCounts, narrowed, countWords, rowSay, statusOf, withStatus, lineParts, groupsOf, groupLabel, STATUS_WORDS, ON_WORDS, OFF_WORDS, SORTS, TABS, GROUPS, RAG } from "../logic/useCasesList.js";
import { commitWords } from "../logic/commitment.js";
import { UseCaseDetail } from "../components/UseCaseDetail.jsx";
import { UCEDIT, openAdd } from "./UseCasesEdit.jsx";
import { UseCasesFilter } from "./UseCasesFilter.jsx";
import { plural } from "../workItems.js";
import { Menu, Fade } from "../components/Menu.jsx";
import { NewTile } from "../components/NewTile.jsx";
import { Icon } from "../components/Icon.jsx";
import { CommitChip } from "../components/CommitChip.jsx";

const kept = {};                                            // project -> state: a browser that refuses storage still narrows the list
const tick = signal(0);
const state = computed(() => { void tick.value; const code = project.value; return kept[code] || recalled(code); });
const all = computed(() => (data.value ? listOf(data.value, allRows.value) : []));
const current = signal("");                                   // the id of the row that is the list's one tab stop
const statusOpen = signal(false);
const archShown = signal(false);                            // row 830: Show archived is on (kept for the visit)
const shutGroups = signal(new Set());                       // row 1085: the groups shut for the visit ("group|key"), never remembered
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

function Row({ r, stop, shown }) {
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
      <span class="ucl-st"><span class={`pill ${RAG[r.status] || "n"}`} data-status>{r.status}</span><CommitChip u={r} /></span>
      <span class="ucl-wi num">{r.total ? <><b>{r.total}</b> linked<small>{r.open} open</small></> : "None linked"}</span>
      <span class="ucl-ms">{ms || <span class="muted">None</span>}</span>
      <button type="button" class="ucl-eye" tabIndex={-1} data-eye title={eyeWords} aria-label={`${r.ref || "Use case"} ${r.name}: ${eyeWords}. ${r.on ? "Take it off the dashboard" : "Put it on the dashboard"}`}
        onFocus={() => { current.value = r.id; }} onClick={(e) => { blink(e); setEye(r, shown); }}><Icon name={r.on ? "eye" : "eyeoff"} /></button>
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

// The Status choice reads and writes the line's status chip (row 1085), so the two never disagree.
function StatusFilter({ f, rows }) {
  const st = statusOf(f.line, rows), setSt = (next) => set({ line: withStatus(f.line, next, rows) });
  const box = useRef(null), wrap = useRef(null), open = statusOpen.value;
  useEffect(() => {
    if (!open) return;
    const first = box.current && box.current.querySelector("input");
    if (first) first.focus({ preventScroll: true });
    const away = (e) => { if (wrap.current && !wrap.current.contains(e.target)) statusOpen.value = false; };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [open]);
  const toggle = (w) => setSt(st.includes(w) ? st.filter((x) => x !== w) : [...st, w]);
  const close = () => { statusOpen.value = false; const b = wrap.current && wrap.current.querySelector("button"); if (b) b.focus(); };
  return (
    <span class="fwrap" ref={wrap} onFocusOut={(e) => { if (open && e.relatedTarget && !wrap.current.contains(e.relatedTarget)) statusOpen.value = false; }}>
      <button type="button" class={`btn ucl-pill${st.length ? " on" : ""}`} id="ucl-status" aria-haspopup="true" aria-expanded={open ? "true" : "false"} onClick={() => { statusOpen.value = !open; }}>
        {st.length ? `Status: ${st.join(", ")}` : "Status: All"} <Icon name="chevdown" />
      </button>
      {open ? (
        <Fade boxRef={box} class="fbox ucl-pop" role="group" aria-label="Status" onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } }}>
          {STATUS_WORDS.map((w) => (
            <label key={w}><input type="checkbox" value={w} checked={st.includes(w)} onChange={() => toggle(w)} /><span class={`pill ${RAG[w]}`}>{w}</span></label>
          ))}
          <div class="fact ucl-pop-f"><button type="button" class="btn sm" data-clear onClick={() => setSt([])}>Clear</button></div>
        </Fade>
      ) : null}
    </span>
  );
}

// Row 830: the archived use cases, read with the archived rows (the page's own data leaves them out), under the list: a footer with
// Show archived, and when on a box with each one's name (it opens read-only), a tag, its linked work items and Restore.
function ArchivedUseCases() {
  const code = project.value, d = data.value;
  const [got, setGot] = useState(null);
  useEffect(() => {
    let live = true;
    getArchived(code).then((r) => { if (live && r.ok) setGot({ code, list: (r.data.use_cases || []).filter((u) => u.archived) }); });
    return () => { live = false; };
  }, [code, d]);
  const list = got && got.code === code ? got.list : [];
  if (!list.length) return null;
  const on = archShown.value, n = list.length;
  const linked = (u) => ((d.actions || []).concat(d.raid || [], d.decisions || [])).filter((r) => r.use_case === u.id).length;
  return (
    <div data-archived-uc>
      {on ? (
        <div class="card arch-box ucl-arch">
          <h2 class="arch-h">Archived <span>{plural(n, "use case")}</span></h2>
          <ul class="arch-l plain">
            {list.map((u) => (
              <li class="arch" key={u.id} data-arch-uc={u.id}>
                <button type="button" class="link" onClick={() => openUseCase(u.id)}>{u.ref || "Use case"} · {u.title}</button>
                <span class="tag arch">Archived</span>
                <button type="button" class="btn sm" data-restore onClick={() => change({ kind: "use_cases", op: "restore", id: u.id, place: "cell" }, "Use case restored.")}>Restore</button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p class="ucx-foot">{on ? `Showing ${plural(n, "archived use case")}.` : `${plural(n, "archived use case")} ${n === 1 ? "is" : "are"} hidden.`} <button type="button" class="link" data-arch-toggle onClick={() => { archShown.value = !on; }}>{on ? "Hide archived" : "Show archived"}</button></p>
    </div>
  );
}

// The column names over the rows (hidden on a phone: each row names its own parts).
const Hd = () => <div class="ucl-row ucl-hd" aria-hidden="true"><span>Ref</span><span>Use case</span><span class="ucl-head">Where it stands</span><span>Status</span><span>Work items</span><span class="ucl-ms">Milestones</span><span></span></div>;

function UseCasesList() {
  const f = state.value, rows = all.value, kept_ = shownOf(rows, f), n = tabCounts(rows, f);
  // Row 1085: the rows in their groups (one plain group for Nothing); a shut group keeps its heading and its count, its rows are away for the visit.
  const groups = groupsOf(kept_, f.group, commitWords(data.value)).map((g) => ({ ...g, shut: f.group !== "nothing" && shutGroups.value.has(`${f.group}|${g.key}`) }));
  const shown = groups.flatMap((g) => (g.shut ? [] : g.rows));
  const toggleGroup = (g) => { const next = new Set(shutGroups.value), k = `${f.group}|${g.key}`; if (next.has(k)) next.delete(k); else next.add(k); shutGroups.value = next; };
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
  const clear = () => set({ line: "", tab: "all" });
  const parts = lineParts(f.line, rows), filtered = parts.chips.length > 0 || f.tab !== "all";     // the empty state: the plain words said back, and whether filters narrowed it too
  // Row 1085: the tabs row as Work items draws its saved views (the tabs with their counts over one rule), with Add use case (the growing +) at its
  // right end (the ruling keeps the + and leaves the Import and Export icons off this page); the filter line under it. The tabs' counts follow the line.
  const tools = (
    <span class="ucl-tools">
      {rows.length ? <Menu label="Group by" ariaLabel={`Group by: ${groupLabel(f.group)}`} id="ucl-group" btnCls="btn sm" menuLabel="Group by" left items={GROUPS.map(([k, w]) => ({ id: k, name: w, checked: f.group === k }))} onPick={(k) => set({ group: k })} /> : null}
      <NewTile word="Add use case" kind="use_case" id="ucAddPage" onAdd={openAdd} />
    </span>
  );
  return (
    <section class="frame ucl" id="usecases">
      <div class="head">
        <div>
          <h1>Use cases</h1>
          <p class="muted ucl-sub">Every use case of this project. The home dashboard shows the ones marked {ON_WORDS}.</p>
        </div>
        {rows.length ? null : <div class="hacts">{tools}</div>}
      </div>
      {rows.length ? (
        <div class="fviews ucl-views">
          <div class="fvrow">
            <div class="vtabs" role="group" aria-label="Narrow the list">
              {TABS.map(([id, name]) => (
                <button type="button" key={id} class="vtab" data-tab={id} aria-pressed={f.tab === id ? "true" : "false"} onClick={() => set({ tab: id })}><span>{name}</span><em class="num">{n[id]}</em></button>
              ))}
            </div>
            {tools}
          </div>
        </div>
      ) : null}
      {rows.length ? <UseCasesFilter f={f} rows={rows} now={() => state.value.line} apply={(text) => set({ line: text })} /> : null}
      {rows.length ? (
        <div class="wbar ucl-bar" role="group" aria-label="Narrow the list">
          <StatusFilter f={f} rows={rows} />
          <Menu label={`Sort: ${sortWord}`} id="ucl-sort" menuLabel="Sort by" left items={SORTS.map(([k, w]) => ({ id: k, name: w, checked: f.sort === k }))} onPick={(k) => set({ sort: k })} />
          <span class="ucl-count num" id="ucl-count" role="status">{countWords(kept_.length, rows)}</span>
        </div>
      ) : null}
      {!rows.length ? <p class="muted ucl-none" data-empty>No use cases yet.</p>
        : !kept_.length ? (
          <div class="ucl-none" data-empty>
            <p class="muted">No use cases match {parts.words ? `“${parts.words}”` : "these filters"}{parts.words && filtered ? " with these filters" : ""}.</p>
            {narrowed(f) ? <button type="button" class="btn" data-clear-all onClick={clear}>Clear the filters</button> : null}
          </div>
        ) : f.group === "nothing" ? (
          <div class="ucl-box" ref={list} onKeyDown={keys}>
            <Hd />
            <ul class="ucl-list" aria-label="Use cases">
              {shown.map((r) => <Row key={r.id} r={r} stop={r.id === stop} shown={shown} />)}
            </ul>
          </div>
        ) : (
          <div class="ucl-box" ref={list} onKeyDown={keys}>
            {groups.map((g) => (
              <div class="wgroup ucl-group" key={g.key} data-group={g.key}>
                <div class="ucl-grp">
                  <button type="button" class="grp-b" aria-expanded={g.shut ? "false" : "true"} onClick={() => toggleGroup(g)}>
                    <Icon name="chevdown" cls={g.shut ? "turn" : ""} /><span class="gl">{g.label}</span><span class="gc num">{plural(g.rows.length, "use case")}</span>
                  </button>
                </div>
                {g.shut ? null : (
                  <>
                    <Hd />
                    <ul class="ucl-list" aria-label={g.label}>
                      {g.rows.map((r) => <Row key={r.id} r={r} stop={r.id === stop} shown={shown} />)}
                    </ul>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      <ArchivedUseCases />
    </section>
  );
}

// An address that is not a live use case: an archived one opens its detail (read-only, with Restore); anything else opens the list.
function ArchivedAddress({ keyOf }) {
  const code = project.value;
  const [read, setRead] = useState({ key: "", id: "" });
  useEffect(() => {
    let stale = false;
    readArchivedUseCase(code, keyOf).then((r) => {
      if (stale) return;
      if (r.ok && r.row) setRead({ key: keyOf, id: r.row.id });
      else leaveUseCase();
    });
    return () => { stale = true; };
  }, [code, keyOf]);
  if (read.key !== keyOf) return <div class="ucd" data-ucd><p class="muted">Loading the use case.</p></div>;
  return <UseCaseDetail id={read.id} ed={UCEDIT} />;
}

export function UseCasesPage() {
  const key = uc.value, found = key && data.value ? ucFor(data.value, key) : null;
  const last = useRef("");                                  // the use case on show: Archive takes it out of the live rows, but its page stays
  if (!key) last.current = "";
  else if (found) last.current = found.id;
  if (found) return <UseCaseDetail id={found.id} ed={UCEDIT} />;
  if (key && data.value) return last.current ? <UseCaseDetail id={last.current} /> : <ArchivedAddress keyOf={key} />;
  return <UseCasesList />;
}
