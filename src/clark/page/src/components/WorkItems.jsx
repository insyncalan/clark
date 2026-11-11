// The Work items list (#36, read only; #64a filters and Add): one project's actions, risks, issues, assumptions, dependencies and
// decisions from GET /api/data, as tables in bordered group cards (#456): item (a letter badge for its kind, title, id), owner, due date in
// words, priority, status, and in the page clark serves the Client-visible eye. The list rules are in
// ../workItems.js, the filter rules in ../filters.js. A filter change redraws the list region and the switches' words only.
// This page has no View | Edit mode (row 824), so the Owner, Due, Priority and Status cells change in place (#80, #442)
// (tools.Cell, edit/cells/): each opens its own picker. A published file has no tools, so no pickers.
// A click on the row anywhere else opens the item's peek.
// The keyboard (#80): the table is one tab stop, the row last focused (the first until then). Up and Down move between rows (from a
// cell to the same cell of the next row), Home and End to the first and last row, Right and Left across the row's
// cells and back to the row. Enter on a row opens its peek; on a cell, Enter, Space or Alt+Down opens its picker.
// Selecting several (#195, on the page clark serves): a click selects the row and opens its peek, Cmd or Ctrl+click adds or removes it, Shift+click
// selects a range in the order drawn; Shift+Up and Shift+Down extend from the cursor row, Space
// adds or removes it, Cmd or Ctrl+A selects every row shown; each group heading has a tick box. The rules are in pick.js.
// Hand over (#199, edit/HandOver.jsx): while pick mode is on the table is drawn with a tick box on each open item, a click or Space on a
// row only ticks it, and none of the keys above, the cells' pickers or the peek is on. The ticks are stores/handover.js `ticks`.
import { signal } from "@preact/signals";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { cursor, stopOf as stopOfIds, moveTo } from "../listKeys.js";
import { data, rows as allRows, filterState, setFilterState, filterNote, openPeek, fromFile, filterCtx, query, setQuery, asAt } from "../stores/report.js";
import { workSelection as sel } from "../stores/selection.js";
import { selecting, ownClick, noTextRange, pickClick, pickOpen, pickKeys, drawnOrder, installSelectionRules } from "./pick.js";
import { SelectBar, GroupTick } from "./SelectBar.jsx";
import { itemRows } from "../stores/work.js";
import { handing, ticks } from "../stores/handover.js";
import { KIND_WORDS, kindLetter, sortRows, dueCell, pillOf, ownerOf, metaOf, isOpen, todayIso } from "../workItems.js";
import { applyFilters, chips, canClear, countText, clearAll, removeFilter, addPlan } from "../filters.js";
import { Switches, FilterBar } from "./WorkFilters.jsx";
import { lineApi } from "../stores/lineSlot.js";
import { ImportExport } from "./ImportExport.jsx";
import { NewTile } from "./NewTile.jsx";
import { Menu } from "./Menu.jsx";
import { isChanged, WORD } from "../stores/changed.js";
import { Icon } from "./Icon.jsx";
import { work, setWork, announce, contextFor } from "../stores/work.js";
import { GROUPS, groupLabel, boardGroup, columnsFor, cellOf, isCollapsed, toggleCollapsed } from "../logic/board.js";

// The Add button (gap list B-8): in clark, a pick makes the item at once and opens it, with "<ID> added" and Undo in the toast
// (tools.addItem, edit/addItem.js). The published file has no Add (#204); a page with no tools says, in words, that nothing was added.
const asked = signal("");
function adder(tools) {
  if (tools && typeof tools.addItem === "function" && !fromFile.value) {
    return (kind) => { asked.value = ""; tools.addItem(kind, work.value.view === "board" ? "board" : "menu"); };
  }
  return (kind) => { const k = kind || "item"; asked.value = `Nothing was added. This page is read only. To add ${/^[aeiou]/.test(k) ? "an" : "a"} ${k}, open the project in clark.`; };
}

