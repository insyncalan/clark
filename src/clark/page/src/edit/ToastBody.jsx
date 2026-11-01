// One toast: its words, Undo and Close. Toast.jsx (Edit) and the profile menu's live region (View, ProfileMenu.jsx) both draw it.
import { toast, dismiss, undo } from "../stores/changes.js";

// The toast itself. In View only a Settings toast (saySettings) is drawn, by the profile menu's own live region (ProfileMenu.jsx).
export function ToastBody({ viewOnly }) {
  const t = toast.value;
  if (!t || (viewOnly && !t.settings)) return null;
  return (
    <div class={`toast ${t.kind}`} key={t.id} data-kind={t.kind} role={t.kind === "problem" ? "alert" : undefined}>
      <span class="toast-text">{t.text}</span>
      {t.undo ? <button type="button" class="toast-btn" data-undo onClick={() => { dismiss(); undo(t.undo, t.code); }}>Undo</button> : null}
      {t.back ? <button type="button" class="toast-btn" data-undo onClick={() => { dismiss(); t.back(); }}>Undo</button> : null}
      <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={dismiss}>Close</button>
    </div>
  );
}
