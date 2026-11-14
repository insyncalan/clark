// Item 1177: View | Edit as a floating icon pill (#mode-pill), fixed just under the sticky header on the right, the Dashboard's alone (ReportBar.jsx draws it).
// Eye is View, pencil is Edit; each button has its word as a tooltip and nothing else as text. Switching changes what is drawn and nothing else, as the V and E
// keys do (keys.js). It is half see-through at rest and solid on hover and focus; shell.css hides it in the full-screen board, under a dialog and while the profile menu is open.
import { mode, data } from "../stores/report.js";
import { singleKeys } from "../stores/keyPrefs.js";

export function ModePill() {
  if (!data.value) return null;
  const editing = mode.value === "edit";
  return (
    <span class="modes" id="mode-pill" role="group" aria-label="View or Edit mode">
      <button type="button" class="mode" data-mode="view" title="View" aria-keyshortcuts={singleKeys.value ? "V" : undefined} aria-pressed={editing ? "false" : "true"} onClick={() => { mode.value = "view"; }}>
        <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 10s3-5.5 8-5.5S18 10 18 10s-3 5.5-8 5.5S2 10 2 10z" /><circle cx="10" cy="10" r="2.4" /></svg>
      </button>
      <button type="button" class="mode" data-mode="edit" title="Edit" aria-keyshortcuts={singleKeys.value ? "E" : undefined} aria-pressed={editing ? "true" : "false"} onClick={() => { mode.value = "edit"; }}>
        <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M13.5 3.5l3 3L7 16H4v-3z" /></svg>
      </button>
    </span>
  );
}