function Owner({ name }) {
  const o = ownerOf(name);
  return o.initials
    ? <span class="who"><span class="av" aria-hidden="true">{o.initials}</span><span>{o.text}</span></span>
    : <span class="muted">{o.text}</span>;
}

const active = cursor;                          // the id of the row that is the table's one tab stop (listKeys.js)

// A cell the arrows reach: a picker's button (Edit) or the Client-visible eye's button (Edit). `field` names it for "the same cell of the next row".
const CELLS = "[data-cell], button.weye";
const fieldOf = (c) => (c ? (c.dataset.cell ? c.dataset.cell.slice(c.dataset.cell.lastIndexOf(":") + 1) : "client") : "");
const cellIn = (r, field) => (field === "client" ? r.querySelector("button.weye") : field ? r.querySelector(`[data-cell$=":${field}"]`) : null);

// The arrow keys inside the table. Only a key on a row or on a cell's own button: never one meant for an open picker.
function keys(e, row) {
  const tr = e.currentTarget, t = e.target;
  const cell = t !== tr && t.matches && t.matches(CELLS) ? t : null;
  if (t !== tr && !cell) return;
  if (handing()) {                                                                 // #199: Space only ticks; Enter opens nothing; the arrows still move
    if (e.key === " " && !cell && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); if (isOpen(row)) ticks.toggle(row.id); return; }
    if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.key === "Enter") return;
  } else {
    if (selecting() && pickKeys(e, row.id, (id) => focusRow(tr, id, cell), { space: !cell })) return;
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || (selecting() && e.shiftKey)) return;
    if (!cell && e.key === "Enter") { e.preventDefault(); openPeek(row.id, "item"); return; }   // Enter opens the peek; the arrows always walk the cells (this page has no mode)
  }
  const rows = Array.from(tr.closest("#work-list").querySelectorAll("tr[data-id]")), at = rows.indexOf(tr);   // across the groups (each its own card and table), never a group heading
  const cells = Array.from(tr.querySelectorAll(CELLS)), c = cells.indexOf(cell);
  const field = fieldOf(cell);
  const toRow = (j) => {
    const r = rows[Math.max(0, Math.min(rows.length - 1, j))];
    (cellIn(r, field) || r).focus();
  };
  const vert = e.key === "ArrowDown" || e.key === "ArrowUp" || (!cell && (e.key === "Home" || e.key === "End"));
  if (vert) toRow(moveTo(e.key, at, rows.length, ["ArrowUp", "ArrowDown", "Home", "End"]));
  else if (e.key === "ArrowRight") { if (cells[c + 1]) cells[c + 1].focus(); }
  else if (e.key === "ArrowLeft" && cell) (c > 0 ? cells[c - 1] : tr).focus();
  else return;
  e.preventDefault();
}

// Shift+Up or Shift+Down moved the cursor: the keyboard goes to that row (to the same cell when it was on one).
function focusRow(tr, id, cell) {
  const r = tr.closest("#work-list").querySelector(`tr[data-id="${CSS.escape(id)}"]`);
  if (!r) return;
  (cellIn(r, fieldOf(cell)) || r).focus();
}

// #970: a row deleted in Edit keeps its place for the fade (a copy with no id and no role, inert, hidden from a screen reader), then leaves the DOM.
function GhostRow({ row, today, Eye, group, onMotionEnd }) {
  const due = dueCell(row, today), pill = pillOf(row, today), o = ownerOf(row.owner);
  return (
    <tr class="leaving" role="presentation" aria-hidden="true" inert onAnimationEnd={(e) => { if (e.target === e.currentTarget && e.animationName === "m-out") onMotionEnd(row.id); }}>
      <td class="c-item"><div class="tcell"><span class={`kb k-${row.kind}`} aria-hidden="true">{kindLetter(row.kind)}</span><span class="tx"><span class="t">{row.title}</span><span class="meta">{metaOf(row, group)}</span></span></div></td>
      <td class="c-owner">{o.text}</td>
      <td class="c-due"><span class="num">{due.date}</span>{due.words ? <span class="due-l">{due.words}</span> : null}</td>
      <td class="c-prio">{row.priority || ""}</td>
      <td class="c-status"><span class={`pill ${pill.class}`}>{pill.text}</span></td>
      {Eye ? <td class="c-eye" /> : null}
    </tr>
  );
}

