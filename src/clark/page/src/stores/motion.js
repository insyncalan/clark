// Motion: one place that says whether the page may move, and the small helpers the motions share. The page may move only when
// the computer has not asked for reduced motion (CSS `prefers-reduced-motion`) and clark's own setting is not "reduce"
// (`<html data-motion="reduce">`; the Settings screen will set it). The CSS does the same sums in one block
// (shell.css, "Motion"), so a motion is simply absent when either is on, never switched off after the fact.
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";

/** True when nothing may move. */
export function reduced() {
  if (typeof document === "undefined") return true;
  if (document.documentElement.dataset.motion === "reduce") return true;
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** The screen whose loading placeholder was drawn, kept until it has faded out (Views.jsx Leaving); null otherwise. */
export const skeleton = signal(null);

/** When `value` changes after the first draw, give `ref`'s element the class `settle` for one run of its animation (a one-shot
 *  opacity settle). The class goes again when the animation ends. Nothing happens when the page may not move. */
export function useSettle(ref, value) {
  const prev = useRef(value);
  useEffect(() => {
    const el = ref.current;
    if (prev.current !== value && el && !reduced()) {
      el.classList.remove("settle");
      void el.offsetWidth;                                  // restart the animation if it was still running
      el.classList.add("settle");
    }
    prev.current = value;
  }, [value]);
}

/** The first-time hint on the section handle: the id of the section whose handle pulses once and shows the words, or null. It is
 *  shown once in this browser (remembered in localStorage when it can be) for a few seconds, and goes at the next press or key. */
export const handleHint = signal(null);
export const HINT_WORDS = "Drag to move, + to add a template";
export const HINT_MS = 4000;
const KEY = "clark.handleHint";
let hintTimer = 0, hintListening = false, armed = false;

function endHint() {
  clearTimeout(hintTimer);
  handleHint.value = null;
  if (hintListening) { hintListening = false; document.removeEventListener("pointerdown", endHint, true); document.removeEventListener("keydown", endHint, true); }
}

/** Offer the hint on this section's handle, the first time only. */
export function armHint(id) {
  if (handleHint.value || typeof document === "undefined") return;
  try { if (localStorage.getItem(KEY)) return; localStorage.setItem(KEY, "1"); } catch (e) { /* no storage: it shows once per page load */ if (armed) return; }
  armed = true;
  handleHint.value = id;
  hintTimer = setTimeout(endHint, HINT_MS);
  hintListening = true;
  document.addEventListener("pointerdown", endHint, true);
  document.addEventListener("keydown", endHint, true);
}
