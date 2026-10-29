// What the last change did, with Undo while there is a step to undo (Edit only). The wrapper is always there in Edit, so a
// screen reader hears each new message; an error stays until it is dismissed or the next change.
import { mode } from "../stores/report.js";
import { toast, dismiss, undo } from "../stores/changes.js";

export function Toast() {
  if (mode.value !== "edit") return null;
  const t = toast.value;
  return (
    <div class="toasts" data-edit-only role="status" aria-live="polite">
      {t ? (
        <div class={`toast ${t.kind}`} key={t.id} data-kind={t.kind} role={t.kind === "problem" ? "alert" : undefined}>
          <span class="toast-text">{t.text}</span>
          {t.undo ? <button type="button" class="toast-btn" data-undo onClick={() => { dismiss(); undo(t.undo); }}>Undo</button> : null}
          <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={dismiss}>Close</button>
        </div>
      ) : null}
    </div>
  );
}
