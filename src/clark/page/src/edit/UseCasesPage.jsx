// The Use cases page (the editor's page, in the main navigation beside Milestones): every use case of the project, selected for the
// dashboard or not, and one use case's own page when the address names one (#usecases&p=CODE&uc=1.2, drawn by UseCaseDetail).
// A row: its reference, its name (the button that opens it), where it stands, the status in words with a dot, the linked work items
// and how many are open, the linked milestones, and the eye (an icon alone; its words are the tooltip). The eye is the dashboard's own switch (use_cases.client_visible),
// changed through the one change path with its Undo toast, in View as in Edit (row 819).
// The list is ONE tab stop (the current row's name): Up and Down move between rows, Home and End to the first and last, Right to the
// row's eye and Left back to its name. Row 1085: the page follows the Work items page: four saved views as tabs with counts (item 1203: read from logic/filterLine.js viewsGet with page "usecases"; the starting four are All use cases, On the
// dashboard, Committed, At risk) over one rule, Group by and the + at the row's end, the filter line under it (the Work items box over this
// page's own fields, edit/UseCasesFilter.jsx), the sort in a menu beside Group by (item 1149: the rows are the dashboard summary's, no column names). The tab, the line, the group and the sort are remembered for
// each project in this browser (logic/useCasesList.js), never in the address, so they add no Back entry.
import { StepsBadge } from "../components/StepsBadge.jsx";
import { signal, computed } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { data, rows as allRows, project, uc, openUseCase, leaveUseCase } from "../stores/report.js";
import { change, say, sayLocalUndo } from "../stores/changes.js";
import { blink } from "../stores/motion.js";
import { RecordContextMenu } from "./RecordContextMenu.jsx";
import { readArchivedUseCase, getArchived } from "../api.js";
import { cameBackFrom } from "../stores/useCaseFocus.js";
import { listOf, ucFor, tidy, recalled, keep, narrowed, countWords, rowSay, groupsOf, groupLabel, refBox, ON_WORDS, OFF_WORDS, SORTS, GROUPS, RAG } from "../logic/useCasesList.js";
import { commitWords } from "../logic/commitment.js";
import { UseCaseDetail } from "../components/UseCaseDetail.jsx";
import { UCEDIT, openAdd } from "./UseCasesEdit.jsx";
import { UseCasesFilter } from "./UseCasesFilter.jsx";
import { shownOf, tabCounts, lineParts } from "./useCasesLine.js";
import { viewsGet, viewsPut, visibleViews, addView, nextViewName, renameView, duplicateView, deleteView, insertView, reorderViews, MAX_NAME } from "../logic/filterLine.js";
import { local } from "../stores/line.js";
import { plural } from "../workItems.js";
import { Menu } from "../components/Menu.jsx";
import { NewTile } from "../components/NewTile.jsx";
import { Icon } from "../components/Icon.jsx";
import { groupIcon, sortIcon } from "../menuIcons.js";
import { useColumns } from "./ColumnsMenu.jsx";
import { narrowHeader as narrow } from "./narrowHeader.js";
import { ownerOf } from "../workItems.js";
import { CommitChip } from "../components/CommitChip.jsx";
import { classicTheme } from "../components/Contents.jsx";
import { AskAbout } from "./AskAbout.jsx";

const kept = {};                                              // project -> state: a browser that refuses storage still narrows the list
const tick = signal(0);
const state = computed(() => { void tick.value; const code = project.value; return kept[code] || recalled(code); });
const all = computed(() => (data.value ? listOf(data.value, allRows.value) : []));
const current = signal("");                                   // the id of the row that is the list's one tab stop
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

// Row 1325: a row is a table row as the Work items rows are: the use case (its name, then a grey line with the reference and the commitment), where it stands,
// the status, the owner, the next steps with a progress bar, the milestone, the optional columns, and the eye. A use case the client does not see is `off`.
// With the Commitment column drawn (not at 900 and narrower, where it is not) the grey line no longer repeats the commitment.
const COLS = { item: "Use case", where: "Where it stands", status: "Status", owner: "Owner", steps: "Next steps", ms: "Milestone", cm: "Commitment", rel: "Release", dash: "On the dashboard" };
const closedPct = (r) => (r.total ? Math.round(((r.total - r.open) / r.total) * 100) : 0);

