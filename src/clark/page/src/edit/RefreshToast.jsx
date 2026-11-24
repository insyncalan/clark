// Row 1046 (approved mock-up 1046-alerts): the Informed "Database refreshed" toast. Its own slot, so a change toast can never replace it (and it never
// replaces one); a database icon, the lead "Database refreshed", a teal edge, no Undo, 8 seconds counted only while nothing holds it (pointer or focus), and Close.
import { signal } from "@preact/signals";
import { toastClock, holdOn } from "../stores/toastClock.js";
import { startHeld } from "./ToastCard.jsx";

export const REFRESH_MS = 8000;
export const refreshed = signal(false);
const clock = toastClock(() => { refreshed.value = false; }, REFRESH_MS);

/** The shared database was read again: say so (a second call starts the 8 seconds again). */
export function announceRefreshed() { refreshed.value = true; clock.start(); }
export function closeRefreshed() {
  const a = document.activeElement, m = document.getElementById("main");
  if (a && a.closest && a.closest(".toast") && m) m.focus({ preventScroll: true });   // focus on the message would drop to the page's top
  clock.stop(); refreshed.value = false;
}

const Icon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><ellipse cx="8" cy="4" rx="5.5" ry="2" /><path d="M2.5 4v8c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2V4M2.5 8c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2" /></svg>
);

export function RefreshToast() {
  if (!refreshed.value) return null;
  return (
    <div class="toast refresh" data-kind="refresh" role="status" aria-live="polite" ref={startHeld(clock)} {...holdOn(clock)}>
      <span class="toast-text refresh-lead"><Icon />Database refreshed</span>
      <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={closeRefreshed}>Close</button>
      <span class="toast-bar" aria-hidden="true" style={`--dur-toast:${REFRESH_MS}ms`} />
    </div>
  );
}