const stillMotion = () => document.documentElement.dataset.motion === "reduce" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

// #970: which rows are new since the last draw (they rise in) and which were deleted (they fade in place). Only a row added to or removed from
// the project's items counts: a filter, a sort, Group by or a search never animates, nor does the first draw, a project change, or a still-motion setting.
// `lay` is the drawn layout, [{ key, rows }]. Returns { motion(id), ghostsFor(key), done(id) }. Edit only: a published file has none.
function useRowMotion(lay) {
  const memo = useRef(null), fresh = useRef(new Set()), ghosts = useRef(new Map()), [, redraw] = useState(0);
  const ids = new Set(allRows.value.map((r) => r.id)), prev = memo.current;
  const drawn = new Map();
  lay.forEach((c) => c.rows.forEach((r, i) => drawn.set(r.id, { row: r, key: c.key, at: i })));
  if (prev && !fromFile.value && !stillMotion() && Array.from(prev.ids).some((id) => ids.has(id))) {
    drawn.forEach((_, id) => { if (!prev.ids.has(id)) fresh.current.add(id); });
    prev.drawn.forEach((d, id) => { if (!ids.has(id) && !ghosts.current.has(id)) ghosts.current.set(id, d); });
  }
  ghosts.current.forEach((_, id) => { if (ids.has(id)) ghosts.current.delete(id); });      // undone: the row is back
  memo.current = { ids, drawn };
  const done = (id) => { fresh.current.delete(id); if (ghosts.current.delete(id)) redraw((n) => n + 1); };
  const n = ghosts.current.size;
  useEffect(() => { if (!n) return undefined; const t = setTimeout(() => { ghosts.current.clear(); redraw((k) => k + 1); }, 400); return () => clearTimeout(t); }, [n]);
  return {
    done,
    motion: (id) => (fresh.current.has(id) ? "enter" : undefined),
    ghostsFor: (key) => Array.from(ghosts.current.values()).filter((d) => d.key === key).sort((a, b) => a.at - b.at),
  };
}