function ClassicRow({ r, stop, shown, cols }) {
  const open = () => { returning = r.id; openUseCase(r.id); };
  const eyeWords = r.on ? ON_WORDS : OFF_WORDS;
  const own = ownerOf(r.u.owner), cmCol = cols.includes("cm") && !narrow.value, ref = refBox(r.u.ref);
  const cell = {
    item: <td class="c-item" data-col="item">
      <span class="t"><button type="button" class="ucl-go uctitle" tabIndex={stop ? 0 : -1} aria-label={rowSay(r)} title={`Open ${r.name}`} onFocus={() => { current.value = r.id; }} onClick={open}>{r.name}</button></span>
      {ref || (r.commitment && !cmCol) ? <span class="meta2 num">{ref ? <span class="ucl-ref" data-ref>{ref}</span> : null}{r.commitment && !cmCol ? <span class="cm">{ref ? " \u00b7 " : ""}{r.commitment}</span> : null}</span> : null}
    </td>,
    where: <td class="c-where" data-col="where"><span class={`where ucl-head uchead${r.headline ? "" : " none"}`} title={r.headline}>{r.headline || "No headline yet"}</span></td>,
    status: <td class="c-status ucl-st" data-col="status"><span class={`pill ${RAG[r.status] || "n"}`} data-status>{r.status}</span></td>,
    owner: <td class="c-owner" data-col="owner">{own.initials ? <span class="own"><span class="av" aria-hidden="true" title={own.text}>{own.initials}</span><span class="on">{own.text}</span></span> : own.text ? <span class="muted">{own.text}</span> : <span class="muted">{"\u2014"}</span>}</td>,
    steps: <td class="c-steps" data-col="steps"><span class={`stp ucl-steps ucsteps num${r.open ? " some" : ""}`} data-steps><StepsBadge n={r.open} /></span>
      <span class="prg" role="img" aria-label={`${r.total - r.open} of ${plural(r.total, "work item")} closed`}><i style={{ width: `${closedPct(r)}%` }}></i></span></td>,
    ms: <td class="c-ms" data-col="ms">{r.ms.length ? <span class="mslab" title={r.ms.map((m) => m.name).join(", ")}>{r.ms[0].name}{r.ms.length > 1 ? ` +${r.ms.length - 1}` : ""}</span> : <span class="muted">{"\u2014"}</span>}</td>,
    cm: <td class="c-cm" data-col="cm">{r.commitment || <span class="muted">{"\u2014"}</span>}</td>,
    rel: <td class="c-rel num" data-col="rel">{String(r.u.release || "").trim() || <span class="muted">{"\u2014"}</span>}</td>,
    dash: <td class="c-dash" data-col="dash">{r.on ? "Shown" : "Not shown"}</td>,
  };
  return (
    <tr class={`ucr${r.on ? "" : " off"}`} data-uc={r.id}
      onClick={(e) => { if (e.target.closest("button, a, input") || String(getSelection()).trim()) return; open(); }}>
      {cols.map((id) => cell[id])}
      <td class="c-eye"><button type="button" class="ucl-eye weye" tabIndex={-1} data-eye aria-pressed={r.on ? "true" : "false"} title={eyeWords} aria-label={`${r.ref || "Use case"} ${r.name}: ${eyeWords}. ${r.on ? "Take it off the dashboard" : "Put it on the dashboard"}`}
        onFocus={() => { current.value = r.id; }} onClick={(e) => { blink(e); setEye(r, shown); }}><Icon name={r.on ? "eye" : "eyeoff"} /></button><AskAbout kind="use case" id={r.id} name={`${r.ref || r.id} ${r.name}`.trim()} /></td>
    </tr>
  );
}

// The column header row (one, over the rows) and the widths; the last cell holds the Columns button (edit/ColumnsMenu.jsx, the Work items one).
function Heads({ cols, cm }) {
  return (
    <tr class="colh" {...cm.rowProps}>
      {cols.map((id) => <th key={id} scope="col" class={`c-${id}`} data-col={id}>{COLS[id]}</th>)}
      <th class="c-eye"><span class="sr">Dashboard</span>{cm.button()}</th>
    </tr>
  );
}
const Cols = ({ cols }) => <colgroup>{cols.map((id) => <col key={id} class={`c-${id}`} />)}<col class="c-eye" /></colgroup>;

