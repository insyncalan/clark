// One change toast: its words, Undo (a server step, or `back` for a change clark keeps outside the step list, #440) and Close.
import { dismiss, undo } from "../stores/changes.js";

export function ToastBox({ t }) {
  return (
    <div class={`toast ${t.kind}`} data-kind={t.kind} role={t.kind === "problem" ? "alert" : undefined}>
      <span class="toast-text">{t.text}</span>
      {t.back ? <button type="button" class="toast-btn" data-undo onClick={() => { const b = t.back; dismiss(); b(); }}>Undo</button> : null}
      {t.undo ? <button type="button" class="toast-btn" data-undo onClick={() => { dismiss(); undo(t.undo, t.code); }}>Undo</button> : null}
      <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={dismiss}>Close</button>
    </div>
  );
}