function Row({ row, today, Cell, Eye, stop, pos, size, group, motion, onMotionEnd }) {
  if (motion === "leave") return <GhostRow row={row} today={today} Eye={Eye} group={group} onMotionEnd={onMotionEnd} />;
  const due = dueCell(row, today), pill = pillOf(row, today);
  const cell = (field, said, content) => (Cell ? <Cell row={row} field={field} said={said}>{content}</Cell> : content);
  const hand = handing(), can = isOpen(row), ticked = hand && ticks.ids.value.includes(row.id);
  const on = selecting() && !hand, picked = on && sel.ids.value.includes(row.id);
  const click = (e) => {
    if (!ownClick(e.target, e.currentTarget)) return;
    if (hand) { if (can) ticks.toggle(row.id); }
    else if (on) pickClick(e, row.id);
    else if (!String(window.getSelection()).length) openPeek(row.id, "item");
  };
  const dbl = (e) => { if (on && ownClick(e.target, e.currentTarget)) pickOpen(row.id); };
  return (
    <tr data-id={row.id} data-kind={row.kind} data-changed={isChanged(row.id) ? "1" : undefined} class={`${can ? "" : "done"}${motion === "enter" ? " entering" : ""}${picked || ticked ? " picked" : ""}${isChanged(row.id) ? " changed" : ""}${Eye ? " has-eye" : ""}`.trim()} tabIndex={stop ? 0 : -1} aria-posinset={pos} aria-setsize={size}
      aria-label={hand ? (can ? `Tick ${row.id}` : `${row.id}, closed, not offered`) : on ? `Select or open ${row.id}` : `Open ${row.id}`}
      aria-selected={on ? (picked ? "true" : "false") : hand && can ? (ticked ? "true" : "false") : undefined}
      onFocusIn={() => { active.value = row.id; if (on) sel.moveCursor(row.id); }} onKeyDown={(e) => keys(e, row)} onMouseDown={on ? noTextRange : undefined} onClick={click} onDblClick={dbl} onAnimationEnd={motion === "enter" ? (e) => { if (e.target === e.currentTarget && e.animationName === "m-rise") onMotionEnd(row.id); } : undefined}>
      {hand ? (
        <td class="c-pick">
          {can ? <label class="rtick-hit" onClick={(e) => e.stopPropagation()}>
            <input type="checkbox" class="rtick" data-tick={row.id} checked={ticked} aria-label={`Hand over ${row.id}`} onChange={() => ticks.toggle(row.id)} />
          </label> : null}
        </td>
      ) : null}
      <td class="c-item">
        <div class="tcell">
          <span class={`kb k-${row.kind}`} role="img" aria-label={KIND_WORDS[row.kind] || row.kind} title={KIND_WORDS[row.kind] || row.kind}>{kindLetter(row.kind)}</span>
          <span class="tx">
            <span class="t">{row.title}</span>
            <span class="meta">{metaOf(row, group)}{isChanged(row.id) ? <span class="tag chg">{WORD}</span> : null}</span>
          </span>
        </div>
      </td>
      <td class="c-owner">{cell("owner", ownerOf(row.owner).text === "—" ? "none" : ownerOf(row.owner).text, <Owner name={row.owner} />)}</td>
      <td class="c-due">{cell("due", due.date === "—" ? "none" : due.date, <><span class="num">{due.date}</span>{due.words ? <span class={`due-l${due.tone ? " " + due.tone : ""}`}>{due.words}</span> : null}</>)}</td>
      <td class="c-prio">{cell("priority", row.priority || "none", row.priority || <span class="muted">{"—"}</span>)}</td>
      <td class="c-status">{cell("status", pill.text, <span class={`pill ${pill.class}`}>{pill.text}</span>)}</td>
      {Eye ? <td class="c-eye"><Eye row={row} /></td> : null}
    </tr>
  );
}

// The table, in groups (Group by): each group is its own bordered card (#456, prototype `.group`) with a heading bar (the name and the
// count that opens and shuts the group) and its own table: the column names, then its rows. "Nothing" is one card with no heading bar.
// The columns are Item (a letter badge, the title, then the id and links), Owner, Due, Priority, Status and, in the page clark serves,
// the Client-visible eye. A published file has no eye column, and its code holds none of the eye's words: the client is shown nothing about what is internal.
// A group with no rows is not drawn here (the board draws every column). The table's one tab stop (#80) is the row last focused
// while it is drawn, else the first row drawn.
const COLS = ["c-item", "c-owner", "c-due", "c-prio", "c-status"];
function Heads({ eye, hand }) {
  return (
    <>
      {hand ? <th class="c-pick"><span class="sr">Hand over</span></th> : null}
      <th class="c-item">Item</th><th class="c-owner">Owner</th><th class="c-due">Due</th><th class="c-prio">Priority</th><th class="c-status">Status</th>
      {eye ? <th class="c-eye"><span class="sr">{eye.heading}</span></th> : null}
    </>
  );
}
function Cols({ eye, hand }) { return <colgroup>{(hand ? ["c-pick"] : []).concat(COLS, eye ? ["c-eye"] : []).map((c) => <col key={c} class={c} />)}</colgroup>; }

