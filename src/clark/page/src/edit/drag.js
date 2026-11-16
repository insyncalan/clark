// Dragging a section by its handle (row 95; row 1214 made it steady). Pointer events, not the browser's own drag and drop, so a mouse,
// a pen and a finger all work and the handle stays the same element, keeping focus. What the pointer means comes from
// logic/dragLayout.js (dragTarget, from the section rects measured once when the drag starts, never from what the page shows
// later); the slot moves only after the pointer has rested REST_MS on a new target (settle), and the page is redrawn only when the
// shown target changes. What is drawn comes from logic/placement.js (indicator), and the drop is the shown target, so the line on
// the page and the drop cannot disagree. Esc puts everything back.
// Row 1214, what the person sees: a ghost (a copy of the title) follows the pointer, a faint dashed outline stays at the old place,
// the section is drawn as a dashed slot where it would land, and the others make room (dragList: the page as the drop would leave it).
// Row 101's new grip calls startDrag too.
import { data, dropAt, dragFrom, dragList, CHANGE_FAILED } from "../stores/report.js";
import { indicator, place, applied } from "../logic/placement.js";
import { noteRects } from "../components/glide.js";
import { dragTarget, freezeRects, settle, settleStart, restLeft, REST_MS } from "../logic/dragLayout.js";
import { placeAt } from "./actions.js";
import { say } from "../stores/changes.js";
import { edgeStep } from "../logic/edgeScroll.js";

const THRESHOLD = 4;                           // px the pointer must travel before it is a drag and not a click
const STACKED = "(max-width: 900px)";          // one column: a pair stacks, so there is no half to drop on

let saving = false;                              // a drop is being stored: the page still shows the preview while the stored order is the old one, so no new drag starts until it is done

