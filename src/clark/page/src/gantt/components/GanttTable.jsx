// The Gantt plan as a table that behaves like an Excel sheet (#926). Props in, callbacks out: it fetches nothing and saves nothing.
//   lines          every line of the plan, in order (the shape is described in ../logic/grid.js)
//   edit           true in Edit; false is View: read only, no row numbers, the hidden columns not drawn
//   hidden         the keys of the columns hidden from the client (default: logic/grid.js DEFAULT_HIDDEN)
//   filter         'all' | 'phases' | 'phasesMilestones' | 'ticked' (the page's "Show")
//   today          YYYY-MM-DD, the day Status is worked out against
//   onChange(lines, change)   the whole new list after any step; change is { type, ids } (type: edit, paste, fill, clear, add, delete, undo, redo)
//   onAdd({ id, afterId, type })   a line was added        onDelete(ids)   lines were deleted
//   onHiddenChange(keys)      a column's eye was pressed (Edit only)
//   onUndo()                  when given, Cmd or Ctrl+Z and the Undo button are this (the page's own history), not a list kept here
// Row numbers are the lines' own places in the plan, so they stay the same when the filter hides lines. Every value is a text node.
import { useEffect, useRef, useState } from "preact/hooks";
import { Fade } from "../../components/Menu.jsx";
import { actionIcon } from "../../menuIcons.js";
import { Icon } from "../../components/Icon.jsx";
import {
  COLUMNS, DEFAULT_HIDDEN, WORDS, hideable, addLine, cellCount, clampSel, clampZoom, clashes, clearCells, deleteLines, emptyHistory, endSel, enterNext, fillDown,
  fillRight, fillTo, fitWidth, getValue, homeSel, inRange, makeSel, moveSel, parseTSV, pasteCells, rangeOf, record, redo, selectAll, selectColumn, selectRow,
  setField, tabNext, toTSV, undo, visibleColumns, visibleRows,
} from "../logic/grid.js";

const ROW_HEAD = 44;
const PAGE_ROWS = 10;

// The icon of a row-menu line comes from its words and its danger flag, here at the drawing, so the lines that build the menus stay as they were.
const rowAction = (it) => (it[2] ? "delete" : /^Add /.test(it[0]) ? "add" : it[0] === "Clear cells" ? "clear" : "copy");

