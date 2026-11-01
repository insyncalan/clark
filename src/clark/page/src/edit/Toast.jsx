// What the last change did, with Undo while there is a step to undo (on the Dashboard in Edit only; every other page always has it). The wrapper is always there then, so a
// screen reader hears each new message; an error stays until it is dismissed or the next change. The profile menu's note (what
// Preview or Export did) is shown in this same region, so the page has one live region (#147); on the Dashboard in View the profile
// menu draws the only one.
import { useEffect } from "preact/hooks";
import { mode, view } from "../stores/report.js";
import { toast, dismiss, undo } from "../stores/changes.js";
import { MenuNote } from "./ProfileMenu.jsx";
import { undoKey } from "./undoKey.js";

export function Toast() {
  useEffect(() => {                                   // #197: Cmd or Ctrl+Z undoes the last change (undoKey.js)
    document.addEventListener("keydown", undoKey);
    return () => document.removeEventListener("keydown", undoKey);
  }, []);
  const editing = mode.value === "edit";
  const full = editing || view.value !== "dashboard";               // View and Edit exist only on the Dashboard: the other pages always show it (ruled 02-11-2026)
  useEffect(() => { if (!editing) dismiss(); }, [editing]);       // a message from Edit does not follow the person into View
  const t = toast.value;
  if (!full && !t) return null;                       // the Dashboard in View has no toast of its own; it shows one only for the report bar's Week ending field (A-D2), which saves from View too
  return (
    <div class="toasts" data-edit-only={full ? true : undefined} role="status" aria-live="polite">
      {t ? (
        <div class={`toast ${t.kind}`} key={t.id} data-kind={t.kind} role={t.kind === "problem" ? "alert" : undefined}>
          <span class="toast-text">{t.text}</span>
          {t.undo ? <button type="button" class="toast-btn" data-undo onClick={() => { dismiss(); undo(t.undo, t.code); }}>Undo</button> : null}
          <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={dismiss}>Close</button>
        </div>
      ) : null}
      {full ? <MenuNote /> : null}
    </div>
  );
}
