// What the last change did, with Undo while there is a step to undo (on the Dashboard in Edit only; every other page always has it). A toast may carry its own Undo, `local` (a function:
// a save that is not in the change log, such as About you), which the button calls instead of the change history's. The wrapper is always there then, so a
// screen reader hears each new message; an error stays until it is dismissed or the next change. The profile menu's note (what
// Preview or Export did) is shown in this same region, so the page has one live region (#147); on the Dashboard in View the profile
// menu draws the only one.
import { useEffect } from "preact/hooks";
import { mode, view } from "../stores/report.js";
import { toast } from "../stores/changes.js";
import { MenuNote } from "./ProfileMenu.jsx";
import { undoKey } from "./undoKey.js";
import { ToastCard } from "./ToastCard.jsx";

export function Toast() {
  useEffect(() => {                                   // #197: Cmd or Ctrl+Z undoes the last change (undoKey.js)
    document.addEventListener("keydown", undoKey);
    return () => document.removeEventListener("keydown", undoKey);
  }, []);
  if (mode.value !== "edit" && view.value === "dashboard") return null;      // View and Edit exist only on the Dashboard: the other pages always show it (ruled 02-11-2026)
  const t = toast.value;
  return (
    <div class="toasts" data-edit-only role="status" aria-live="polite">
      {t ? (
        <ToastCard t={t} />
      ) : null}
      <MenuNote />
    </div>
  );
}
