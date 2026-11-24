// The peek's exit motion (#450 row 66; prototype app.css:416-18): when the peek closes it slides out to the right in
// var(--dur-instant) with var(--ease-exit), instead of vanishing. The live panel is already gone from the page by then, so a
// copy of it (no id, inert, hidden from reading aids) is the thing that slides, and it removes itself when the motion ends.
// Nothing here changes what is on the page once it has ended; under reduced motion no copy is made at all.
export function slideOut(el) {
  if (!el || !el.isConnected || !el.parentNode || typeof el.cloneNode !== "function") return null;
  try { if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return null; } catch (e) { /* no media query: slide */ }
  const copy = el.cloneNode(true);
  copy.removeAttribute("id");
  copy.removeAttribute("data-peek");
  copy.setAttribute("aria-hidden", "true");
  copy.setAttribute("inert", "");
  copy.classList.add("leaving");
  for (const n of copy.querySelectorAll("[id]")) n.removeAttribute("id");
  document.body.appendChild(copy);
  const done = () => { if (copy.parentNode) copy.parentNode.removeChild(copy); };
  copy.addEventListener("animationend", done);
  setTimeout(done, 400);                                  // safety: never left behind if the event does not come
  return copy;
}
