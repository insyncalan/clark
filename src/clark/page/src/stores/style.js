// The section style (#45, Settings › Personal): how the Dashboard's sections are spaced and headed. One setting for this person on
// this computer, remembered in the browser (never in the project's data), applied at once as an attribute on the page. A published
// file carries the style it was published with (openPublished) and has no way to change it.
import { signal } from "@preact/signals";

export const IDS = ["slim", "roomy", "grey", "card"];
const KEY = "clark.section-style";
export const DEFAULT_STYLE = "slim";
export const valid = (v) => IDS.includes(v);

function remembered() {
  try { const v = localStorage.getItem(KEY); return valid(v) ? v : DEFAULT_STYLE; } catch (e) { return DEFAULT_STYLE; }
}

export const style = signal(remembered());

function paint(v) {
  try { document.documentElement.dataset.secstyle = v; } catch (e) { /* no document: nothing to paint */ }
}
paint(style.value);

/** Choose a style (Settings › Personal): it applies at once and is remembered. Anything else is ignored. */
export function setStyle(v) {
  if (!valid(v)) return;
  style.value = v;
  paint(v);
  try { localStorage.setItem(KEY, v); } catch (e) { /* a private window: it applies now, and is not remembered */ }
}

/** A published file's own style (set once, never remembered). */
export function useFileStyle(v) {
  const s = valid(v) ? v : DEFAULT_STYLE;
  style.value = s;
  paint(s);
}
