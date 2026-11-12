// One shared way to change a column's width in a table of the editor (row 1104): drag the right edge of a heading, or focus the
// edge and press Left or Right; a double-click on the edge puts that column back. The widths are kept for each table on this computer
// (logic/remember.js), never in the data, and a published page does not have this file: it keeps its default widths.
// A table calls useColWidths(name) once, puts `style` on each column (or a heading) and `grip(id, label)` inside each heading.
import { useState } from "preact/hooks";
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
  const put = (id, px) => {
    const next = { ...saved };
    if (px === null) delete next[id]; else next[id] = clamp(px);
    setSaved(next);
    remember(key, next);
  };
  const px = (id) => (Number.isFinite(saved[id]) ? clamp(saved[id]) : null);
  const style = (id) => (px(id) === null ? undefined : { width: `${px(id)}px` });
  const grip = (id, label) => {
    const start = (e) => {
      if (e.button) return;
      e.preventDefault();
      const from = e.clientX, was = e.currentTarget.parentElement.getBoundingClientRect().width;
      const move = (m) => put(id, was + m.clientX - from);
      const stop = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", stop); document.removeEventListener("pointercancel", stop); };
      document.addEventListener("pointermove", move); document.addEventListener("pointerup", stop); document.addEventListener("pointercancel", stop);
    };
    const key = (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault(); e.stopPropagation();
      put(id, e.currentTarget.parentElement.getBoundingClientRect().width + (e.key === "ArrowRight" ? STEP : -STEP));
    };
    return <span class="cgrip" role="separator" aria-orientation="vertical" tabIndex={0} data-cgrip={id} aria-valuemin={MIN_COL} aria-valuenow={px(id) === null ? undefined : px(id)}
      aria-label={`Width of the ${label} column. Left and Right arrows change it.`}
      onPointerDown={start} onKeyDown={key} onClick={(e) => e.stopPropagation()} onDblClick={(e) => { e.stopPropagation(); put(id, null); }}></span>;
  };
  return { px, style, grip };
}

/** A grid template: each default track, with the track of a column that has a chosen width set to that many pixels. `ids` runs along the tracks. */
export function gridTracks(tracks, ids, cw) {
  return tracks.map((t, i) => (ids[i] && cw.px(ids[i]) !== null ? `${cw.px(ids[i])}px` : t)).join(" ");
}
