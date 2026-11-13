// A small modal box for Settings (item 444): the project form and Import workbook. Edit only (a published file has no
// Settings). It follows the Add a section box (AddDialog.jsx): focus starts in `first` (a selector inside it, else the first control), Tab
// stays inside, Esc closes it, a click on the backdrop closes it, the page behind is `inert` while it is open, and focus goes back to what
// opened it. The words are the caller's and are drawn as text.
import { useEffect, useRef } from "preact/hooks";
import { inertBehind } from "./modalLayers.js";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// The controls Tab can reach: a hidden one (the import's file input) is not one, so the wrap lands on a control that takes the focus.
const tabbable = (r) => Array.from(r.querySelectorAll(FOCUSABLE)).filter((el) => !el.hidden && el.type !== "hidden" && el.offsetParent !== null);

// Focus the first of `selectors` (one, or a list tried in order) that is drawn; it may not be drawn yet (the screen after a removal), so look again a few times.
function giveFocusTo(selectors) {                                  // the best target that exists once the page has stopped changing (a screen can render a beat after the box closes)
  const list = [].concat(selectors);
  let obs = null, quiet = null;
  const give = () => {
    if (obs) obs.disconnect();
    clearTimeout(quiet); clearTimeout(limit);
    if (document.querySelector(".ad-scrim")) return;
    const el = list.map((s) => document.querySelector(s)).find((x) => x && x.focus);
    if (el) el.focus();
  };
  const settle = () => { clearTimeout(quiet); quiet = setTimeout(give, 150); };      // 150 ms with no change to the page
  const limit = setTimeout(give, 2000);                            // bounded: a page that never stops changing still gets the focus after 2 seconds
  if (typeof MutationObserver !== "undefined") { obs = new MutationObserver(settle); obs.observe(document.body, { childList: true, subtree: true }); }
  settle();
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
      const el = back.current, fb = later.current;
      setTimeout(() => {                                                       // looked at after the render, not now: the opener may be removed in the same update that closes the box
        if (document.querySelector(".ad-scrim")) return;                       // not when another box took its place (the import's next step)
        if (el && el.isConnected && el.focus) el.focus();
        else if (fb) giveFocusTo(fb);                                      // the opener went while the box was open (the demo banner): focus goes to the caller's fallback
      }, 0);
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
