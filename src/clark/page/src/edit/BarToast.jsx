// A message made while the Dashboard is in View (item 439): what the report bar's Week ending field just did (it saves from View too).
// Every other message belongs to Edit (Toast.jsx) and is not drawn in View; it is kept, so it
// is there again, with its Undo, when Edit is entered again. This sits inside the profile menu's live region (ProfileMenu.jsx), which
// View always has, so a screen reader hears it. It is drawn as every toast is (ToastCard.jsx).
import { signal } from "@preact/signals";
import { toast } from "../stores/changes.js";
import { mode } from "../stores/report.js";
import { ToastCard } from "./ToastCard.jsx";

const mine = signal(0);                     // the id of the toast made in View; the toast itself is the changes store's

// In Edit the message is Edit's own (Toast.jsx); only one made while the page is in View is this one's.
export function ownToast() { mine.value = mode.value !== "edit" && toast.value ? toast.value.id : 0; }

export function BarToast() {
  const t = toast.value;
  if (!t || t.id !== mine.value) return null;
  return <ToastCard t={t} />;
}
