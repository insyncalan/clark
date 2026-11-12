// #80: the one panel a picker opens in, under the control that opened it (above it when there is no room below, and moved up
// to fit inside the window when there is room on neither side, so its last choice can always be reached). One panel only:
// no browser popup is ever stacked over it, so a single Esc closes it ("a single esc should close both calendar
// panels"; #91, #92). Esc closes it and leaves the value as it was, with focus back on the control; so does a click outside it.
// Tab closes it too, and focus carries on from the control. The key never reaches anything behind it (the peek's own Esc).
import { useLayoutEffect, useRef } from "preact/hooks";

// Row 962 (the pattern of row 922, Menu.jsx): a picker that closes is gone from the page at once, so a copy of it (no id, role="presentation", inert,
// aria-hidden, class leaving) fades out over --dur-instant (opacity only, edit.css) and removes itself when the animation ends; a 400 ms timer guards it.
// Under reduced motion (the computer's setting or <html data-motion="reduce">) no copy is made at all.
const stillMotion = () => document.documentElement.dataset.motion === "reduce" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
export function fadeOut(el) {
  if (!el || !el.isConnected || !el.parentNode || stillMotion()) return null;
  const copy = el.cloneNode(true);
  for (const n of [copy, ...copy.querySelectorAll("[id]")]) n.removeAttribute("id");
  for (const a of ["data-pop", "data-edit-only", "aria-label"]) copy.removeAttribute(a);
  copy.setAttribute("role", "presentation");
  copy.setAttribute("aria-hidden", "true");
  copy.setAttribute("inert", "");
  copy.removeAttribute("tabindex");
  copy.classList.add("leaving");
  document.body.appendChild(copy);
  const gone = () => { if (copy.parentNode) copy.parentNode.removeChild(copy); };
  copy.addEventListener("animationend", (e) => { if (e.target === copy && e.animationName === "m-out") gone(); });
  setTimeout(gone, 400);
  return copy;
}

export function Pop({ anchor, label, role = "dialog", cls = "", onClose, children }) {
  const box = useRef(null);
  const place = () => {
    const el = box.current, a = anchor && anchor.current;
    if (!el || !a) return;
    const r = a.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight;
    const left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
    let top = r.bottom + 4;
    if (top + h > window.innerHeight - 8 && r.top - h - 4 > 8) top = r.top - h - 4;
    top = Math.max(8, Math.min(top, window.innerHeight - h - 8));   // no room either side: it moves up just enough to be whole
    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(top)}px`;
  };
  useLayoutEffect(place, []);                             // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => () => { fadeOut(box.current); }, []);   // closing (any way) leaves the fading copy where the picker was
  // (it is drawn off screen first, not hidden, so the picker inside can take focus as it opens, before it is placed)
  useLayoutEffect(() => {                                 // at once, not after the next frame: a click that quick still closes it
    const away = (e) => {
      const el = box.current, a = anchor && anchor.current;
      if (el && !el.contains(e.target) && !(a && a.contains(e.target))) onClose(false);
    };
    const moved = (e) => { if (!box.current || !box.current.contains(e.target)) place(); };
    const resized = () => onClose(false);
    document.addEventListener("pointerdown", away, true);
    document.addEventListener("scroll", moved, true);
    window.addEventListener("resize", resized);
    return () => {
      document.removeEventListener("pointerdown", away, true);
      document.removeEventListener("scroll", moved, true);
      window.removeEventListener("resize", resized);
    };
  }, []);                                                 // eslint-disable-line react-hooks/exhaustive-deps
  const keys = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(true); }
    else if (e.key === "Tab") {
      onClose(true);
      // The panel sits right after its control in the page, and the redraw that removes it comes after this key: the browser's own Tab step would
      // then land on a choice inside the closing panel, and the panel's removal would leave focus on nothing. Inert, it is skipped at once.
      if (box.current) box.current.inert = true;
      // If the browser still leaves focus on nothing (a slow machine, the redraw landing late), carry on from the control by hand.
      const from = anchor && anchor.current, back = e.shiftKey;
      setTimeout(() => {
        const a = document.activeElement;
        if (!from || !from.isConnected || (a && a !== document.body) || document.querySelector("[data-pop]")) return;   // gone, settled, or another picker took over
        const all = [...document.querySelectorAll("a[href],button,input,select,textarea,[tabindex]")]
          .filter((n) => !n.disabled && n.tabIndex >= 0 && n.getClientRects().length && !n.closest("[data-pop],[inert]") && !from.contains(n));
        const rel = (n) => from.compareDocumentPosition(n);
        const next = back ? all.filter((n) => rel(n) & Node.DOCUMENT_POSITION_PRECEDING && !n.contains(from)).pop() : all.find((n) => rel(n) & Node.DOCUMENT_POSITION_FOLLOWING);
        if (next) next.focus();
      }, 60);
    }
    else if (e.key === "Enter") e.stopPropagation();      // the row behind never takes an Enter meant for the panel
  };
  return (
    <div class={`cpop ${cls}`} ref={box} role={role} aria-label={label} data-edit-only data-pop style="left:-10000px;top:0"
      onKeyDown={keys} onClick={(e) => e.stopPropagation()}>
      {children}
    </div>
  );
}

// The arrows, Home and End move focus through a list of controls (wrapping); returns whether the key was one of them.
export function roam(e, items) {
  const all = items.filter((el) => el && !el.disabled);
  if (!all.length) return false;
  const at = all.indexOf(document.activeElement);
  let next = -1;
  if (e.key === "ArrowDown") next = (at + 1) % all.length;
  else if (e.key === "ArrowUp") next = at <= 0 ? all.length - 1 : at - 1;
  else if (e.key === "Home") next = 0;
  else if (e.key === "End") next = all.length - 1;
  if (next < 0) return false;
  e.preventDefault();
  all[next].focus({ preventScroll: true });
  return true;
}
