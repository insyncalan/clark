// One change toast: its words, Undo while there is something to undo, and Close. A toast may carry its own Undo, `local` (a function: a save
// that is not in the change log, such as About you), which the button calls instead of the change history's. Toast.jsx shows it in Edit;
// the profile menu's region shows one that carries a local Undo in View too (Settings opens in View, #429).
import { dismiss, undo } from "../stores/changes.js";

export function ToastCard({ t }) {
  return (
    <div class={`toast ${t.kind}`} key={t.id} data-kind={t.kind} role={t.kind === "problem" ? "alert" : undefined}>
      <span class="toast-text">{t.text}</span>
      {t.undo || t.local ? <button type="button" class="toast-btn" data-undo onClick={() => { dismiss(); if (t.local) t.local(); else undo(t.undo, t.code); }}>Undo</button> : null}
      <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={dismiss}>Close</button>
    </div>
  );
}
