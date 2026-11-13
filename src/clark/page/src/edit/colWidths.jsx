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

const clamp = (n) => Math.max(MIN_COL, Math.min(MAX_COL, Math.round(n)));

export function useColWidths(table) {
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
  /** Props for the heading cell: not a tab stop, but it can hold the focus (a click on it, or the code); it says how its width changes. */
  const head = (id, label, hidden) => hidden ? { "data-cw-head": id, "data-cw-table": table } : { tabIndex: -1, "data-cw-head": id, "data-cw-table": table, "aria-description": `Width of the ${label} column. Alt with Left or Right arrow changes it.` };
  // hidden: the heading row is hidden from a screen reader (the Milestones list), so it holds no focus and no words; the arrows work from a row.
  const latest = useRef();
  latest.current = { put };
  useEffect(() => {
    const onKey = (e) => {
      if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
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
  return { px, style, grip, head };
}

/** A grid template: each default track, with the track of a column that has a chosen width set to that many pixels. `ids` runs along the tracks. */
export function gridTracks(tracks, ids, cw) {
  return tracks.map((t, i) => (ids[i] && cw.px(ids[i]) !== null ? `${cw.px(ids[i])}px` : t)).join(" ");
}