function rects() {
  const out = {};
  for (const el of document.querySelectorAll(".secs > .sec[data-id]")) {
    const r = el.getBoundingClientRect();
    out[el.dataset.id] = { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
  }
  return out;
}

let active = false;                              // one drag at a time: a second finger or pen has no drag of its own, the signals are shared

// Start a drag of section `id` from a pointerdown on `handle` (its element). `count` is how many sections there are.
export function startDrag(e, handle, id, count) {
  if (e.button !== 0 || count < 2 || active || saving) return;
  const start = freezeRects(rects());            // measured once, here: the preview moves the sections, so it is never measured again; before the drag is marked on, so a start that cannot measure blocks nothing
  active = true;
  e.preventDefault();
  const startX = e.clientX, startY = e.clientY;
  const scrollX = window.scrollX, scrollY = window.scrollY;
  let dragging = false, cancelled = false, state = settleStart(), timer = 0, last = null, ptr = null, frame = 0;
  try { handle.setPointerCapture(e.pointerId); } catch (x) { /* a pointer that cannot be captured still drags */ }
  handle.focus();
  const sections = () => ((data.value && data.value.report_sections) || []).filter((s) => s.type !== "needs");      // item 1174: as the Dashboard draws them
  const clear = () => { if (timer) { clearTimeout(timer); timer = 0; } };
  let ghost = null, was = null;                  // the title that follows the pointer, and the outline at the old place: drawn over the page, never hit by it
  const follow = (m) => { if (ghost) ghost.style.transform = `translate(${m.clientX + 12}px, ${m.clientY + 12}px)`; };
  const draw = () => {
    const mine = sections().find((s) => s.id === id), r = start[id];
    ghost = document.createElement("div");
    ghost.className = "sec-ghost";
    ghost.setAttribute("aria-hidden", "true");
    ghost.textContent = mine ? mine.title : "";
    document.body.appendChild(ghost);
    if (r) {
      was = document.createElement("div");
      was.className = "sec-was";
      was.setAttribute("aria-hidden", "true");
      Object.assign(was.style, { left: `${r.left + scrollX}px`, top: `${r.top + scrollY}px`, width: `${r.right - r.left}px`, height: `${r.bottom - r.top}px` });
      document.body.appendChild(was);
    }
    dragFrom.value = id;
    unwatch = dragFrom.subscribe((v) => { if (v === undefined && !cancelled && dragging && active) abort(); });      // the store lets go of the drag (leave): so does the drag
  };
  const wipe = () => { if (ghost) { ghost.remove(); ghost = null; } if (was) { was.remove(); was = null; } dragFrom.value = undefined; };
  const show = (t) => {
    const here = (t && indicator(sections(), id, t)) || undefined;
    const p = t && place(sections(), id, t);
    noteRects();                                 // so the sections that make room glide
    dropAt.value = here;
    dragList.value = p && p.ok ? applied(sections(), p.payload) : undefined;
  };
  const look = (point, now) => {                 // what the pointer means now, run through the rest rule
    const columns = window.matchMedia(STACKED).matches ? 1 : 2;
    state = settle(state, dragTarget(sections(), id, start, point, { columns }), now);
    if (state.moved) show(state.shown);          // redraw only when the shown target changed
  };
  const aim = () => {                            // where the pointer is now, in the frame of the start rects: also called after a scroll, as a still pointer is then over something else
    last = { x: ptr.x + (window.scrollX - scrollX), y: ptr.y + (window.scrollY - scrollY) };
    look(last, performance.now());
  };
  const stop = () => { if (frame) cancelAnimationFrame(frame); frame = 0; };
  const tick = () => {                           // near the top or bottom edge the page scrolls, so a far section can be reached
    frame = 0;
    if (cancelled || !ptr) return;
    const bar = document.querySelector(".top"), top = bar ? bar.getBoundingClientRect().bottom : 0;
    const dy = edgeStep(ptr.y, top, window.innerHeight);
    if (dy) { window.scrollBy(0, dy); aim(); }
    frame = requestAnimationFrame(tick);
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
    if (m.pointerId !== e.pointerId) return;       // another finger or pen is not this drag
    if (cancelled) return;                       // Esc is final: more movement cannot bring the drop back
    if (!dragging && Math.hypot(m.clientX - startX, m.clientY - startY) < THRESHOLD) return;
    if (!dragging) draw();
    dragging = true;
    follow(m);
    ptr = { x: m.clientX, y: m.clientY };
    aim();
    clear();
    arm(REST_MS);                                // a pointer that stops still counts as resting
    if (!frame) frame = requestAnimationFrame(tick);
  };
  let unwatch = null;
  const finish = () => {                         // every way a drag ends: nothing of it stays on the page or on the document
    stop();
    clear();
    document.removeEventListener("keydown", cancel, true);
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", end);
    document.removeEventListener("pointercancel", end);
    handle.removeEventListener("lostpointercapture", lost);
    window.removeEventListener("blur", abort);
    if (unwatch) { unwatch(); unwatch = null; }
    active = false;
    dropAt.value = undefined;
    wipe();
  };
  const abort = () => { cancelled = true; finish(); noteRects(); dragList.value = undefined; };   // the page left Edit (or the project changed) mid-drag: drop nothing
  const lost = (l) => {                          // the handle left the page mid-drag: the drag ends here and drops nothing
    if (l.pointerId !== e.pointerId) return;
    if (handle.isConnected !== false) return;    // the preview hides the grip (it is in the slot), and a hidden grip loses the capture too: that is not the end
    if (document.querySelector(`.secs > .sec[data-id="${CSS.escape(id)}"] [data-drag]`)) return;     // the page drew the grip again (a new element for the same section): the drag goes on
    abort();
  };
  const keepFromHandle = (k) => { if (k.altKey && (k.key === "ArrowUp" || k.key === "ArrowDown")) { k.preventDefault(); k.stopPropagation(); } };     // the handle's own Alt+Arrow would move the data under the frozen rects
  const cancel = (k) => { keepFromHandle(k); if (k.key === "Escape") { state = settleStart(); abort(); } };   // Esc: the drag is over now, whether or not a release ever comes (a lost window focus or pointer would leave it stuck)
  const end = (u) => {
    if (u.pointerId !== e.pointerId) return;
    stop();
    finish();
    const target = state.shown;
    if (dragging && !cancelled && u.type === "pointerup" && target) {
      saving = true;
      const clearList = () => { saving = false; dragList.value = undefined; };
      const failed = () => say("problem", CHANGE_FAILED);     // the page's own sentence for a change that could not be saved, said in the toast the other changes use
      try {
        const done = placeAt(id, target, "report", "handle");      // the others stay where the preview put them until the move is stored, so nothing jumps back and forth
        Promise.resolve(done).catch(failed).finally(clearList);
      } catch (err) { failed(); clearList(); }       // placeAt threw before it started: the preview must not stay
    } else { noteRects(); dragList.value = undefined; }     // nothing to place (dropped where it already is, Esc, click, pointercancel, no target): placement says nothing
  };
  handle.addEventListener("lostpointercapture", lost);
  window.addEventListener("blur", abort);      // the window lost focus (alt-tab) mid-drag: the release may never reach the page, so the drag ends here and drops nothing
  document.addEventListener("keydown", cancel, true);      // capture: before the handle's own key handler sees it
  document.addEventListener("pointermove", move);      // on the document, not the grip: the preview draws the section as a slot and the grip in it is hidden, so the grip no longer gets the pointer
  document.addEventListener("pointerup", end);
  document.addEventListener("pointercancel", end);
}
