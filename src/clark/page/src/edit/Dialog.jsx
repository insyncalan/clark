// A small modal box for Settings (#444): the project form, Import workbook and the Reset confirm. Edit only (a published file has no
// Settings). It follows the Add a section box (AddDialog.jsx): focus starts in `first` (a selector inside it, else the first control), Tab
// stays inside, Esc closes it, a click on the backdrop closes it, the page behind is `inert` while it is open, and focus goes back to what
// opened it. The words are the caller's and are drawn as text.
import { useEffect, useRef } from "preact/hooks";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const BEHIND = ["#main", ".top"];                                    // made inert while the box is open (the message area stays live)

export function Dialog({ title, id, onClose, first, wide, children, foot, onSubmit, opener }) {
  const root = useRef(null);
  const back = useRef(opener || (typeof document !== "undefined" ? document.activeElement : null));
  useEffect(() => {
    const held = BEHIND.map((q) => document.querySelector(q)).filter(Boolean);
    held.forEach((el) => el.setAttribute("inert", ""));
    const r = root.current;
    const start = (first && r && r.querySelector(first)) || (r && r.querySelector(FOCUSABLE));
    if (start) start.focus();
    return () => {
      held.forEach((el) => el.removeAttribute("inert"));
      const el = back.current;
      if (el && el.isConnected && el.focus) setTimeout(() => { if (!document.querySelector(".ad-scrim")) el.focus(); }, 0);   // not when another box took its place (the import's next step)
    };
  }, []);
  const onKeyDown = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab" || !root.current) return;
    const all = Array.from(root.current.querySelectorAll(FOCUSABLE));
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
