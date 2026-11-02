// Which rows just changed: after a change or an undo, the rows whose data differs are marked, so a person can see what the
// last step did. The mark is a static tint, a bar on the left edge and the word "Changed", so it does not depend on colour or on
// motion and reads the same when the computer asks for reduced motion. It goes at the next click or key press, or after
// SHOW_MS (about 3 seconds, #131), whichever is first. The timer is held in `clock` so a test can swap it for one it winds by hand (useClock).
import { signal } from "@preact/signals";

export const SHOW_MS = 3000;
export const WORD = "Changed";

export const changed = signal([]);                  // the ids of the rows marked now

const real = { setTimeout: (f, ms) => setTimeout(f, ms), clearTimeout: (t) => clearTimeout(t) };
let clock = real, timer = null, listening = false;

/** Swap the timer (tests). Called with nothing, it puts the real one back. */
export function useClock(c) {
  if (timer !== null) clock.clearTimeout(timer);
  timer = null;
  clock = c || real;
}

/** The ids in `after` whose row is new or differs from its row in `before` (both are lists of rows with an `id`). Only the fields
 *  the `after` row carries are compared: a reply leaves out a field (a section's body) that the first read had. */
export function diffIds(before, after) {
  const was = new Map((before || []).map((r) => [r.id, r]));
  return (after || []).filter((r) => {
    const old = was.get(r.id);
    return !old || Object.keys(r).some((k) => JSON.stringify(r[k]) !== JSON.stringify(old[k]));
  }).map((r) => r.id);
}

export const isChanged = (id) => changed.value.indexOf(id) >= 0;

export function clearChanged() {
  if (timer !== null) clock.clearTimeout(timer);
  timer = null;
  if (changed.value.length) changed.value = [];
}

const MODIFIERS = ["Shift", "Control", "Alt", "Meta"];
function onAction(e) {
  if (e.type === "keydown" && MODIFIERS.indexOf(e.key) >= 0) return;       // holding a modifier is not an action
  clearChanged();
}

/** Mark these rows as changed, replacing the earlier marks. An empty list clears them. */
export function markChanged(ids) {
  clearChanged();
  if (!ids || !ids.length) return;
  changed.value = ids.slice();
  if (!listening && typeof document !== "undefined") {
    listening = true;
    document.addEventListener("pointerdown", onAction, true);
    document.addEventListener("keydown", onAction, true);
  }
  timer = clock.setTimeout(clearChanged, SHOW_MS);
}
