// The generic part of a drag, with no DOM (#68; #95's drag.js can adopt it): a pointer goes down, and only after it has moved
// `threshold` pixels does it become a drag (so a click stays a click). The caller feeds it pointer positions and gets the
// callbacks; the page binds pointer events to down, move, up and cancel.
export function createDrag({ threshold = 4, onStart = () => {}, onMove = () => {}, onDrop = () => {}, onCancel = () => {} } = {}) {
  let from = null, dragging = false;
  return {
    down(x, y, data) { from = { x, y, data }; dragging = false; },
    move(x, y) {
      if (!from) return false;
      if (!dragging) {
        if (Math.hypot(x - from.x, y - from.y) < threshold) return false;
        dragging = true;
        onStart(from.data, from);
      }
      onMove({ x, y, data: from.data });
      return true;
    },
    // true when it was a drag (the click that follows must be ignored); false for a plain click
    up(x, y) {
      const was = dragging, data = from && from.data;
      from = null; dragging = false;
      if (was) { onDrop({ x, y, data }); }
      return was;
    },
    cancel() { const was = dragging; from = null; dragging = false; if (was) onCancel(); return was; },
    get dragging() { return dragging; },
  };
}