export function GanttTable({ lines, edit = false, hidden = DEFAULT_HIDDEN, filter = "all", today = "", onChange, onAdd, onDelete, onHiddenChange, onUndo, addBelowWord = "" }) {
  const cols = visibleColumns(hidden, edit);
  const rows = visibleRows(lines, { edit, filter });
  const clash = clashes(lines);
  const [sel, setSel] = useState(makeSel(0, 0));
  const [editing, setEditing] = useState(null);                       // { r, c, init }
  const [zoom, setZoom] = useState(1);
  const [widths, setWidths] = useState({});
  const [menu, setMenu] = useState(null);                              // { x, y, items }
  const [msg, setMsg] = useState(null);                                // { text, bad, undo, n }
  const box = useRef(null);
  const field = useRef(null);
  const live = useRef(null);                                           // the edit that is open; set to null when it is closed, so a blur after it does nothing
  const hist = useRef(emptyHistory());
  const drag = useRef(null);
  const fillRef = useRef(null);
  const count = useRef(0);
  const leave = useRef(false);
  const menuBox = useRef(null);
  const now = useRef({});

  const s = clampSel(sel, rows.length, cols.length);
  const range = rangeOf(s);
  const width = (c) => Math.round((widths[c.key] ?? c.width) * zoom);
  const left0 = edit ? Math.round(ROW_HEAD * zoom) : 0;
  const lefts = [left0, left0 + (cols[0] ? width(cols[0]) : 0)];
  const tableWidth = left0 + cols.reduce((a, c) => a + width(c), 0);
  const lineAt = (r) => lines[rows[r]];

  const say = (text, { bad = false, undo: u = false } = {}) => { if (onUndo && !bad) return; count.current += 1; setMsg({ text, bad, undo: u, n: count.current }); };      // with the page's own history, its toast says what was done (and may say it was refused)
  useEffect(() => {
    if (!msg) return undefined;
    const t = setTimeout(() => setMsg((m) => (m && m.n === msg.n ? null : m)), 9000);
    return () => clearTimeout(t);
  }, [msg]);
  useEffect(() => {
    const up = () => now.current.up && now.current.up();
    const away = (e) => { if (now.current.menuOpen && !e.target.closest(".gt-menu")) setMenu(null); };
    document.addEventListener("mouseup", up);
    document.addEventListener("pointerdown", away, true);
    return () => { document.removeEventListener("mouseup", up); document.removeEventListener("pointerdown", away, true); };
  }, []);

  const focusBox = () => { if (box.current) box.current.focus({ preventScroll: true }); };
  const locked = () => { if (!edit) { say(WORDS.viewOnly); return true; } return false; };

  // One step is made: remember how it was, tell the page. `text` is the toast.
  const step = (next, change, text, bad = false) => {
    hist.current = record(hist.current, lines);
    if (onChange) onChange(next, change);
    if (text) say(text, { bad, undo: true });
  };
  const goUndo = () => {
    if (onUndo) { onUndo(); return; }      // the page keeps the history (the server's): Cmd+Z in the table is the app's Undo
    const got = undo(hist.current, lines);
    if (got.lines === null) return;
    hist.current = got.history;
    if (onChange) onChange(got.lines, { type: "undo", ids: [] });
  };
  const goRedo = () => {
    if (onUndo) return;
    const got = redo(hist.current, lines);
    if (got.lines === null) return;
    hist.current = got.history;
    if (onChange) onChange(got.lines, { type: "redo", ids: [] });
  };

  const select = (next) => {
    setSel(clampSel(next, rows.length, cols.length));
    const td = box.current && box.current.querySelector(`td[data-r="${Math.max(0, Math.min(rows.length - 1, next.fr))}"][data-c="${Math.max(0, Math.min(cols.length - 1, next.fc))}"]`);
    if (td && td.scrollIntoView) td.scrollIntoView({ block: "nearest", inline: "nearest" });
  };

  // ── editing one cell ──
  const startEdit = (r, c, init) => {
    if (locked()) return;
    const col = cols[c];
    if (!col || !lineAt(r)) return;
    if (col.type === "ro") { say(WORDS.workedOut(col.label)); return; }
    const e = { r, c, init };
    live.current = e;
    setEditing(e);
  };
  const cancelEdit = () => { live.current = null; setEditing(null); focusBox(); };
  // Close the open edit with what was typed. Gives the new list (the same one when nothing changed or the value was refused).
  const closeEdit = () => {
    const e = live.current;
    if (!e) return { lines, ok: false };
    live.current = null;
    const el = field.current;
    const typed = el ? el.value : "";
    const col = cols[e.c];
    const i = rows[e.r];
    setEditing(null);
    if (!col || i === undefined || typed === getValue(lines[i], col.key, today)) return { lines, ok: true };
    const got = setField(lines, i, col.key, typed);
    if (got.error) { say(got.error, { bad: true }); return { lines, ok: false }; }
    return { lines: got.lines, ok: true, change: { type: "edit", ids: [lines[i].id] }, text: WORDS.changed(col.label, i + 1) };
  };
  const finishEdit = (dr, dc, blur = false) => {
    const e = live.current;
    if (!e) return;
    const done = closeEdit();
    if (!blur) focusBox();
    const here = makeSel(e.r, e.c);
    if (!done.ok) { setSel(here); return; }
    if (blur) { if (done.change) step(done.lines, done.change, done.text); return; }
    if (dc > 0 || dc < 0) {
      const t = tabNext(here, dc < 0, rows.length, cols.length);
      if (t.addLine) { addBelow(rows.length - 1, "t", done); return; }
      if (done.change) step(done.lines, done.change, done.text);
      select(t.sel);
      return;
    }
    if (done.change) step(done.lines, done.change, done.text);
    select(enterNext(here, dr < 0, rows.length));
  };

  // ── lines ──
  // A line below row `r` (a row as drawn). `base` is a result of closeEdit when an edit is being finished in the same step.
  const addBelow = (r, type, base) => {
    if (locked()) return;
    const from = base && base.lines ? base.lines : lines;
    const ref = rows.length ? lines[rows[Math.max(0, Math.min(r, rows.length - 1))]] : null;
    const made = addLine(from, ref ? ref.id : "", type);
    hist.current = record(hist.current, lines);
    if (onChange) onChange(made.lines, { type: "add", ids: [made.id] });
    if (onAdd) onAdd({ id: made.id, afterId: ref ? ref.id : "", type });
    say(WORDS.added, { undo: true });
    const at = Math.min(rows.length, r + 1);
    setSel(makeSel(at, Math.min(1, cols.length - 1)));
    live.current = { r: at, c: Math.min(1, cols.length - 1) };
    setEditing(live.current);
  };
  const removeRows = (r0, r1) => {
    if (locked()) return;
    const ids = rows.slice(r0, r1 + 1).map((i) => lines[i].id);
    if (!ids.length) return;
    step(deleteLines(lines, ids), { type: "delete", ids }, WORDS.deleted(ids));
    if (onDelete) onDelete(ids);
    setSel(makeSel(r0, s.fc));
  };
  const clearSelected = () => {
    if (locked()) return;
    const got = clearCells(lines, rows, cols, s);
    if (got.ok) step(got.lines, { type: "clear", ids: [] }, WORDS.cleared(got.ok, got.bad));
    else if (got.bad) say(WORDS.needValue, { bad: true });
  };
  const pasteText = (text) => {
    if (locked()) return;
    const got = pasteCells(lines, rows, cols, s, parseTSV(text));
    if (got.ok) {
      step(got.lines, { type: "paste", ids: got.added }, WORDS.pasted(got.ok, got.bad, got.first));
      if (onAdd) got.added.forEach((id) => onAdd({ id, afterId: "", type: "t" }));
    } else say(got.bad ? WORDS.pasteNone(got.first) : WORDS.nothingToPaste, { bad: !!got.bad });
  };
  const doFill = (kind) => {
    if (locked()) return;
    if (kind === "down" && range.r1 === range.r0) return;
    if (kind === "right" && range.c1 === range.c0) return;
    const got = kind === "down" ? fillDown(lines, rows, cols, s, today) : fillRight(lines, rows, cols, s, today);
    if (got.ok) step(got.lines, { type: "fill", ids: [] }, kind === "down" ? WORDS.filledDown(got.ok) : WORDS.filledRight(got.ok));
    else if (got.bad) say(got.first, { bad: true });
  };
  now.current.up = () => {
    drag.current = null;
    const f = fillRef.current;
    fillRef.current = null;
    if (!f || f.to === null || f.to <= range.r1) return;
    if (locked()) return;
    const got = fillTo(lines, rows, cols, s, f.to, today);
    if (got.ok) step(got.lines, { type: "fill", ids: [] }, WORDS.filled(got.ok));
    setSel(makeSel(range.r0, range.c0, f.to, range.c1));
  };
  now.current.menuOpen = !!menu;

  const showMenu = (x, y, items) => setMenu({ x, y, items });
  const copyNow = () => { setMenu(null); focusBox(); document.execCommand("copy"); };
  const rowMenu = (x, y, r) => {
    const g = r >= range.r0 && r <= range.r1 ? range : { r0: r, r1: r };
    const n = g.r1 - g.r0 + 1;
    if (!edit) { showMenu(x, y, [["Copy", copyNow]]); return; }
    showMenu(x, y, [["Add a task below", () => addBelow(g.r1, "t")], ["Add a phase below", () => addBelow(g.r1, "p")], ["Add a milestone below", () => addBelow(g.r1, "m")], "-",
      ["Copy", copyNow], ["Clear cells", () => { setMenu(null); focusBox(); clearSelected(); }], "-",
      [n === 1 ? "Delete this line" : `Delete ${n} lines`, () => { setMenu(null); removeRows(g.r0, g.r1); }, true]]);
  };

  // ── the keyboard ──
  const onKeyDown = (e) => {
    if (editing || e.target !== e.currentTarget) return;
    const k = e.key;
    if (k === "Tab" && leave.current) return;                    // after Esc, Tab leaves the table (the keyboard is never trapped)
    leave.current = k === "Escape"; const mod = e.metaKey || e.ctrlKey; const K = k.toLowerCase();
    const nav = (dr, dc) => { e.preventDefault(); select(moveSel(s, dr, dc, { extend: e.shiftKey, edge: mod, rows: rows.length, cols: cols.length })); };
    if (k === "Escape") { if (menu) setMenu(null); return; }
    if (k === "ArrowDown") nav(1, 0); else if (k === "ArrowUp") nav(-1, 0); else if (k === "ArrowRight") nav(0, 1); else if (k === "ArrowLeft") nav(0, -1);
    else if (k === "Tab") {
      e.preventDefault();
      const t = tabNext(s, e.shiftKey, rows.length, cols.length);
      if (t.addLine) addBelow(rows.length - 1, "t"); else select(t.sel);
    } else if (k === "Enter") { e.preventDefault(); select(enterNext(s, e.shiftKey, rows.length)); }
    else if (k === "F2") { e.preventDefault(); startEdit(s.fr, s.fc); }
    else if (k === "Delete" || k === "Backspace") { e.preventDefault(); clearSelected(); }
    else if (k === "Home") { e.preventDefault(); select(homeSel(s, mod)); }
    else if (k === "End") { e.preventDefault(); select(endSel(s, mod, rows.length, cols.length)); }
    else if (k === "PageDown") nav(PAGE_ROWS, 0); else if (k === "PageUp") nav(-PAGE_ROWS, 0);
    else if (mod && K === "a") { e.preventDefault(); select(selectAll(rows.length, cols.length)); }
    else if (mod && K === "d") { e.preventDefault(); doFill("down"); } else if (mod && K === "r") { e.preventDefault(); doFill("right"); }
    else if (mod && K === "z") { e.preventDefault(); if (e.shiftKey) goRedo(); else goUndo(); } else if (mod && K === "y") { e.preventDefault(); goRedo(); }
    else if (!mod && !e.altKey && k.length === 1) { e.preventDefault(); startEdit(s.fr, s.fc, k); }
  };
  const onInputKey = (e) => {
    const k = e.key;
    e.stopPropagation();
    if (k === "Enter") { e.preventDefault(); finishEdit(e.shiftKey ? -1 : 1, 0); }
    else if (k === "Tab") { e.preventDefault(); finishEdit(0, e.shiftKey ? -1 : 1); }
    else if (k === "Escape") { e.preventDefault(); cancelEdit(); }
  };

  // ── the mouse ──
  const hit = (e) => ({ td: e.target.closest("td[data-c]"), th: e.target.closest("th") });
  const onMouseDown = (e) => {
    if (e.button === 2 || e.target.closest(".gt-eye, .gt-rb, .gt-cr")) return;
    if (e.target.classList.contains("gt-fh")) { e.preventDefault(); fillRef.current = { to: null }; return; }
    if (editing && !e.target.closest("td.gt-ed")) { const done = closeEdit(); if (done.change) step(done.lines, done.change, done.text); }
    const { td, th } = hit(e);
    const nr = rows.length; const nc = cols.length;
    if (td) {
      if (td.classList.contains("gt-ed")) return;
      e.preventDefault(); focusBox();
      const r = +td.dataset.r; const c = +td.dataset.c;
      select(e.shiftKey ? makeSel(s.ar, s.ac, r, c) : makeSel(r, c));
      drag.current = "cell";
    } else if (th && th.dataset.row !== undefined) {
      e.preventDefault(); focusBox(); select(selectRow(s, +th.dataset.row, nc, e.shiftKey)); drag.current = "row";
    } else if (th && th.dataset.all) {
      e.preventDefault(); focusBox(); select(selectAll(nr, nc));
    } else if (th && th.dataset.col !== undefined) {
      e.preventDefault(); focusBox(); select(selectColumn(s, +th.dataset.col, nr, e.shiftKey)); drag.current = "col";
    }
  };
  const onMouseOver = (e) => {
    const { td, th } = hit(e);
    if (fillRef.current) { if (td) fillRef.current.to = +td.dataset.r; return; }
    if (!drag.current) return;
    if (drag.current === "cell" && td) select(makeSel(s.ar, s.ac, +td.dataset.r, +td.dataset.c));
    else if (drag.current === "row" && th && th.dataset.row !== undefined) select(makeSel(s.ar, 0, +th.dataset.row, cols.length - 1));
    else if (drag.current === "col" && th && th.dataset.col !== undefined) select(makeSel(0, s.ac, rows.length - 1, +th.dataset.col));
  };
  const autoFit = (c) => {
    const col = cols[c];
    if (!col) return;
    setWidths((w) => ({ ...w, [col.key]: fitWidth(col.label, rows.map((i) => getValue(lines[i], col.key, today)), edit) }));
  };
  const onDblClick = (e) => {
    const cr = e.target.closest(".gt-cr");
    if (cr) { autoFit(+cr.dataset.c); return; }
    const td = e.target.closest("td[data-c]");
    if (td && !td.classList.contains("gt-ed")) startEdit(+td.dataset.r, +td.dataset.c);
  };
  const onContextMenu = (e) => {
    const td = e.target.closest("td[data-c]"); const th = e.target.closest("th[data-row]");
    if (!td && !th) return;
    e.preventDefault();
    const row = td ? +td.dataset.r : +th.dataset.row;
    if (row < range.r0 || row > range.r1) setSel(td ? makeSel(row, +td.dataset.c) : makeSel(row, 0, row, cols.length - 1));
    rowMenu(e.clientX, e.clientY, row);
  };
  const startResize = (e, c) => {
    e.preventDefault(); e.stopPropagation();
    const col = cols[c]; const x0 = e.clientX; const w0 = widths[col.key] ?? col.width; const z = zoom;
    const el = e.currentTarget; el.setPointerCapture(e.pointerId); el.classList.add("gt-on");
    el.onpointermove = (m) => setWidths((w) => ({ ...w, [col.key]: Math.max(46, Math.min(500, Math.round(w0 + (m.clientX - x0) / z))) }));
    el.onpointerup = () => { el.onpointermove = null; el.onpointerup = null; el.classList.remove("gt-on"); };
  };

  // ── copy, cut, paste ──
  const onCopy = (e) => { if (editing) return; e.clipboardData.setData("text/plain", toTSV(lines, rows, cols, s, today)); e.preventDefault(); say(WORDS.copied); };
  const onCut = (e) => { if (editing) return; e.clipboardData.setData("text/plain", toTSV(lines, rows, cols, s, today)); e.preventDefault(); if (edit) clearSelected(); else say(WORDS.copied); };
  const onPaste = (e) => { if (editing) return; e.preventDefault(); pasteText(e.clipboardData.getData("text/plain")); };

  const toggleHidden = (col) => {
    const now_ = new Set(hidden);
    const was = now_.has(col.key);
    if (was) now_.delete(col.key); else now_.add(col.key);
    if (onHiddenChange) onHiddenChange(COLUMNS.map((c) => c.key).filter((k) => now_.has(k)));
    say(WORDS.hiddenCol(col.label, !was));
  };
  const eyeWords = (col) => (hidden.includes(col.key) ? "Hidden from the client view" : "Shown in the client view");

  // ── drawing ──
  const cur = cols[s.fc]; const curLine = lineAt(s.fr);
  const where = cur && curLine ? `${cur.label}, line ${rows[s.fr] + 1}${cellCount(s) > 1 ? ` · ${cellCount(s)} cells selected` : ""}` : "";
  const typeOf = (l) => ({ p: "gt-p", t: "gt-t", m: "gt-m" })[l.t] || "";

  const cell = (l, i, r, col, c) => {
    const val = getValue(l, col.key, today);
    const isEd = editing && editing.r === r && editing.c === c;
    const inSel = inRange(s, r, c);
    const act = r === s.fr && c === s.fc;
    const bad = col.key === "s" && clash[l.id];
    const cls = ["gt-cell", col.type === "ro" ? "gt-ro" : "", c < 2 ? "gt-fz" : "", inSel && !act ? "gt-sel" : "", act ? "gt-act" : "", isEd ? "gt-ed" : "",
      bad ? "gt-clash" : "", edit && r === range.r1 && c === range.c1 && !editing ? "gt-last" : ""].filter(Boolean).join(" ");
    let inner = val;
    if (isEd) {
      const e0 = editing.init;
      if (col.type === "select") {
        const pick = e0 ? col.options.find((o) => o && o.toLowerCase().startsWith(e0.toLowerCase())) : undefined;
        inner = <select ref={field} aria-label={col.label} onKeyDown={onInputKey} onBlur={() => finishEdit(0, 0, true)}>{col.options.map((o) => <option key={o} value={o} selected={o === (pick ?? val)}>{o}</option>)}</select>;
      } else {
        inner = <input ref={field} aria-label={col.label} defaultValue={e0 !== undefined ? e0 : val} onKeyDown={onInputKey} onBlur={() => finishEdit(0, 0, true)} />;
      }
    }
    const fh = edit && !editing && r === range.r1 && c === range.c1 ? <i class="gt-fh" title="Drag down to fill" /> : null;
    return (
      <td key={col.key} class={cls} data-r={r} data-c={c} data-k={col.key} role="gridcell" aria-selected={inSel ? "true" : "false"} aria-readonly={edit && col.type !== "ro" ? undefined : "true"}
        style={c < 2 ? { left: `${lefts[c]}px` } : undefined} title={bad ? WORDS.startsBefore(clash[l.id]) : undefined}>
        {inner}{fh}
      </td>
    );
  };

  useEffect(() => {
    if (menu && menuBox.current) { const b = menuBox.current.querySelector("button"); if (b) b.focus(); }
  }, [menu]);
  useEffect(() => {
    if (editing && field.current) {
      const el = field.current;
      el.focus();
      if (el.tagName === "INPUT") { if (editing.init === undefined) el.select(); else el.setSelectionRange(el.value.length, el.value.length); }
    }
  }, [editing]);

  return (
    <div class="gt" data-gt data-mode={edit ? "edit" : "view"} style={{ "--gz": zoom }}>
      <div class="gt-bar">
        <button type="button" data-gt-zoom-out aria-label="Zoom out" title="Zoom out" onClick={() => setZoom(clampZoom(zoom / 1.2))}>−</button>
        <button type="button" data-gt-zoom-fit aria-label="Back to fit" title="Back to fit" onClick={() => setZoom(1)}>{Math.round(zoom * 100)}%</button>
        <button type="button" data-gt-zoom-in aria-label="Zoom in" title="Zoom in" onClick={() => setZoom(clampZoom(zoom * 1.2))}>+</button>
        <span role="status" aria-live="polite" data-gt-msg={msg && msg.bad ? "bad" : msg ? "ok" : ""} class={`gt-msg${msg && msg.bad ? " gt-bad" : ""}`}>
          {msg ? msg.text : ""}
          {msg && msg.undo && edit && !onUndo ? <button type="button" data-gt-undo onClick={goUndo}>Undo</button> : null}
        </span>
        <span class="gt-pos" data-gt-where>{where}</span>
      </div>
      <div class="gt-scroll" ref={box} tabIndex={0} role="grid" aria-label="Plan table" aria-rowcount={rows.length + 1} aria-colcount={cols.length}
        onKeyDown={onKeyDown} onMouseDown={onMouseDown} onMouseOver={onMouseOver} onDblClick={onDblClick} onContextMenu={onContextMenu}
        onCopy={onCopy} onCut={onCut} onPaste={onPaste}>
        <table style={{ width: `${tableWidth}px` }}>
          <colgroup>{edit ? <col style={{ width: `${left0}px` }} /> : null}{cols.map((c) => <col key={c.key} style={{ width: `${width(c)}px` }} />)}</colgroup>
          <thead>
            <tr role="row">
              {edit ? <th class="gt-rh0" data-all="1" title="Select all" aria-label="Select all" /> : null}
              {cols.map((col, c) => (
                <th key={col.key} role="columnheader" data-col={c} data-k={col.key} class={`${c >= range.c0 && c <= range.c1 ? "hs" : ""}${hidden.includes(col.key) && hideable(col) ? " gt-hid" : ""}${c < 2 ? " gt-fz" : ""}`}
                  style={c < 2 ? { left: `${lefts[c]}px` } : undefined}>
                  <span class="gt-hl">{col.label}</span>
                  {edit && hideable(col) ? (
                    <button type="button" class="gt-eye" data-hc={col.key} aria-pressed={hidden.includes(col.key) ? "true" : "false"} title={eyeWords(col)}
                      aria-label={`${eyeWords(col)}: ${col.label}`} onClick={(e) => { e.stopPropagation(); toggleHidden(col); }}>
                      <Icon name={hidden.includes(col.key) ? "eyeoff" : "eye"} />
                    </button>
                  ) : null}
                  <i class="gt-cr" data-c={c} title="Drag to change the width. Double-click to fit." onPointerDown={(e) => startResize(e, c)} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((i, r) => {
              const l = lines[i];
              return (
                <tr key={l.id} role="row" class={typeOf(l)} data-id={l.id}>
                  {edit ? (
                    <th class={`gt-rh${r >= range.r0 && r <= range.r1 ? " hs" : ""}`} data-row={r} data-r={r} scope="row">
                      <span class="gt-rn">{i + 1}</span>
                      <button type="button" class="gt-rb" data-add={r} aria-label={addBelowWord} title={addBelowWord}
                        onClick={(e) => { e.stopPropagation(); const b = e.currentTarget.getBoundingClientRect(); setSel(makeSel(r, 0, r, cols.length - 1)); showMenu(b.left, b.bottom + 4, [["Add a task below", () => addBelow(r, "t")], ["Add a phase below", () => addBelow(r, "p")], ["Add a milestone below", () => addBelow(r, "m")]]); }}><Icon name="plus" /></button>
                      <button type="button" class="gt-rb gt-del" data-del={r} aria-label="Delete this line" title="Delete this line"
                        onClick={(e) => { e.stopPropagation(); if (r >= range.r0 && r <= range.r1 && range.r1 > range.r0) removeRows(range.r0, range.r1); else removeRows(r, r); focusBox(); }}><Icon name="x" /></button>
                    </th>
                  ) : null}
                  {cols.map((col, c) => cell(l, i, r, col, c))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {menu ? (
        <Fade class="gt-menu" role="menu" boxRef={menuBox} style={{ left: `${Math.min(menu.x, (window.innerWidth || 1400) - 230)}px`, top: `${Math.min(menu.y, (window.innerHeight || 900) - 200)}px` }}
          onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setMenu(null); focusBox(); } }}>
          {menu.items.map((it, n) => (it === "-" ? <hr key={n} /> : (
            <button key={n} type="button" role="menuitem" class={it[2] ? "gt-danger" : ""} onClick={() => { setMenu(null); it[1](); }}><Icon name={actionIcon(rowAction(it))} cls="mi" /><span>{it[0]}</span></button>
          )))}
        </Fade>
      ) : null}
    </div>
  );
}