// Cards (no Theme layer): the list exactly as it is on main. Classic (the Theme layer is on) draws the table.
function CardsRow({ r, stop, shown }) {
  const open = () => { returning = r.id; openUseCase(r.id); };
  const eyeWords = r.on ? ON_WORDS : OFF_WORDS;
  // Item 1149: the dashboard summary's row (reference box, title, where it stands, status word with the commitment, the next steps) and the eye; the counts sit behind the click.
  return (
    <li class={`ucl-row${r.on ? "" : " off"}`} data-uc={r.id}
      onClick={(e) => { if (e.target.closest("button, a, input") || String(getSelection()).trim()) return; open(); }}>
      {r.u.ref ? <span class="ucref ucl-ref num" data-ref>{refBox(r.u.ref)}</span> : <span class="ucl-ref"></span>}
      <button type="button" class="ucl-go uctitle" tabIndex={stop ? 0 : -1} aria-label={rowSay(r)} title={`Open ${r.name}`} onFocus={() => { current.value = r.id; }} onClick={open}>{r.name}</button>
      <span class="ucl-head uchead" title={r.headline}>{r.headline || "No headline yet"}</span>
      <span class="ucl-st ucstc"><span class={`pill ${RAG[r.status] || "n"}`} data-status>{r.status}</span><CommitChip u={r} /></span>
      <span class={`ucl-steps ucsteps num${r.open ? " some" : ""}`} data-steps><StepsBadge n={r.open} /></span>
      <button type="button" class="ucl-eye" tabIndex={-1} data-eye title={eyeWords} aria-label={`${r.ref || "Use case"} ${r.name}: ${eyeWords}. ${r.on ? "Take it off the dashboard" : "Put it on the dashboard"}`}
        onFocus={() => { current.value = r.id; }} onClick={(e) => { blink(e); setEye(r, shown); }}><Icon name={r.on ? "eye" : "eyeoff"} /></button>
    </li>
  );
}

// Row 1203: the column names over the rows (the rows' own columns; the eye has none). Not read out: each row says its own parts.
function ColumnHeads() {
  return (
    <div class="ucl-cols" aria-hidden="true">
      <span class="ucl-c1">Use case</span><span>Where it stands</span><span>Status</span><span>Next steps</span><span></span>
    </div>
  );
}

function Row(p) { return p.cols ? <ClassicRow {...p} /> : <CardsRow {...p} />; }

// The list's keys, taken only when focus is on a row's name or eye, so the search box and the filters keep their own keys.
function keys(e) {
  const t = e.target, k = e.key;
  if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.isComposing || e.defaultPrevented || !t.closest) return;
  const row = t.closest(".ucl-row, tr.ucr");
  if (!row || !t.matches(".ucl-go, .ucl-eye")) return;
  const eye = t.classList.contains("ucl-eye"), rows = [...e.currentTarget.querySelectorAll(".ucl-list .ucl-row, tbody tr.ucr")], at = rows.indexOf(row);
  const focus = (el) => { if (el) { e.preventDefault(); el.focus(); } };
  if (k === "ArrowRight") return focus(eye ? null : row.querySelector(".ucl-eye"));      // the name, then the eye (Archive and Delete are in the row's right-click menu, the menu key or Shift+F10)
  if (k === "ArrowLeft") return focus(eye ? row.querySelector(".ucl-go") : null);
  const to = { ArrowUp: at - 1, ArrowDown: at + 1, Home: 0, End: rows.length - 1 }[k];
  if (to === undefined) return;
  e.preventDefault();
  const r = rows[Math.max(0, Math.min(rows.length - 1, to))];
  (eye ? r.querySelector(".ucl-eye") || r.querySelector(".ucl-go") : r.querySelector(".ucl-go")).focus();
}

