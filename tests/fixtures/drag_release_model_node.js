// Row 1277: a node model of the release in startDrag (edit/drag.js): move() -> aim() -> settle(), the REST_MS timer (arm/restLeft),
// and end() dropping on state.shown (drag.js:178) WITHOUT a last aim(). It uses the page's own settle, restLeft and dragTarget, so
// only the timer plumbing is copied; a fake clock replaces setTimeout and performance.now().
import { dragTarget, freezeRects, settle, settleStart, restLeft, REST_MS } from "@src/logic/dragLayout.js";

export { REST_MS };

// moves: [{ at, x, y }] in ms; release: ms of the pointerup. Returns { shown, want, log } as end() sees them at the release.
export function model({ sections, id, rects, moves, release, columns = 2 }) {
  const start = freezeRects(rects);
  let state = settleStart(), timer = null, ptr = null, now = 0;
  const log = [];
  const aim = () => {
    state = settle(state, dragTarget(sections, id, start, ptr, { columns }), now);
    if (state.moved) log.push({ at: now, shown: state.shown });
  };
  const arm = (ms) => { timer = now + ms; };
  const fire = () => { timer = null; aim(); const left = restLeft(state, now); if (left > 0) arm(left); };
  const run = (until) => { while (timer !== null && timer <= until) { now = timer; fire(); } };
  for (const m of moves) {
    run(m.at);                                   // a timer due before this move fires first
    now = m.at;
    ptr = { x: m.x, y: m.y };
    aim();
    timer = null;                                // clear()
    arm(REST_MS);
  }
  run(release);
  now = release;
  return { shown: state.shown, want: state.want, log };    // end(): const target = state.shown
}
