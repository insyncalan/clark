// One shared way to change a column's width in a table of the editor (row 1104): drag the right edge of a heading; or, from the keyboard,
// press Alt+Left or Alt+Right with the focus on a heading cell or anywhere in the column of a row (the handle itself is not a tab stop, so a
// table stays one tab stop with the arrows moving inside it); a double-click on the edge puts that column back. The widths are kept for each table on this computer
// (logic/remember.js), never in the data, and a published page does not have this file: it keeps its default widths.
// A table calls useColWidths(name) once, puts `style` on each column (or a heading) and `grip(id, label)` inside each heading.
import { useEffect, useRef, useState } from "preact/hooks";
import { recall, remember } from "../logic/remember.js";

export const MIN_COL = 48;      // a column cannot be made narrower than this, so it cannot vanish
const STEP = 12;                // one arrow press
const MAX_COL = 1200;

const clampTo = (lo, hi) => (n) => Math.max(lo, Math.min(hi, Math.round(n)));
export const LIST_MIN = 60;      // row 1195: the Classic Work items list keeps a width between 60 and 360 px, as the approved mock-up does
export const LIST_MAX = 360;

export function useColWidths(table, ctrl = false) {      // row 1195: ctrl true (the Work items list under Classic): Ctrl with an arrow changes the width, Alt with an arrow is left to moving the column
  const clamp = ctrl ? clampTo(LIST_MIN, LIST_MAX) : clampTo(MIN_COL, MAX_COL);
  const key = `cols.${table}`;
  const [saved, setSaved] = useState(() => {
    const v = recall(key, {});
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  });
  // The widths as they are now, read from a ref (never from the render a drag started in), so a drag, a key and a double-click
  // each start from the latest. `keep` false: only the screen changes (a drag in progress); the store is written when it ends.
  const now = useRef(saved);
  now.current = saved;
  const put = (id, px, keep = true) => {
    const next = { ...now.current };
    if (px === null) delete next[id]; else next[id] = clamp(px);
    now.current = next;
    setSaved(next);
    if (keep) remember(key, next);
  };
  const px = (id) => (Number.isFinite(saved[id]) ? clamp(saved[id]) : null);
  const style = (id) => (px(id) === null ? undefined : { width: `${px(id)}px` });
  const grip = (id, label) => {
    const start = (e) => {
      if (e.button) return;
      e.preventDefault();
      const from = e.clientX, was = e.currentTarget.parentElement.getBoundingClientRect().width;
      const move = (m) => put(id, was + m.clientX - from, false);
      const stop = () => { remember(key, now.current); document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", stop); document.removeEventListener("pointercancel", stop); };
      document.addEventListener("pointermove", move); document.addEventListener("pointerup", stop); document.addEventListener("pointercancel", stop);
    };
    return <span class="cgrip" aria-hidden="true" data-cgrip={id} onPointerDown={start} onClick={(e) => e.stopPropagation()} onDblClick={(e) => { e.stopPropagation(); put(id, null); }}></span>;
  };
  /** Props for the heading cell (row 1195, Classic Work items list: a tab stop, labelled with the mock-up's words, the Item heading without the move words). Otherwise: not a tab stop, but it can hold the focus (a click on it, or the code); it says how its width changes. */
  const head = (id, label, hidden) => hidden ? { "data-cw-head": id, "data-cw-table": table } : ctrl ? { tabIndex: 0, "data-cw-head": id, "data-cw-table": table, "aria-label": `${label} column. ${id === "title" ? "" : "Drag to move it; Alt with an arrow key moves it; "}${id === "title" ? "D" : "d"}rag its right edge or press Ctrl with an arrow key to resize` } : { tabIndex: -1, "data-cw-head": id, "data-cw-table": table, "aria-description": `Width of the ${label} column. Alt with Left or Right arrow changes it.` };
  // hidden: the heading row is hidden from a screen reader (the Milestones list), so it holds no focus and no words; the arrows work from a row.
  const latest = useRef();
  latest.current = { put, ctrl };
  useEffect(() => {
    const onKey = (e) => {
      const mod = latest.current.ctrl ? e.ctrlKey && !e.altKey : e.altKey && !e.ctrlKey;      // the key that changes a width: Alt, or Ctrl under Classic's Work items list
      if (!mod || e.metaKey || e.shiftKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
      const t = e.target;
      if (!t || !t.closest || t.isContentEditable || t.closest("input, textarea, select, .ProseMirror")) return;
      let cell = t.closest("[data-cw-head]");
      if (!cell) {
        const box = t.closest("table, .ucl-box, .msl-box");
        const x = t.getBoundingClientRect().left + 1;
        cell = box && Array.from(box.querySelectorAll("[data-cw-head]")).find((h) => { const r = h.getBoundingClientRect(); return x < r.right; });
      }
      if (!cell || cell.getAttribute("data-cw-table") !== table) return;
      e.preventDefault(); e.stopPropagation();
      latest.current.put(cell.getAttribute("data-cw-head"), cell.getBoundingClientRect().width + (e.key === "ArrowRight" ? STEP : -STEP));
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [table]);
  /** The widths to draw in a table `room` px wide (row 1104): the saved widths shrink together when they would leave the first column under `least` px
   *  next to the columns that have no saved width (`rest`, their drawn px); the saved values themselves are never changed. */
  const fit = (ids, room, rest, least = 160) => {
    const own = ids.filter((id) => px(id) !== null), sum = own.reduce((a, id) => a + px(id), 0), free = room - least - rest;
    return sum > 0 && sum > free ? Math.max(0, free) / sum : 1;
  };
  const drawn = (id, k) => (px(id) === null ? undefined : { width: `${k < 1 ? Math.max(MIN_COL, Math.floor(px(id) * k)) : px(id)}px` });
  const any = () => Object.keys(saved).some((id) => px(id) !== null);       // a table with a chosen width is laid out in fixed mode, so the width holds
  return { px, style, grip, head, fit, drawn, any };
}

/** A grid template: each default track, with the track of a column that has a chosen width set to that many pixels. `ids` runs along the tracks. */
export function gridTracks(tracks, ids, cw) {
  return tracks.map((t, i) => (ids[i] && cw.px(ids[i]) !== null ? `${cw.px(ids[i])}px` : t)).join(" ");
}

/** Row 1195 (the Work items list under Classic): the order of a table's columns, changed by dragging a heading onto another or, from the keyboard, Alt with Left or Right arrow on a heading.
 *  Kept for each table on this computer (logic/remember.js), never in the data. `apply(ids)` is the ids in the kept order (a column never moved keeps its place after the moved ones);
 *  `props(id, ids)` goes on the heading cell. A drop on a heading puts the dragged column in that heading's place. */
export function useColOrder(table, shared = null) {      // row 1534: `shared` = { read(): ids, write(ids, id) } keeps the order with the project instead of this browser, and also moves with Alt+Shift
  const key = `order.${table}`;
  const [mine, setSaved] = useState(() => { const v = recall(key, []); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; });
  const [drag, setDrag] = useState(null), [over, setOver] = useState(null);
  const focus = useRef(null), from = useRef(null), onGrip = useRef(false);
  // After a move the heading keeps the focus, so the next arrow press moves it again. The saved order is drawn again when the save's reply is read back, and that can
  // draw the heading cell new, which drops the focus to the page: the wish stays until the focus is somewhere else on purpose (a press, or another control taking it).
  useEffect(() => {
    if (!focus.current) return;
    const a = document.activeElement, h = document.querySelector(`[data-cw-table="${table}"][data-cw-head="${focus.current}"]`);
    if (h && h.focus && (!a || a === document.body)) h.focus();
  });
  useEffect(() => {
    const off = (e) => { if (focus.current && !(e.target && e.target.closest && e.target.closest(`[data-cw-table="${table}"][data-cw-head="${focus.current}"]`))) focus.current = null; };
    document.addEventListener("focusin", off, true); document.addEventListener("pointerdown", off, true);
    return () => { document.removeEventListener("focusin", off, true); document.removeEventListener("pointerdown", off, true); };
  }, [table]);
  const saved = shared ? shared.read() : mine;
  const apply = (ids) => { const known = saved.filter((x) => ids.includes(x)); return known.concat(ids.filter((x) => !known.includes(x))); };
  const move = (a, b, ids) => {
    const now = apply(ids);
    if (a === b || !now.includes(a) || !now.includes(b)) return;
    const o = now.filter((x) => x !== a), i = o.indexOf(b);
    o.splice(now.indexOf(a) < now.indexOf(b) ? i + 1 : i, 0, a);
    if (shared) shared.write(o, a); else { setSaved(o); remember(key, o); }
    focus.current = a;
  };
  // row 1534 (a Dashboard list of one type): a heading is dragged with the pointer (a mouse, a pen or a finger: HTML5 draggable does not fire on touch, as in the Work items table, ColumnsMenu.jsx).
  // A press that moves less than 5 px is a click and moves nothing; a drop on another movable heading of the row moves the column there; a drop anywhere else, on the Status or the Item, or Esc cancels.
  const press = (id, ids) => (e) => {
    if (e.button || (e.target.closest && e.target.closest(".cgrip, button"))) return;
    const th = e.currentTarget, row = th.parentElement, x0 = e.clientX, y0 = e.clientY;
    let moving = false, to = null;
    const heads = () => Array.from(row.querySelectorAll("th[data-move]"));
    const clear = () => heads().forEach((t) => { t.classList.remove("col-dragging", "col-drop-before", "col-drop-after"); });
    const hit = (m) => { const el = document.elementFromPoint(m.clientX, m.clientY), t = el && el.closest ? el.closest("th[data-move]") : null; return t && t.parentElement === row ? t : null; };
    const go = (m) => {
      if (!moving && Math.hypot(m.clientX - x0, m.clientY - y0) < 5) return;
      moving = true; clear(); th.classList.add("col-dragging"); to = null;
      const t = hit(m), tid = t && t.getAttribute("data-cw-head");
      if (!t || tid === id) return;
      to = tid; t.classList.add(heads().indexOf(t) > heads().indexOf(th) ? "col-drop-after" : "col-drop-before");
    };
    const done = (drop) => {
      document.removeEventListener("pointermove", go); document.removeEventListener("pointerup", up); document.removeEventListener("pointercancel", cancel); document.removeEventListener("keydown", key, true); document.removeEventListener("selectstart", stop, true); document.removeEventListener("dragstart", stop, true);
      clear();
      if (!moving) return;
      const quiet = (c) => { c.stopPropagation(); c.preventDefault(); };      // the click that ends a drag is not a click on the heading
      document.addEventListener("click", quiet, { capture: true, once: true }); setTimeout(() => document.removeEventListener("click", quiet, true), 0);
      if (drop && to) move(id, to, ids);
    };
    const up = () => done(true), cancel = () => done(false), key = (k) => { if (k.key === "Escape") { k.stopPropagation(); done(false); } }, stop = (x) => x.preventDefault();      // no text selection and no browser drag of a selection while a heading is dragged
    document.addEventListener("selectstart", stop, true); document.addEventListener("dragstart", stop, true);
    document.addEventListener("pointermove", go); document.addEventListener("pointerup", up); document.addEventListener("pointercancel", cancel); document.addEventListener("keydown", key, true);
  };
  const keys = (id, ids) => (e) => {      // Alt+Shift with an arrow (row 1534) and Alt with an arrow (row 1195, the words of the heading's label) both move it; Ctrl with an arrow still resizes
    if (!e.altKey || e.ctrlKey || e.metaKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
    if (!e.target.closest || e.target.closest("input, textarea, select")) return;
    e.preventDefault(); e.stopPropagation();
    const now = apply(ids), j = now.indexOf(id) + (e.key === "ArrowLeft" ? -1 : 1);
    if (now[j] && !(shared && now[j] === "status")) move(id, now[j], ids);
  };
  const props = (id, ids) => shared ? (id === "status" || !ids.includes(id) ? {} : { "data-move": "", onPointerDown: press(id, ids), onKeyDown: keys(id, ids) }) : ({
    draggable: true,
    onPointerDownCapture: (e) => { onGrip.current = !!(e.target.closest && e.target.closest(".cgrip")); },      // a press on the width handle resizes, it never starts a move
    onDragStart: (e) => {
      if (onGrip.current) { e.preventDefault(); return; }
      from.current = id; setDrag(id);
      if (e.dataTransfer) { e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setData("text/plain", id); } catch (x) { /* a browser that refuses: the move still works from the ref */ } }
    },
    onDragOver: (e) => { if (!from.current) return; e.preventDefault(); if (over !== id) setOver(id); },
    onDrop: (e) => { if (!from.current) return; e.preventDefault(); move(from.current, id, ids); from.current = null; setDrag(null); setOver(null); },
    onDragEnd: () => { from.current = null; setDrag(null); setOver(null); },
    onKeyDown: (e) => {
      if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
      if (!e.target.closest || e.target.closest("input, textarea, select")) return;
      e.preventDefault(); e.stopPropagation();
      const now = apply(ids), j = now.indexOf(id) + (e.key === "ArrowLeft" ? -1 : 1);
      if (now[j]) move(id, now[j], ids);
    },
  });
  const cls = (id, ids) => (shared ? (id === "status" || !ids || !ids.includes(id) ? "" : " col-move") : `${drag === id ? " wil-dragging" : ""}${over === id && drag !== id ? " wil-drop" : ""}`);      // col-move: the grab cursor, and a finger drags the heading instead of scrolling the page (rules-2.css)
  return { apply, props, cls };
}