// Row 830: the archived use cases, read with the archived rows (the page's own data leaves them out), under the list: a footer with
// Show archived, and when on a box with each one's name (it opens read-only), a tag, its linked work items and Restore.
function restore(u) {      // the Restore button leaves with its row: the footer's toggle (or the restored row's name) takes the focus
  change({ kind: "use_cases", op: "restore", id: u.id, place: "cell" }, "Use case restored.").then(() => setTimeout(() => {
    const el = document.querySelector("#usecases [data-arch-toggle]") || document.querySelector(`#usecases [data-uc="${CSS.escape(u.id)}"] .ucl-go`);
    if (el) el.focus({ preventScroll: true });
  }, 120));
}

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
                <button type="button" class="btn sm" data-restore aria-label={`Restore ${u.ref || "Use case"} · ${u.title}`} onClick={() => restore(u)}>Restore</button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p class="ucx-foot">{on ? `Showing ${plural(n, "archived use case")}.` : `${plural(n, "archived use case")} ${n === 1 ? "is" : "are"} hidden.`} <button type="button" class="link" data-arch-toggle onClick={() => { archShown.value = !on; }}>{on ? "Hide archived" : "Show archived"}</button></p>
    </div>
  );
}

function UseCasesList() {
  const f = state.value, rows = all.value, views = visibleViews(viewsGet(local(), project.value, "usecases")), kept_ = shownOf(rows, f, views), n = tabCounts(rows, f, views);
  // Row 1085: the rows in their groups (one plain group for Nothing); a shut group keeps its heading and its count, its rows are away for the visit.
  const groups = groupsOf(kept_, f.group, commitWords(data.value)).map((g) => ({ ...g, shut: f.group !== "nothing" && shutGroups.value.has(`${f.group}|${g.key}`) }));
  const shown = groups.flatMap((g) => (g.shut ? [] : g.rows));
  const toggleGroup = (g) => { const next = new Set(shutGroups.value), k = `${f.group}|${g.key}`; if (next.has(k)) next.delete(k); else next.add(k); shutGroups.value = next; };
  const stop = shown.some((r) => r.id === current.value) ? current.value : shown.length ? shown[0].id : "";
  const list = useRef(null), cm = useColumns("uc", true);
  const code = project.value, nameBox = useRef(null);
  const [form, setForm] = useState(null);      // row 1203: the Rename view box ({name, error}), or null
  const [moving, setMoving] = useState("");      // row 1203: the id of the tab Move view is moving with the arrow keys
  const [told, setTold] = useState("");      // row 1203: what the tabs say aloud
  const active = views.find((v) => v.id === f.tab) || null;
  const saveViews = (next) => { viewsPut(local(), code, next, "usecases"); tick.value++; };
  const focusTab = (id) => setTimeout(() => { const el = document.querySelector(`#usecases .vtab[data-tab="${CSS.escape(id)}"]`); if (el) el.focus({ preventScroll: true }); }, 0);
  const closeForm = () => { setForm(null); setTimeout(() => { const el = document.getElementById("ucl-viewTabMenu"); if (el) el.focus(); }, 0); };
  const submitName = (e) => {
    e.preventDefault();
    const r = renameView(views, active.id, form.name);
    if (!r.ok) { setForm({ ...form, error: r.message }); return; }
    saveViews(r.views);
    closeForm();
  };
  useEffect(() => {      // the name box takes the focus once the menu has given the focus back to its button
    if (!form) return undefined;
    const t = setTimeout(() => { if (nameBox.current) nameBox.current.focus(); }, 40);
    return () => clearTimeout(t);
  }, [!!form]);
  const tabAct = (id) => {
    if (id === "new") {
      const r = addView(views, nextViewName(views), f.line.trim());
      if (!r.ok) { say("problem", r.message); return; }
      saveViews(r.views);
      set({ tab: r.id, line: "" });
      setTold(`Saved as ${r.views.find((v) => v.id === r.id).name}. Use Rename view to change the name.`);
    } else if (!active) return;
    else if (id === "rename") setForm({ name: active.name, error: "" });
    else if (id === "move") { setMoving(active.id); setTold(`Moving ${active.name}. Press Left or Right arrow to move it, Enter to finish.`); focusTab(active.id); }
    else if (id === "duplicate") {
      const r = duplicateView(views, active.id);
      if (!r.ok) { say("problem", r.message); return; }
      saveViews(r.views);
      set({ tab: r.id });
      setTold(`Duplicated as ${r.views.find((v) => v.id === r.id).name}.`);
      focusTab(r.id);
    } else if (id === "delete") {      // no question first: the message at the foot of the page has Undo, which puts the view back where it was
      const at = views.findIndex((v) => v.id === active.id), gone = active, r = deleteView(views, gone.id);
      if (!r.ok) { say("problem", r.message); return; }
      saveViews(r.views);
      set({ tab: (r.views[at] || r.views[at - 1] || { id: "all" }).id });
      sayLocalUndo("done", `View deleted: ${gone.name}`, () => {
        const b = insertView(visibleViews(viewsGet(local(), code, "usecases")), gone, at);
        if (!b.ok) { say("problem", b.message); return; }      // a name taken since, say, is told, never silent
        saveViews(b.views);
        set({ tab: gone.id });
      }, code);
      setTimeout(() => { const el = document.getElementById("ucl-viewNew"); if (el) el.focus(); }, 0);
    }
  };
  const tabKeys = (e, id) => {      // Move view: Left and Right put the tab one place over, Enter or Esc ends
    if (moving !== id) return;
    if (e.key === "Enter" || e.key === "Escape") { e.preventDefault(); setMoving(""); return; }
    const to = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0;
    if (!to) return;
    e.preventDefault();
    const ids = views.map((v) => v.id), at = ids.indexOf(id), j = at + to;
    if (at < 0 || j < 0 || j >= ids.length) return;
    [ids[at], ids[j]] = [ids[j], ids[at]];
    const r = reorderViews(views, ids);
    if (r.ok) { saveViews(r.views); setTold(`Moved to place ${j + 1} of ${ids.length}.`); focusTab(id); }
  };
  const tabItems = [{ id: "rename", name: "Rename view", icon: "pencil" }, ...(views.length > 1 ? [{ id: "move", name: "Move view", icon: "move" }] : []),
    { id: "duplicate", name: "Duplicate view", icon: "copy" }, { id: "delete", name: "Delete view", icon: "trash", danger: true }];
  const [menu, setMenu] = useState(null);      // row 1203: the right-click menu on a row (the record, the point, the element that takes the focus back)
  const rowMenu = (e) => {      // a right click, the menu key or Shift+F10 on a row
    const el = e.target.closest && e.target.closest(".ucl-row[data-uc], .ucr[data-uc]");
    if (!el) return;
    const rec = rows.find((x) => x.id === el.dataset.uc);
    if (!rec) return;
    e.preventDefault();
    const go = el.querySelector(".ucl-go"), key = e.clientX === 0 && e.clientY === 0, at = (key ? (document.activeElement && el.contains(document.activeElement) ? document.activeElement : go) : null);
    const box = at ? at.getBoundingClientRect() : null;
    setMenu({ row: rec.u, x: box ? box.left : e.clientX, y: box ? box.bottom : e.clientY, from: go });
  };
  useEffect(() => {      // coming back from a use case: its row takes the focus
    const from = returning || cameBackFrom.value;       // Back (this page noted it) or the detail's crumb and Esc (the detail left it)
    returning = "";
    cameBackFrom.value = "";
    if (!from) return;
    const el = list.current && list.current.querySelector(`[data-uc="${CSS.escape(from)}"] .ucl-go`);
    if (el) el.focus({ preventScroll: true });
  }, []);
  const clear = () => {      // the button leaves with the empty state: the search box takes the focus
    set({ line: "", tab: "all" });
    setTimeout(() => { const q = document.getElementById("ucl-q"); if (q) q.focus({ preventScroll: true }); }, 60);
  };
  const parts = lineParts(f.line, rows), filtered = parts.chips.length > 0 || f.tab !== "all";     // the empty state: the plain words said back, and whether filters narrowed it too
  // Row 1085: the tabs row as Work items draws its saved views (the tabs with their counts over one rule), with Group by and Add use case
  // (the growing +) at its right end (Import and Export are in Settings, on the Data card); the filter line under it. The tabs' counts follow the line.
  const classic = classicTheme();
  const tools = classic ? <span class="ucl-tools"><NewTile word="Add use case" kind="use_case" id="ucAddPage" onAdd={openAdd} /></span> : (
    <span class="ucl-tools">
      {rows.length ? <Menu label="Group by" ariaLabel={`Group by: ${groupLabel(f.group)}`} id="ucl-group" btnCls="btn sm" menuLabel="Group by" items={GROUPS.map(([k, w]) => ({ id: k, name: w, icon: groupIcon(k), checked: f.group === k }))} onPick={(k) => set({ group: k })} /> : null}
      {rows.length ? <Menu label="Sort by" ariaLabel={`Sort by: ${(SORTS.find(([k]) => k === f.sort) || SORTS[0])[1]}`} id="ucl-sort" btnCls="btn sm" menuLabel="Sort by" items={SORTS.map(([k, w]) => ({ id: k, name: w, icon: sortIcon(k), checked: f.sort === k }))} onPick={(k) => set({ sort: k })} /> : null}
      <NewTile word="Add use case" kind="use_case" id="ucAddPage" onAdd={openAdd} />
    </span>
  );
  // Row 1325: the layout pair, the layout pair is icon buttons, Group by and Sort by are labelled buttons (row 1316 follow-up), at the right end of the filter line. There is no board for use cases: its button is drawn
  // (the approved mock-up has it) and cannot be pressed.
  const tail = classic && rows.length ? (
    <span class="vicons">
      <div class="seg lsw" role="group" aria-label="Layout">
        <button type="button" data-lay="table" aria-label="List" title="List" aria-pressed="true"><Icon name="table" /></button>
        <button type="button" data-lay="board" aria-label="Board" title="Board" aria-pressed="false" aria-disabled="true" onClick={() => say("problem", "There is no board for use cases yet.")}><Icon name="board" /></button>
      </div>
      <Menu label="Group by" ariaLabel={`Group by: ${groupLabel(f.group)}`} chevron={false} id="ucl-group" btnCls="btn sm" menuLabel="Group by" items={GROUPS.map(([k, w]) => ({ id: k, name: w, icon: groupIcon(k), checked: f.group === k }))} onPick={(k) => set({ group: k })} />
      <Menu label="Sort by" ariaLabel={`Sort by: ${(SORTS.find(([k]) => k === f.sort) || SORTS[0])[1]}`} chevron={false} id="ucl-sort" btnCls="btn sm" menuLabel="Sort by" items={SORTS.map(([k, w]) => ({ id: k, name: w, icon: sortIcon(k), checked: f.sort === k }))} onPick={(k) => set({ sort: k })} />
    </span>
  ) : null;
  const cols = cm.shown;
  const table = (heads, body, cls = "", label = "Use cases") => <table aria-label={label} class={`items ucl-table${cls}${cols.includes("cm") ? " cmcol" : ""}`}><Cols cols={cols} />{heads ? <thead><Heads cols={cols} cm={cm} /></thead> : null}{body}</table>;
  return (
    <section class="frame ucl" id="usecases">
      <p class="crumbs">{data.value.project.name}</p>
      <div class="head">
        <div>
          <h1>Use cases</h1>
        </div>
        {rows.length ? null : <div class="hacts">{tools}</div>}
      </div>
      {rows.length ? (
        <div class="fviews ucl-views">
          <div class="fvrow">
            <div class="vtabs" role="group" aria-label="Narrow the list">
              {views.map(({ id, name }) => (
                <span class="vt" key={id}>
                  <button type="button" class="vtab" data-tab={id} aria-pressed={f.tab === id ? "true" : "false"} data-moving={moving === id ? "" : undefined} onClick={() => set({ tab: id })} onKeyDown={(e) => tabKeys(e, id)} onBlur={() => { if (moving === id) setMoving(""); }}><span>{name}</span><em class="num">{n[id]}</em></button>
                  {f.tab === id ? <Menu label="" ariaLabel={`Options for ${name}`} id="ucl-viewTabMenu" btnCls="vtabmenu" menuId="ucl-viewTabMenuList" fixed="start" menuLabel={`Options for ${name}`} items={tabItems} onPick={tabAct} /> : null}
                </span>
              ))}
            </div>
            <button type="button" class="vnew" id="ucl-viewNew" onClick={() => tabAct("new")}>{"+ New view"}</button>
            {tools}
          </div>
          {form ? (
            <form class="vform" onSubmit={submitName} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); closeForm(); } }}>
              <label for="vname">New name for this view</label>
              <input id="vname" type="text" value={form.name} maxLength={MAX_NAME} ref={nameBox} onInput={(e) => setForm({ ...form, name: e.target.value, error: "" })} />
              <button type="submit" class="btn sm" id="vsave">Save</button>
              <button type="button" class="btn sm" onClick={closeForm}>Cancel</button>
              <span class="vmsg" role="status">{form.error}</span>
            </form>
          ) : null}
          <p class="sr-only" role="status">{told}</p>
        </div>
      ) : null}
      {rows.length ? <UseCasesFilter f={f} rows={rows} now={() => state.value.line} apply={(text) => set({ line: text })} tail={tail} /> : null}
      {!rows.length ? <p class="muted ucl-none" data-empty>No use cases yet.</p>
        : !kept_.length ? (
          <div class="ucl-none" data-empty>
            <p class="muted">No use cases match {parts.words ? `“${parts.words}”` : "these filters"}{parts.words && filtered ? " with these filters" : ""}.</p>
            {narrowed(f) ? <button type="button" class="btn" data-clear-all onClick={clear}>Clear the filters</button> : null}
          </div>
        ) : classic ? (
          f.group === "nothing" ? (
          <div class="ucl-wrap" ref={list} onKeyDown={keys} onContextMenu={rowMenu}>
            <div class="wgroup">
              {table(true, <tbody>{shown.map((r) => <Row key={r.id} r={r} stop={r.id === stop} shown={shown} cols={cols} />)}</tbody>)}
              {cm.button("key")}{cm.menu}
            </div>
          </div>
        ) : (
          <div class="ucl-wrap" ref={list} onKeyDown={keys} onContextMenu={rowMenu}>
            {/* Row 1325: the grouping is as it was (a heading above each group's rows); the column header is drawn once on top. Row 1324 draws the heading as Option A of its mock-up. */}
            <div class="wgroup">{table(true, null, " hdr")}{cm.button("key")}{cm.menu}</div>
            {groups.map((g) => (
              <div class="wgroup ucl-group" key={g.key} data-group={g.key}>
                <div class="ucl-grp">
                  <button type="button" class="grp-b" aria-expanded={g.shut ? "false" : "true"} onClick={() => toggleGroup(g)}>
                    <Icon name="chevdown" cls={g.shut ? "turn" : ""} /><span class="gl">{g.label}</span><span class="gc num">{plural(g.rows.length, "use case")}</span>
                  </button>
                </div>
                {g.shut ? null : table(false, <tbody>{g.rows.map((r) => <Row key={r.id} r={r} stop={r.id === stop} shown={shown} cols={cols} />)}</tbody>, "", g.label)}
              </div>
            ))}
          </div>
          )
        ) : f.group === "nothing" ? (
          <div class="ucl-box" ref={list} onKeyDown={keys} onContextMenu={rowMenu}>
            <ColumnHeads />
            <ul class="ucl-list" aria-label="Use cases">
              {shown.map((r) => <Row key={r.id} r={r} stop={r.id === stop} shown={shown} />)}
            </ul>
          </div>
        ) : (
          <div class="ucl-box" ref={list} onKeyDown={keys} onContextMenu={rowMenu}>
            <ColumnHeads />
            {groups.map((g) => (
              <div class="wgroup ucl-group" key={g.key} data-group={g.key}>
                <div class="ucl-grp">
                  <button type="button" class="grp-b" aria-expanded={g.shut ? "false" : "true"} onClick={() => toggleGroup(g)}>
                    <Icon name="chevdown" cls={g.shut ? "turn" : ""} /><span class="gl">{g.label}</span><span class="gc num">{plural(g.rows.length, "use case")}</span>
                  </button>
                </div>
                {g.shut ? null : (
                  <>
                    <ul class="ucl-list" aria-label={g.label}>
                      {g.rows.map((r) => <Row key={r.id} r={r} stop={r.id === stop} shown={shown} />)}
                    </ul>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      {menu ? <RecordContextMenu at={menu} kind="use_cases" onClose={() => setMenu(null)} /> : null}
      {rows.length ? <p class="ucl-count num" id="ucl-count" role="status">{countWords(kept_.length, rows)}</p> : null}
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
