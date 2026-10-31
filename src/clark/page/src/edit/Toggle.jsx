// View or Edit, in the top bar. Only a page that clark serves has it: a published file has no Edit button. Switching changes
// what is drawn and nothing else: no reload, no address change, no history entry, nothing saved. On the Dashboard the plain keys V
// and E do the same (keys.js).
import { useEffect } from "preact/hooks";
import { mode, data } from "../stores/report.js";
import { modeKey } from "./keys.js";

export function Toggle() {
  useEffect(() => {
    document.addEventListener("keydown", modeKey);
    return () => document.removeEventListener("keydown", modeKey);
  }, []);
  if (!data.value) return null;
  const editing = mode.value === "edit";
  return (
    <span class="modes" role="group" aria-label="View or Edit">
      <button type="button" class="mode" data-mode="view" title="View (V)" aria-keyshortcuts="V" aria-pressed={editing ? "false" : "true"} onClick={() => { mode.value = "view"; }}>View</button>
      <button type="button" class="mode" data-mode="edit" title="Edit (E)" aria-keyshortcuts="E" aria-pressed={editing ? "true" : "false"} onClick={() => { mode.value = "edit"; }}>Edit</button>
    </span>
  );
}