const opened = (key) => (e) => { if (justOpened === key) justOpened = ""; e.currentTarget.classList.remove("opening"); };
let justOpened = "";                               // row 880: the group whose rows were just drawn by opening it (they glide in once)
function Table({ rows, today, type, Cell, Eye }) {
  const hand = handing(), st = work.value, g = st.group, on = selecting(), grid = on ? { role: "grid", "aria-multiselectable": "true", "aria-label": hand ? "Work items to hand over" : "Work items" } : {};
  const n = COLS.length + (Eye ? 1 : 0) + (hand ? 1 : 0);
  const stopOf = (drawn) => stopOfIds(drawn.map((r) => r.id));
  let order = [];                                  // the rows drawn, in order: each one's place for a screen reader ("3 of 12")
  let mo = null;
  const row = (r, stop) => <Row key={r.id} row={r} today={today} Cell={Cell} Eye={Eye} stop={r.id === stop} pos={order.indexOf(r.id) + 1} size={order.length} group={g} motion={mo.motion(r.id)} onMotionEnd={mo.done} />;
  const rowsOf = (key, list, stop) => {                                             // the rows, with a deleted row's fading copy back in its old place
    const out = list.map((r) => row(r, stop));
    mo.ghostsFor(key).forEach((d) => out.splice(Math.min(d.at, out.length), 0, <Row key={"gone-" + d.row.id} row={d.row} today={today} Eye={Eye} group={g} motion="leave" onMotionEnd={mo.done} />));
    return out;
  };
  if (g === "nothing") {
    const flat = sortRows(rows, today), stop = stopOf(flat);
    order = flat.map((r) => r.id);
    mo = useRowMotion([{ key: "", rows: flat }]);
    return <div class="wgroup"><table class="items" {...grid}><Cols eye={Eye} hand={hand} /><thead><tr><Heads eye={Eye} hand={hand} /></tr></thead><tbody>{rowsOf("", flat, stop)}</tbody></table></div>;
  }
  const ctx = contextFor(today, type);
  const groups = columnsFor(g, rows, ctx).map((c) => ({ ...c, rows: sortRows(rows.filter((r) => cellOf(g, r, ctx) === c.key), today) })).filter((c) => c.rows.length > 0)
    .map((c) => ({ ...c, shut: isCollapsed(st, g, c.key) }));
  const shown = groups.flatMap((c) => (c.shut ? [] : c.rows)), stop = stopOf(shown);
  order = shown.map((r) => r.id);
  mo = useRowMotion(groups.map((c) => ({ key: c.key, rows: c.shut ? [] : c.rows })));
  return (
    <>
      {groups.map((c) => {
        const shut = c.shut;
        return (
          <div class="wgroup" key={c.key}>
            <table class="items grouped" {...grid}>
              <Cols eye={Eye} hand={hand} />
              <thead data-group={c.key} class={justOpened === c.key && !shut && !fromFile.value ? "opening" : undefined} onAnimationEnd={opened(c.key)}>
                <tr class="grp"><th colspan={n} scope="colgroup">
                  {hand ? <GroupTick sel={ticks} ids={c.rows.filter((r) => isOpen(r)).map((r) => r.id)} label={c.label} shut={shut} />
                    : on ? <GroupTick ids={c.rows.map((r) => r.id)} label={c.label} shut={shut} /> : null}
                  <button type="button" class="grp-b" aria-expanded={shut ? "false" : "true"} onClick={() => { justOpened = shut && !fromFile.value ? c.key : ""; setWork(toggleCollapsed(work.value, g, c.key)); }}>
                    <Icon name="chevdown" cls={shut ? "turn" : ""} /><span class="gl">{c.label}</span><span class="gc num">{c.rows.length} {c.rows.length === 1 ? "item" : "items"}</span>
                  </button>
                </th></tr>
                {shut ? null : <tr class="colh"><Heads eye={Eye} hand={hand} /></tr>}
              </thead>
              <tbody data-group={c.key} class={justOpened === c.key && !shut && !fromFile.value ? "opening" : undefined} onAnimationEnd={opened(c.key)}>
                {shut ? null : rowsOf(c.key, c.rows, stop)}
              </tbody>
            </table>
          </div>
        );
      })}
    </>
  );
}

// The published file's Group by (the app's is in the filter line's View menu, #287): a menu button reading "Group by: Status".
function GroupBy({ board }) {
  const g = work.value.group, shown = board ? boardGroup(g) : g;
  return (
    <Menu label={`Group by: ${groupLabel(shown)}`} ariaLabel={`Group by: ${groupLabel(shown)}`} id="group-by" btnCls="btn gb" menuLabel="Group by" left
      items={GROUPS.filter((x) => !board || x.id !== "nothing").map((x) => ({ id: x.id, name: x.label }))}
      onPick={(id) => { const lane = work.value.lane; setWork({ group: id, lane: lane === id ? null : lane }); announce.value = `Grouped by ${groupLabel(id)}.`; }} />
  );
}

