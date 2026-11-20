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
export function useColOrder(table) {
  const key = `order.${table}`;
  const [saved, setSaved] = useState(() => { const v = recall(key, []); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; });
  const [drag, setDrag] = useState(null), [over, setOver] = useState(null);
  const focus = useRef(null), from = useRef(null), onGrip = useRef(false);
  useEffect(() => {      // after a move the heading keeps the focus, so the next arrow press moves it again
    if (!focus.current) return;
    const h = document.querySelector(`[data-cw-table="${table}"][data-cw-head="${focus.current}"]`);
    focus.current = null;
    if (h && h.focus) h.focus();
  });
  const apply = (ids) => { const known = saved.filter((x) => ids.includes(x)); return known.concat(ids.filter((x) => !known.includes(x))); };
  const move = (a, b, ids) => {
    const now = apply(ids);
    if (a === b || !now.includes(a) || !now.includes(b)) return;
    const o = now.filter((x) => x !== a), i = o.indexOf(b);
    o.splice(now.indexOf(a) < now.indexOf(b) ? i + 1 : i, 0, a);
    setSaved(o); remember(key, o); focus.current = a;
  };
  const props = (id, ids) => ({
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
  const cls = (id) => `${drag === id ? " wil-dragging" : ""}${over === id && drag !== id ? " wil-drop" : ""}`;
  return { apply, props, cls };
}
