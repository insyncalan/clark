// The first time a browser enters Edit (once, A-D2, prototype views.js:530 idea 8): the first section's grip and plus pulse once.
// `pulse` is true from entering Edit until the animation ends (or a short time passes, in case it never runs). Nothing is kept
// here: ReportBar.jsx decides it is the first time (the drag hint's own memory) and calls begin().
import { signal } from "@preact/signals";

export const pulse = signal(false);
let timer = 0;

export const reduced = () => { try { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (e) { return false; } };

export function begin() {
  if (reduced()) return;
  pulse.value = true;
  clearTimeout(timer);
  timer = setTimeout(end, 1500);
}

export function end() {
  clearTimeout(timer);
  pulse.value = false;
}