// The published file's search box (#69): it filters as the client types and is never re-created by a click, so nothing moves.
function SearchBox() {
  return (
    <label class="search"><span class="sr">Search work items</span>
      <input id="q" type="search" placeholder="Search work items" autocomplete="off" value={query.value} onInput={(e) => setQuery(e.currentTarget.value)} />
    </label>
  );
}

// The published file's list (#69): the older filter bar's chips, search, as-at day. The filter line is the app's only (#153).
// The part a filter change redraws: the count, the chips with Clear all, and the table or the board.
function PublishedList({ Board, Cell, Eye, Bulk }) {
  const st = filterState.value, today = fromFile.value && asAt.value ? asAt.value : todayIso();
  const filtered = applyFilters(itemRows.value, st, today);
  const cs = chips(st);
  const words = query.value.trim() !== "", canClearAll = canClear(st) || words;
  const clear = () => { setQuery(""); setFilterState(clearAll(filterState.value)); };    // a published file keeps the type and Open / Closed / All
  const board = !!Board && work.value.view === "board";
  const matching = filtered.map((r) => r.id);
  // After each draw: a row no longer drawn (filtered out, its group collapsed) leaves the selection, unless "all matching" is on.
  useLayoutEffect(() => { if (selecting()) sel.sync(drawnOrder(), matching); });
  return (
    <div id="work-list">
      {selecting() ? <SelectBar sel={sel} matching={matching} actions={Bulk ? <Bulk.Actions /> : null} /> : null}
      {Bulk ? <Bulk.Layer /> : null}
      <div class="factive pub">
        <span id="work-count" class="num" key={countText(filtered.length, st.mode)}>{countText(filtered.length, st.mode)}</span>
        {cs.map((c) => (
          <span class="fchip" key={c.field} data-chip={c.field}>{c.text}
            <button type="button" data-fx={c.field} aria-label={`Remove the ${c.name} filter`} onClick={() => setFilterState(removeFilter(filterState.value, c.field))}>{"×"}</button>
          </span>
        ))}
        {words ? <span class="fchip" data-chip="search">{`Search: ${query.value.trim()}`}
          <button type="button" data-fx="search" aria-label="Remove the search" onClick={() => setQuery("")}>{"×"}</button>
        </span> : null}
        {canClearAll ? <button type="button" class="link" id="clearAll" onClick={clear}>Clear all</button> : null}
      </div>
      {filtered.length === 0
        ? <div class="empty"><p class="muted">No items match these filters.</p>{canClearAll ? <button type="button" class="btn" id="clearAll2" onClick={clear}>Clear all</button> : null}</div>
        : board ? <Board rows={filtered} today={today} type={st.type} /> : <Table rows={filtered} today={today} type={st.type} Cell={Cell} Eye={Eye} />}
    </div>
  );
}

// The part a filter change redraws: the count, the chips with Clear all, and the table or the board.
function List({ Board, Cell, Eye, Bulk, HandOver, L }) {
  const today = todayIso(), v = L.view(itemRows.value, filterCtx());
  const st = v.state, filtered = v.rows, clear = v.clear, can = v.can;
  const hand = handing() && !!HandOver, board = !!Board && work.value.view === "board" && !hand;      // #199: Hand over is drawn as the table
  const matching = filtered.map((r) => r.id);
  // After each draw: a row no longer drawn (filtered out, its group collapsed) leaves the selection, unless "all matching" is on.
  useLayoutEffect(() => { if (selecting() && !hand) sel.sync(drawnOrder(), matching); });
  return (
    <div id="work-list">
      {hand ? <HandOver.Bar rows={filtered} /> : null}
      {selecting() && !hand ? <SelectBar sel={sel} matching={matching} actions={Bulk ? <Bulk.Actions /> : null} /> : null}
      {Bulk ? <Bulk.Layer /> : null}
      {/* Row 805: the count is not drawn as a line; it stays for a screen reader and for the tests that read it. */}
      <span id="work-count" class="sr num" key={countText(filtered.length, st.mode)}>{countText(filtered.length, st.mode)}</span>
      {filtered.length === 0
        ? <div class="empty"><p class="muted">{v.empty.none}</p>{can ? <button type="button" class="link" id="clearFilter" onClick={clear}>{v.empty.clear}</button> : null}{v.empty.hint ? <p class="muted" id="empty-hint">{v.empty.hint}</p> : null}</div>
        : board ? <Board rows={filtered} today={today} type={st.type} /> : <Table rows={filtered} today={today} type={st.type} Cell={hand ? null : Cell} Eye={Eye} />}
    </div>
  );
}

