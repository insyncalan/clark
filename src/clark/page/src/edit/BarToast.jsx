// The one message View shows: what the report bar's Week ending field just did (it saves from View too). Every other message
// belongs to Edit (Toast.jsx) and is not drawn in View; it is kept, so it is there again, with its Undo, when Edit is entered again.
// This sits inside the profile menu's live region (ProfileMenu.jsx), which View always has, so a screen reader hears it.
import { signal } from "@preact/signals";
import { toast, dismiss, undo } from "../stores/changes.js";

const mine = signal(0);                     // the id of the toast that came from the bar; the toast itself is the changes store's

export function ownToast() { mine.value = toast.value ? toast.value.id : 0; }

export function BarToast() {
  const t = toast.value;
  if (!t || t.id !== mine.value) return null;
  return (
    <div class={`toast ${t.kind}`} key={t.id} data-kind={t.kind} role={t.kind === "problem" ? "alert" : undefined}>
      <span class="toast-text">{t.text}</span>
      {t.undo ? <button type="button" class="toast-btn" data-undo onClick={() => { dismiss(); undo(t.undo, t.code); }}>Undo</button> : null}
      <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={dismiss}>Close</button>
    </div>
  );
}
