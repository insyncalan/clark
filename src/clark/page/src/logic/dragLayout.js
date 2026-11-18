// Row 1214, the pure part of the live layout drag: which target a pointer means, decided from the section rects measured when the
// drag started (never from the preview, which moves the sections), and when the slot may move (the pointer must rest on a new
// target for REST_MS). No DOM, no signals, no timers: the page gives these functions the rects, the point and the time.
import { rows, place } from "./placement.js";

export const EDGE = 56;                            // px, the most a top or bottom edge may be, the same as EDGE in placement.js
export const REST_MS = 110;                        // ms the pointer rests on a new target before the slot moves

// A copy of the rects as they are at the start of the drag. Later changes to the page cannot reach it.
export function freezeRects(rects) {
  const out = {};
  for (const id of Object.keys(rects || {})) {
    const r = rects[id];
    out[id] = Object.freeze({ left: r.left, top: r.top, right: r.right, bottom: r.bottom });
  }
  return Object.freeze(out);
}

// The target for `point` { x, y }, from the start rects `rects` { id: { left, top, right, bottom } } (the sections as drawn when
// the drag began; a section with no rect is left out). Columns 2: pairs sit side by side; 1: they stack, so there is no half.
//   top quarter of a row: a full width row above it. bottom quarter: a full width row below it. A quarter is at most 56 px (a tall
//   row keeps a wide half width zone), the same edge as placement.js.
//   middle of a section that is alone: half width, left or right of it (left half of it is left, right half is right).
//   over a pair: only above or below, the nearer of the two.
// null where a drop would change nothing: over the moved section's own old place, or any target that gives back the same page.
export function dragTarget(sections, id, rects, point, opts) {
  const columns = opts && opts.columns === 1 ? 1 : 2;
  const all = rows(sections).filter((r) => r.some((s) => rects[s.id]));
  if (!all.length || !point) return null;
  const k = rowAt(all, rects, point);
  const row = all[k];
  if (row.some((s) => s.id === id) && row.length === 1) return null;        // its own old place, on its own row
  const drawn = row.map((s) => rects[s.id]).filter(Boolean);
  const top = Math.min(...drawn.map((r) => r.top)), bottom = Math.max(...drawn.map((r) => r.bottom));
  const above = () => ({ before: row[0].id });
  const below = () => {
    const next = all[k + 1];
    return next ? { before: next[0].id } : { before: null };
  };
  const quarter = Math.min((bottom - top) / 4, EDGE);
  let target;
  if (point.y < top + quarter) target = above();
  else if (point.y > bottom - quarter) target = below();
  else if (columns === 2 && row.length === 1) {
    const r = rects[row[0].id];
    target = { beside: row[0].id, side: point.x < r.left + (r.right - r.left) / 2 ? "left" : "right" };
  } else if (row.some((s) => s.id === id)) return null;                     // the middle of its own pair: its old place, no unpairing
  else target = point.y < (top + bottom) / 2 ? above() : below();
  return place(sections, id, target).ok ? target : null;
}

// The row nearest the point, by distance to the row's box; above the first is the first, below the last is the last.
function rowAt(all, rects, point) {
  let best = 0, near = Infinity;
  all.forEach((row, k) => {
    for (const s of row) {
      const r = rects[s.id];
      if (!r) continue;
      const dx = Math.max(r.left - point.x, 0, point.x - r.right), dy = Math.max(r.top - point.y, 0, point.y - r.bottom);
      if (dx * dx + dy * dy < near) { near = dx * dx + dy * dy; best = k; }
    }
  });
  return best;
}

// A target as a string, so two targets compare by what they mean. null: "none".
export function targetKey(t) {
  if (!t) return "none";
  return "beside" in t ? `beside:${t.beside}:${t.side}` : `before:${t.before === null ? "" : t.before}`;
}

// The rest-time rule. `state` is { shown, want, since } (start with settleStart()), `target` what the pointer means now, `now` ms.
// Returns { shown, want, since, moved }: `shown` is the target the slot is drawn at. It changes to `want` only when the pointer has
// meant the same new target for REST_MS; a pass over a section that is shorter changes nothing, and `moved` is true only on the
// call that changes `shown` (draw then, not before).
export function settleStart() {
  return { shown: null, want: null, since: 0 };
}
export function settle(state, target, now) {
  const key = targetKey(target);
  if (key === targetKey(state.want)) {
    if (key !== targetKey(state.shown) && now - state.since >= REST_MS) return { shown: target, want: target, since: state.since, moved: true };
    return { shown: state.shown, want: state.want, since: state.since, moved: false };
  }
  return { shown: state.shown, want: target, since: now, moved: false };
}

// How long a timer must still wait for the slot to move: 0 when nothing waits (the pointer means the shown target, or the rest is
// already over), else the ms left of REST_MS since `want` was first meant. A timer that fires early (setTimeout may run a ms or
// more before its time) asks this and sets itself again for the rest, so the slot is not left behind a pointer that stopped.
export function restLeft(state, now) {
  if (targetKey(state.want) === targetKey(state.shown)) return 0;
  return Math.max(0, REST_MS - (now - state.since));
}
