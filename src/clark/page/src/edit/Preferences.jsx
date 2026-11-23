// Settings › Backups › the preferences card (row 1535, step 5): says the person's choices are kept with their data, and "Reset all preferences" takes every kept
// choice away (the file in the data folder and the browser's copy) and nothing else: no project row is touched. The first press asks (the button then reads as the
// one that confirms, beside Cancel); the second does it and the page reloads with the defaults. Edit parts only (a published file has no Settings).
import { useState } from "preact/hooks";
import { resetAll } from "../stores/prefsSync.js";

export const KEPT_LINE = "Your preferences are kept with your data";
export const RESET_LABEL = "Reset all preferences";
const CANCEL = "Cancel";

export function Preferences({ reset = resetAll, reload = () => window.location.reload() }) {
  const [asking, setAsking] = useState(false);
  const [failed, setFailed] = useState(false);
  async function go() {
    if (!asking) { setAsking(true); return; }
    const done = await reset();
    if (done) reload(); else { setFailed(true); setAsking(false); }
  }
  return (
    <section class="frame setting" id="preferences">
      <h2 id="preferences-h" tabIndex={-1}>Preferences</h2>
      <p id="preferences-kept">{KEPT_LINE}</p>
      <div class="row">
        <button type="button" class="btn" id="preferences-reset" data-preferences-reset aria-pressed={asking ? "true" : "false"} onClick={go}>{RESET_LABEL}</button>
        {asking ? <button type="button" class="btn" id="preferences-cancel" data-preferences-cancel onClick={() => setAsking(false)}>{CANCEL}</button> : null}
      </div>
      {failed ? <p class="error" role="alert" id="preferences-failed">Nothing was changed.</p> : null}
    </section>
  );
}
