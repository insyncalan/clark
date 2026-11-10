// How long a message stays (row 1075): 5 seconds, counted only while nothing holds it. The pointer over the message and focus inside it
// each hold the count (the bar stops with it, in CSS); when the last hold is let go the rest of the time runs. Used by the change toast
// (changes.js) and the profile menu's note (menuNote.js). The bar itself is drawn by edit/ToastCard.jsx and edit/ProfileMenu.jsx.
export const TOAST_MS = 5000;

export function toastClock(onEnd) {
  let handle = 0, left = 0, since = 0, running = false;
  const holds = new Set();
  const run = () => { since = performance.now(); running = true; handle = setTimeout(() => { running = false; onEnd(); }, left); };
  return {
    start() { clearTimeout(handle); holds.clear(); running = false; left = TOAST_MS; run(); },
    stop() { clearTimeout(handle); holds.clear(); running = false; left = 0; },
    hold(why) {
      if (holds.has(why)) return;
      holds.add(why);
      if (running) { clearTimeout(handle); running = false; left = Math.max(0, left - (performance.now() - since)); }
    },
    release(why) {
      if (!holds.delete(why) || holds.size || running || left <= 0) return;
      run();
    },
  };
}

/** The handlers that hold a clock while the pointer is over a message or focus is in it. */
export function holdOn(clock) {
  return {
    onPointerEnter: () => clock.hold("pointer"), onPointerLeave: () => clock.release("pointer"),
    onfocusin: () => clock.hold("focus"), onfocusout: () => clock.release("focus"),
  };
}
