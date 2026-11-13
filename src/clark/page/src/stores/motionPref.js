// The Motion switch (row 1115, Settings › Essentials): clark's own choice to let the page move or not. Until it is chosen, the switch follows the
// computer's reduced-motion setting (Off when the computer asks for reduced motion, otherwise On). Off sets `data-motion="reduce"`
// on the page at once, which stores/motion.js and the CSS already answer. Remembered in the browser on this computer, like the single-key shortcuts.
// A choice made with the switch is remembered and wins; the computer's reduced-motion setting only sets the default until then. Only Edit's parts import this file (edit/index.js, so the choice is applied at load).
import { signal } from "@preact/signals";

const KEY = "clark.motion";

function systemReduces() {
  try { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (e) { return false; }
}

function remembered() {
  let v = null;
  try { v = localStorage.getItem(KEY); } catch (e) { /* not remembered: follow the computer */ }
  if (v === "on") return true;
  if (v === "off") return false;
  return !systemReduces();
}

export const motionOn = signal(remembered());

function paint(on) {
  try { if (on) delete document.documentElement.dataset.motion; else document.documentElement.dataset.motion = "reduce"; } catch (e) { /* no document: nothing to paint */ }
}
if (!motionOn.value) paint(false);      // at load only a remembered Off is painted: nothing else that set the attribute (a test, a host) is undone

/** Turn clark's own motion on or off: it applies at once and is remembered. */
export function setMotion(on) {
  motionOn.value = !!on;
  paint(!!on);
  try { localStorage.setItem(KEY, on ? "on" : "off"); } catch (e) { /* a private window: it applies now, and is not remembered */ }
}
