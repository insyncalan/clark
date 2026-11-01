// Single-key shortcuts (#193): the letter keys V, E and the rest do nothing when this is off. On by default; remembered in the
// browser on this computer, like the section style (no database change). Read live: no reload.
import { signal } from "@preact/signals";

const KEY = "clark.single-keys";

function remembered() {
  try { return localStorage.getItem(KEY) !== "off"; } catch (e) { return true; }
}

export const singleKeys = signal(remembered());

/** Turn the single-key shortcuts on or off. It applies at once and is remembered. */
export function setSingleKeys(on) {
  singleKeys.value = !!on;
  try { localStorage.setItem(KEY, on ? "on" : "off"); } catch (e) { /* a private window: it applies now, and is not remembered */ }
}
