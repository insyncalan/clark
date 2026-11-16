// Dragging a section by its handle (row 95; row 1214 made it steady). Pointer events, not the browser's own drag and drop, so a mouse,
// a pen and a finger all work and the handle stays the same element, keeping focus. What the pointer means comes from
// logic/dragLayout.js (dragTarget, from the section rects measured once when the drag starts, never from what the page shows
// later); the line moves only after the pointer has rested REST_MS on a new target (settle), and the page is redrawn only when the
// shown target changes. What is drawn comes from logic/placement.js (indicator), and the drop is the shown target, so the line on
// the page and the drop cannot disagree. Esc puts everything back.
// Row 101's new grip calls startDrag too.
import { data, dropAt } from "../stores/report.js";
import { indicator } from "../logic/placement.js";
import { dragTarget, freezeRects, settle, settleStart, restLeft, REST_MS } from "../logic/dragLayout.js";
import { placeAt } from "./actions.js";

const THRESHOLD = 4;                           // px the pointer must travel before it is a drag and not a click
const STACKED = "(max-width: 900px)";          // one column: a pair stacks, so there is no half to drop on

function rects() {
  const out = {};
  for (const el of document.querySelectorAll(".secs > .sec[data-id]")) {
    const r = el.getBoundingClientRect();
    out[el.dataset.id] = { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
  }
  return out;
}

// Start a drag of section `id` from a pointerdown on `handle` (its element). `count` is how many sections there are.
export function startDrag(e, handle, id, count) {
  if (e.button !== 0 || count < 2) return;
  e.preventDefault();
  const startX = e.clientX, startY = e.clientY;
  const scrollX = window.scrollX, scrollY = window.scrollY;
  const start = freezeRects(rects());            // measured once, here: it is never measured again
  let dragging = false, cancelled = false, state = settleStart(), timer = 0, ptr = null;
  try { handle.setPointerCapture(e.pointerId); } catch (x) { /* a pointer that cannot be captured still drags */ }
  handle.focus();
  const sections = () => ((data.value && data.value.report_sections) || []).filter((s) => s.type !== "needs");      // item 1174: as the Dashboard draws them
  const clear = () => { if (timer) { clearTimeout(timer); timer = 0; } };
  const show = (t) => { dropAt.value = (t && indicator(sections(), id, t)) || undefined; };
  const aim = () => {                            // where the pointer is now, in the frame of the start rects
    const columns = window.matchMedia(STACKED).matches ? 1 : 2;
    const point = { x: ptr.x + (window.scrollX - scrollX), y: ptr.y + (window.scrollY - scrollY) };
    state = settle(state, dragTarget(sections(), id, start, point, { columns }), performance.now());
    if (state.moved) show(state.shown);          // redraw only when the shown target changed
  };
  const arm = (ms) => {                          // an early timer sets itself again for the time left, so the rest is never lost
    timer = setTimeout(() => {
      timer = 0;
      if (cancelled) return;
      aim();
      const left = restLeft(state, performance.now());
      if (left > 0) arm(left);
    }, ms);
  };
  const move = (m) => {
    if (cancelled) return;                       // Esc is final: more movement cannot bring the drop back
    if (!dragging && Math.hypot(m.clientX - startX, m.clientY - startY) < THRESHOLD) return;
    dragging = true;
    ptr = { x: m.clientX, y: m.clientY };
    aim();
    clear();
    arm(REST_MS);                                // a pointer that stops still counts as resting
  };
  const cancel = (k) => { if (k.key === "Escape") { cancelled = true; clear(); state = settleStart(); dropAt.value = undefined; } };   // Esc: releasing now drops nothing
  const end = (u) => {
    clear();
    document.removeEventListener("keydown", cancel);
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", end);
    document.removeEventListener("pointercancel", end);
    dropAt.value = undefined;
    const target = state.shown;
    if (dragging && !cancelled && u.type === "pointerup" && target) placeAt(id, target, "report", "handle");     // dropped where it already is: placement says nothing
  };
  document.addEventListener("keydown", cancel);
  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", end);
  document.addEventListener("pointercancel", end);
}
