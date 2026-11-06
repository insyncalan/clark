// Row 878, the exit: a menu that closes fades out in var(--dur-instant) (the nearest of the motion tokens to 160 ms), opacity only, with var(--ease-exit).
// The live menu is already gone from the page when it starts (focus, aria-expanded and the keys all see it closed at once); what fades is a copy of it,
// drawn on the window where the menu was, with no class, role or id left on it (so nothing that looks for a menu finds it), inert, hidden from reading aids and
// taking no pointer. The copy sets no state anywhere: it removes itself when the fade ends (or after a safety wait), and a menu of the same name opening
// again, or the page leaving, removes it at once. Under reduced motion (the system setting or data-motion=reduce) no copy is made: the menu just closes.
import { useCallback, useLayoutEffect, useRef } from "preact/hooks";

const live = new Set();                                  // the copies still fading: { node, key, timer }
const FADE_MS = 400;                                      // safety only: the animation itself is the token's 120 ms

const still = () => {
  if (document.documentElement.dataset.motion === "reduce") return true;
  try { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (e) { return false; }
};
const keyOf = (el) => el.getAttribute("aria-label") || el.className || "menu";

function drop(g) {
  clearTimeout(g.timer);
  if (g.node.parentNode) g.node.parentNode.removeChild(g.node);
  live.delete(g);
}

// A menu of this name is open again: its older copy goes at once, so the two never overlap.
export function fadeCancel(el) {
  if (!el) return;
  const k = keyOf(el);
  for (const g of [...live]) if (g.key === k) drop(g);
}

// Call as the menu `el` is removed (it is still on the page at that moment).
export function fadeOut(el) {
  if (!el || !el.isConnected || typeof el.cloneNode !== "function" || still()) return null;
  const r = el.getBoundingClientRect();
  if (!r.width || !r.height) return null;
  const copy = el.cloneNode(true), src = [el, ...el.querySelectorAll("*")], dst = [copy, ...copy.querySelectorAll("*")];
  const key = keyOf(el);
  src.forEach((s, i) => {                                 // the look is carried by value, so it does not depend on the classes taken off below
    const d = dst[i], cs = getComputedStyle(s);
    if (!d || !d.style) return;
    for (let j = 0; j < cs.length; j++) d.style.setProperty(cs[j], cs.getPropertyValue(cs[j]));
    d.removeAttribute("class"); d.removeAttribute("id"); d.removeAttribute("role"); d.removeAttribute("aria-label"); d.removeAttribute("tabindex");
    for (const a of [...d.attributes]) if (a.name.startsWith("data-") || a.name.startsWith("aria-")) d.removeAttribute(a.name);
  });
  const s = copy.style;
  s.position = "fixed"; s.left = r.left + "px"; s.top = r.top + "px"; s.right = "auto"; s.bottom = "auto"; s.width = r.width + "px"; s.height = r.height + "px";
  s.margin = "0"; s.transform = "none"; s.translate = "none"; s.pointerEvents = "none"; s.transition = "none";
  s.animation = "m-out var(--dur-instant) var(--ease-exit) forwards";
  copy.setAttribute("aria-hidden", "true"); copy.setAttribute("inert", ""); copy.setAttribute("data-fade", "1");
  document.body.appendChild(copy);
  const g = { node: copy, key, timer: 0 };
  live.add(g);
  copy.addEventListener("animationend", () => drop(g));
  g.timer = setTimeout(() => drop(g), FADE_MS);
  return copy;
}

// For a component that is the menu: `useFadeOut(boxRef)` fades the box as the component goes.
export function useFadeOut(box) {
  useLayoutEffect(() => { fadeCancel(box.current); return () => fadeOut(box.current); }, []);      // eslint-disable-line react-hooks/exhaustive-deps
}

// For a menu drawn inside a component that stays: a stable ref callback for the menu's element, which fades it as it is removed.
export function useFadeRef(into) {
  const last = useRef(null);
  return useCallback((n) => {
    if (into) into.current = n;
    if (n) { last.current = n; fadeCancel(n); } else { fadeOut(last.current); last.current = null; }
  }, []);                                                // eslint-disable-line react-hooks/exhaustive-deps
}