export function WorkItems({ tools }) {
  useEffect(() => { if (selecting()) installSelectionRules(); if (tools && tools.Bulk) tools.Bulk.install(); if (tools && tools.HandOver) tools.HandOver.install(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  const L = fromFile.value ? null : lineApi.current, FilterLine = L && L.FilterLine;
  const d = data.value, plan = addPlan(L ? L.toState(allRows.value, filterCtx()).type : filterState.value.type), Board = tools && tools.Board;
  const Cell = tools && tools.Cell && !fromFile.value ? tools.Cell : null;
  const Eye = tools && tools.Eye && !fromFile.value ? tools.Eye : null;      // the Client-visible column: the page clark serves, never a published file
  const board = !!Board && work.value.view === "board";
  // Coming back to Work items: the project's line is the one kept in this session (the address holds the older form of it).
  useEffect(() => { if (L) L.restore(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  const Arch = tools && tools.ArchivedItems && !fromFile.value && L && L.wantsArchived(allRows.value, filterCtx()) ? tools.ArchivedItems : null;   // item 1067: is:archived in the line; Edit parts only
  return (
    <section class={`frame work${fromFile.value ? " pub" : ""}`} id="work">
      <p class="crumbs">{d.project.name}</p>
      <div class="head">
        <div>
          <h1>Work items</h1>
        </div>
        {tools ? (
          <div class="hacts">
            {!(FilterLine && allRows.value.length) ? <ImportExport tools={tools} /> : null}   {/* row 1084: on the filter line when there is one; with no line (no work items yet) they stay here so an import can start the list */}
            {tools.HandOver ? <tools.HandOver.Button /> : null}   {/* #199: with the Owner filter on */}
            <NewTile word={plan.word} kind={plan.kind} items={plan.menu} onAdd={adder(tools)} />   {/* a published file is read only: no Add (#204) */}
          </div>
        ) : null}
      </div>
      <p class="muted note" role="status" id="work-note">{filterNote.value || asked.value}</p>
      <p class="sr" role="status" aria-live="polite" id="work-live">{announce.value}</p>
      {selecting() ? <p class="sr" role="status" aria-live="polite" id="sel-live">{sel.live.value}</p> : null}
      {allRows.value.length === 0
        ? <p class="muted">{tools ? `This project has no work items yet. Use ${plan.word} to add the first.` : "This report has no work items."}</p>
        : <>
            {!L
              ? <>
                  <Switches><GroupBy board={board} /><SearchBox /></Switches>
                  <FilterBar />
                  <PublishedList Board={Board} Cell={Cell} Eye={Eye} Bulk={tools && tools.Bulk} />
                </>
              : <>
                  <Switches L={L} />   {/* item 287: Layout, Group by and the swimlanes are in the filter line's one View menu */}
                  <FilterLine board={!!Board} tools={tools} />   {/* row 1084: Import and Export are icons on this line (item 454, row 824); a published file has neither */}
                  {Arch ? <Arch narrow={(r) => L.apply(r, filterCtx())} /> : <List Board={Board} Cell={Cell} Eye={Eye} Bulk={tools && tools.Bulk} HandOver={tools && tools.HandOver} L={L} />}
                </>}
          </>}
    </section>
  );
}
