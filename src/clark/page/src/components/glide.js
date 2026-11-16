// Row 1214: while a section is dragged and the others make room, each section that changed place glides from where it was to where
// it is now (about 160 ms, the same as --dur-glide in shell.css). noteRects() is called just before the page changes, glide() just after
// it is drawn. When motion is reduced nothing glides: the sections are simply in their new place.
import { reduced } from "../stores/motion.js";

const GLIDE_MS = 160;
let before = null;

function measure(root) {
  const out = {};
  if (root) for (const el of root.querySelectorAll(":scope > .sec[data-id]")) { const r = el.getBoundingClientRect(); out[el.dataset.id] = { left: r.left, top: r.top }; }
  return out;
}

export function noteRects() { before = measure(document.querySelector(".secs")); }

export function glide(root) {
  const was = before;
  before = null;
  if (!was || !root || reduced()) return;
  for (const el of root.querySelectorAll(":scope > .sec[data-id]")) {
    const a = was[el.dataset.id];
    if (!a || !el.animate) continue;
    const r = el.getBoundingClientRect();
    const dx = a.left - r.left, dy = a.top - r.top;
    if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
    el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], { duration: GLIDE_MS, easing: "ease-out" });
  }
}
