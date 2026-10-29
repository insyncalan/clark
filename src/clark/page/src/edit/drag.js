// Dragging a section by its handle (#95). Pointer events, not the browser's own drag and drop, so a mouse, a pen and a finger all
// work and the handle stays the same element, keeping focus. Where the pointer is, and what to draw, come from logic/placement.js
// (targetAt and indicator), and the drop is placement's own result, so the line on the page and the drop cannot disagree.
// #101's new grip calls startDrag too.
import { data, dropAt } from "../stores/report.js";
import { targetAt, indicator } from "../logic/placement.js";
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
  let dragging = false, cancelled = false, target = null;
  try { handle.setPointerCapture(e.pointerId); } catch (x) { /* a pointer that cannot be captured still drags */ }
  handle.focus();
  const sections = () => (data.value && data.value.report_sections) || [];
  const move = (m) => {
    if (cancelled) return;                       // Esc is final: more movement cannot bring the drop back
    if (!dragging && Math.hypot(m.clientX - startX, m.clientY - startY) < THRESHOLD) return;
    dragging = true;
    const columns = window.matchMedia(STACKED).matches ? 1 : 2;
    target = targetAt(sections(), id, rects(), { x: m.clientX, y: m.clientY }, { columns });
    dropAt.value = (target && indicator(sections(), id, target)) || undefined;
  };
  const cancel = (k) => { if (k.key === "Escape") { cancelled = true; target = null; dropAt.value = undefined; } };   // Esc: releasing now drops nothing
  const end = (u) => {
    document.removeEventListener("keydown", cancel);
    handle.removeEventListener("pointermove", move);
    handle.removeEventListener("pointerup", end);
    handle.removeEventListener("pointercancel", end);
    dropAt.value = undefined;
    if (dragging && !cancelled && u.type === "pointerup" && target) placeAt(id, target, "report", "handle");     // dropped where it already is: placement says nothing
  };
  document.addEventListener("keydown", cancel);
  handle.addEventListener("pointermove", move);
  handle.addEventListener("pointerup", end);
  handle.addEventListener("pointercancel", end);
}
