// A small modal box for Settings (item 444): the project form and Import workbook. Edit only (a published file has no
// Settings). It follows the Add a section box (AddDialog.jsx): focus starts in `first` (a selector inside it, else the first control), Tab
// stays inside, Esc closes it, a click on the backdrop closes it, the page behind is `inert` while it is open, and focus goes back to what
// opened it. The words are the caller's and are drawn as text.
import { useEffect, useRef } from "preact/hooks";
import { inertBehind } from "./modalLayers.js";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// The controls Tab can reach: a hidden one (the import's file input) is not one, so the wrap lands on a control that takes the focus.
const tabbable = (r) => Array.from(r.querySelectorAll(FOCUSABLE)).filter((el) => !el.hidden && el.type !== "hidden" && el.offsetParent !== null);

// Focus the first match of `selector`; it may not be drawn yet (the empty screen after a removal), so look again a few times.
function giveFocusTo(selector, tries) {
  setTimeout(() => {
    if (document.querySelector(".ad-scrim")) return;
    const el = document.querySelector(selector);
    if (el && el.focus) el.focus();
    else if (tries > 0) giveFocusTo(selector, tries - 1);
  }, 25);
}

export function Dialog({ title, id, onClose, first, wide, children, foot, onSubmit, opener, fallback }) {
  const root = useRef(null);
  const later = useRef(fallback);                                  // read when the box closes, so a caller can change it while the box is open
  later.current = fallback;
  const back = useRef(opener || (typeof document !== "undefined" ? document.activeElement : null));
  useEffect(() => {
    const r = root.current;
    const release = inertBehind(r);                                 // everything outside the box, a toast button too (modalLayers.js)
    const start = (first && r && r.querySelector(first)) || (r && tabbable(r)[0]);
    if (start) start.focus();
    return () => {
      release();
      const el = back.current;
      if (el && el.isConnected && el.focus) setTimeout(() => { if (!document.querySelector(".ad-scrim")) el.focus(); }, 0);   // not when another box took its place (the import's next step)
      else if (later.current) giveFocusTo(later.current, 20);                  // the opener went while the box was open (the demo banner): focus goes to the caller's fallback
    };
  }, []);
  const onKeyDown = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab" || !root.current) return;
    const all = tabbable(root.current);
    if (!all.length) return;
    const a = all[0], z = all[all.length - 1];
    if (!root.current.contains(document.activeElement) || document.activeElement === root.current) { e.preventDefault(); (e.shiftKey ? z : a).focus(); }
    else if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
    else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
  };
  const Tag = onSubmit ? "form" : "div";
  return (
    <div class="ad-scrim" data-edit-only onKeyDown={onKeyDown} onPointerDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <Tag class={`ad dlg${wide ? " wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby={`${id}-t`} tabindex="-1" ref={root} id={id} onSubmit={onSubmit} noValidate={false}>
        <div class="ad-head"><h2 id={`${id}-t`}>{title}</h2></div>
        <div class="dlg-b">{children}</div>
        <div class="ad-foot">{foot}</div>
      </Tag>
    </div>
  );
}
