// View or Edit, in the top bar (on the Dashboard, a pill at the left of the report bar: ReportBar draws it, TopBar then does not). Only a page that clark serves has it: a published file has no Edit button. Switching changes
// what is drawn and nothing else: no reload, no address change, no history entry, nothing saved. On the Dashboard the plain keys V
// and E do the same (keys.js).
import { useEffect } from "preact/hooks";
import { mode, data, status, view } from "../stores/report.js";
import { modeKey } from "./keys.js";
import { singleKeys } from "../stores/keyPrefs.js";

export function Toggle({ pill }) {      // pill: the Dashboard's, drawn at the left of the report bar (#665); otherwise the top bar's
  useEffect(() => {
    document.addEventListener("keydown", modeKey);
    return () => document.removeEventListener("keydown", modeKey);
  }, []);
  if (!data.value && !(status.value === "none" && view.value === "settings")) return null;       // #656: with no project Settings has its Edit, for Add project
  const editing = mode.value === "edit";
  return (
    <span class={pill ? "modes seg" : "modes"} role="group" aria-label="View or Edit">
      <button type="button" class="mode" data-mode="view" title={singleKeys.value ? "View (V)" : "View"} aria-keyshortcuts={singleKeys.value ? "V" : undefined} aria-pressed={editing ? "false" : "true"} onClick={() => { mode.value = "view"; }}>View</button>
      <button type="button" class="mode" data-mode="edit" title={singleKeys.value ? "Edit (E)" : "Edit"} aria-keyshortcuts={singleKeys.value ? "E" : undefined} aria-pressed={editing ? "true" : "false"} onClick={() => { mode.value = "edit"; }}>Edit</button>
    </span>
  );
}
