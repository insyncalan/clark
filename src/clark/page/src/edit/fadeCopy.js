// Row 962: the copy that fades. A menu or popup that is taken off the page the moment its owner stops drawing it (RowMenu, the card's Move to, Gutter's options)
// is drawn again as a copy on the window where it was: no id, no data-* (but data-edit-only), role=presentation, inert and aria-hidden, class leaving, opacity only
// over --dur-instant (edit.css and shell.css), removed when the animation ends (a 400 ms timer guards it). `wrap` is a class for a box around the copy where the
// menu's styles need one (.rowmenu). Edit part only: it registers itself in fx (Menu.jsx), so the published page carries none of it. Nothing is drawn where motion is off.
import { fx } from "../components/Menu.jsx";

const stillMotion = () => document.documentElement.dataset.motion === "reduce" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

export function fadeCopy(el, wrap) {
  if (!el || !el.isConnected || stillMotion()) return;
  const r = el.getBoundingClientRect();
  if (!r.width || !r.height) return;
  const copy = el.cloneNode(true);
  for (const n of [copy, ...copy.querySelectorAll("*")]) {
    n.removeAttribute("id");
    for (const a of Array.from(n.attributes)) if (a.name.startsWith("data-") && a.name !== "data-edit-only") n.removeAttribute(a.name);
  }
  copy.setAttribute("role", "presentation"); copy.setAttribute("aria-hidden", "true"); copy.setAttribute("inert", ""); copy.removeAttribute("tabindex");
  copy.classList.add("leaving");
  let top = copy;
  if (wrap) { top = document.createElement("div"); top.className = wrap; top.appendChild(copy); }
  top.style.pointerEvents = "none"; top.style.position = "fixed"; top.style.left = `${Math.round(r.left)}px`; top.style.top = `${Math.round(r.top)}px`; top.style.margin = "0"; top.style.right = "auto";
  copy.style.width = `${Math.round(r.width)}px`; copy.style.height = `${Math.round(r.height)}px`; copy.style.boxSizing = "border-box";
  if (wrap) { copy.style.position = "static"; copy.style.maxHeight = "none"; } else copy.style.zIndex = getComputedStyle(el).zIndex;
  document.body.appendChild(top);
  const t = setTimeout(() => done(), 400);
  const done = () => { clearTimeout(t); if (top.parentNode) top.parentNode.removeChild(top); };
  if (getComputedStyle(copy).animationName === "none") { done(); return; }      // no rule fades this one here: nothing is left standing
  copy.addEventListener("animationend", (e) => { if (e.target === copy) done(); });
}
fx.copy = fadeCopy;
