// Row 1046: the message that only informs ("Database refreshed"), a toast kind of its own. It has its own place on the page and its own clock
// (8 seconds, held while the pointer is over it or focus is in it, as a change's message is), so a change's toast (stores/changes.js) never
// replaces it and it never replaces one. It has no Undo: nothing was changed by the person.
import { signal } from "@preact/signals";
import { toastClock, INFORMED_MS } from "./toastClock.js";

export const informed = signal(null);
let last = 0;
export const informedTimer = toastClock(() => { informed.value = null; }, INFORMED_MS);

/** Shows `text` (plain text) under its lead, replacing an earlier message of this kind, and starts the 8 seconds. */
export function sayInformed(text, lead = "Database refreshed") {
  informed.value = { id: ++last, lead: String(lead), text: String(text || "") };
  informedTimer.start();
}

export function dismissInformed() {
  informedTimer.stop();
  informed.value = null;
}
