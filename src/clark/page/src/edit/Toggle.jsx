// View or Edit, in the top bar (on the Dashboard, a pill at the left of the report bar: ReportBar draws it, TopBar then does not).
// Only a page that clark serves has it: a published file has no Edit button. Switching changes
// what is drawn and nothing else: no reload, no address change, no history entry, nothing saved. On the Dashboard the plain keys V
// and E do the same (keys.js, listened for from boot, so the key works whichever bar draws the switch).
import { mode, data } from "../stores/report.js";
import { singleKeys } from "../stores/keyPrefs.js";

export function Toggle({ pill }) {      // pill: the Dashboard's, drawn at the left of the report bar (#665); otherwise the top bar's
  if (!data.value) return null;       // row 826: Settings has no switch, with a project or without (Add project needs no mode)
  const editing = mode.value === "edit";
  return (
    <span class={pill ? "modes seg" : "modes"} role="group" aria-label="View or Edit">
      <button type="button" class="mode" data-mode="view" title={singleKeys.value ? "View (V)" : "View"} aria-keyshortcuts={singleKeys.value ? "V" : undefined} aria-pressed={editing ? "false" : "true"} onClick={() => { mode.value = "view"; }}>View</button>
      <button type="button" class="mode" data-mode="edit" title={singleKeys.value ? "Edit (E)" : "Edit"} aria-keyshortcuts={singleKeys.value ? "E" : undefined} aria-pressed={editing ? "true" : "false"} onClick={() => { mode.value = "edit"; }}>{pill ? <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M13.5 3.5l3 3L7 16H4v-3z" /></svg> : null}Edit</button>
    </span>
  );
}
