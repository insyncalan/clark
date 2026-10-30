// Settings: asking (#47). The on/off switch is one saved choice, "clark.askEnabled", in this browser's own storage beside the
// page's other small choices (never the database, so nothing here is a guarded change). On unless it was turned off. The panel's
// status-line link reads and changes this same choice through setAsk(), so there is one switch whichever place changes it.
// Storage can be blocked (a private window): then the choice lasts until the page is reloaded.
import { signal } from "@preact/signals";

const KEY = "clark.askEnabled";

function stored() {
  try { return window.localStorage.getItem(KEY) !== "off"; } catch (e) { return true; }
}

export const askOn = signal(stored());

export function setAsk(on) {
  askOn.value = !!on;
  try { window.localStorage.setItem(KEY, on ? "on" : "off"); } catch (e) { /* the choice lasts until reload */ }
}

// What the page says to the owner while asking is off (one place, so every place that shows the off state says the same).
export const ASK_OFF_LINE = "Asking is off. Turn it on in Settings.";
