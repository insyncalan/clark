// One change toast: its words, Undo while there is something to undo, and Close. A toast may carry its own Undo, `local` (a function: a save
// that is not in the change log, such as About you), which the button calls instead of the change history's. Toast.jsx shows it in Edit;
// the profile menu's region shows About you's own toasts (`own`) in View too (Settings opens in View, #429), and they go as in Edit: after 5 seconds, on Close, and when Settings is left.
import { dismiss, undo, toastTimer } from "../stores/changes.js";
import { holdOn, TOAST_MS } from "../stores/toastClock.js";

// Row 1075: the bar under a message that goes by itself. It shrinks over the 5 seconds (CSS, and only where motion is allowed: with Reduce motion it is not shown),
// and stands still while the pointer is over the message or focus is in it, as the clock does. A problem stays until Close, so it has no bar.
export const ToastBar = ({ kind }) => kind === "problem" ? null : <span class="toast-bar" aria-hidden="true" style={`--dur-toast:${TOAST_MS}ms`} />;

/** Holds `clock` at once if the pointer is already over the message when it appears (no pointerenter comes then). */
export const startHeld = (clock) => (el) => { if (el && el.matches && el.matches(":hover")) clock.hold("pointer"); };

export function ToastCard({ t }) {
  return (
    <div class={`toast ${t.kind}`} key={t.id} data-kind={t.kind} role={t.kind === "problem" ? "alert" : undefined} ref={startHeld(toastTimer)} {...holdOn(toastTimer)}>
      <span class="toast-text">{t.text}</span>
      {t.undo || t.local ? <button type="button" class="toast-btn" data-undo onClick={() => { dismiss(); if (t.local) t.local(); else undo(t.undo, t.code); }}>Undo</button> : null}
      <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={dismiss}>Close</button>
      <ToastBar kind={t.kind} />
    </div>
  );
}
