// The options menu of a section (Edit only): Move up, Move down, Hide or Show, beside or full width, and Delete (a text
// section only). An item that cannot apply (Move up on the first section) is shown but marked aria-disabled, and does nothing.
import { useEffect, useRef, useState } from "preact/hooks";
import { moveUp, moveDown, setHidden, besideNext, fullWidth, canStep, canBeside, inPair, remove } from "./actions.js";

// An item that cannot apply stays in the menu, unavailable, with the reason on it.
const why = (r) => (r.ok || r.quiet ? {} : { off: true, reason: r.message });

export function Options({ section, index, count }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null), menu = useRef(null);
  const isText = section.type === "text";

  const items = (() => {
    const out = [
      { act: "up", text: "Move up", ...why(canStep(section.id, -1)), run: () => moveUp(section.id, "menu", "options") },
      { act: "down", text: "Move down", ...why(canStep(section.id, 1)), run: () => moveDown(section.id, "menu", "options") },
      section.hidden
        ? { act: "show", text: "Show in the published report", run: () => setHidden(section.id, false, "menu", "options") }
        : { act: "hide", text: "Hide from the published report", run: () => setHidden(section.id, true, "menu", "options") },
    ];
    out.push(inPair(section.id)
      ? { act: "full", text: "Full width", run: () => fullWidth(section.id, "menu", "options") }
      : { act: "beside", text: "Place beside the next section", ...why(canBeside(section.id)), run: () => besideNext(section.id, "menu", "options") });
    if (isText) out.push({ act: "delete", text: "Delete this section", run: () => remove(section.id, "menu") });
    return out;
  })();

  const close = (back) => { setOpen(false); if (back && button.current) button.current.focus(); };

  useEffect(() => {
    if (!open) return undefined;
    const enabled = menu.current && menu.current.querySelector('[role=menuitem]:not([aria-disabled=true])');
    if (enabled) enabled.focus();
    const away = (e) => { if (menu.current && !menu.current.contains(e.target) && e.target !== button.current && !button.current.contains(e.target)) setOpen(false); };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [open]);

  const onMenuKey = (e) => {
    const all = Array.from(menu.current.querySelectorAll('[role=menuitem]:not([aria-disabled=true])'));
    const at = all.indexOf(document.activeElement);
    if (e.key === "Escape") { e.preventDefault(); close(true); }
    else if (e.key === "Tab") setOpen(false);
    else if (e.key === "ArrowDown") { e.preventDefault(); if (all.length) all[(at + 1) % all.length].focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); if (all.length) all[(at - 1 + all.length) % all.length].focus(); }
    else if (e.key === "Home") { e.preventDefault(); if (all.length) all[0].focus(); }
    else if (e.key === "End") { e.preventDefault(); if (all.length) all[all.length - 1].focus(); }
  };

  const pick = (item) => {
    if (item.off) return;
    close(item.act !== "delete");               // a deleted section's focus goes to a neighbour (actions.remove)
    item.run();
  };

  return (
    <span class="opts">
      <button type="button" class="opts-btn" ref={button} data-edit-only data-options aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        aria-label={`Options for ${section.title}`} onClick={() => setOpen(!open)}>
        <svg viewBox="0 0 16 4" width="16" height="4" aria-hidden="true" focusable="false"><g fill="currentColor"><circle cx="2" cy="2" r="1.6" /><circle cx="8" cy="2" r="1.6" /><circle cx="14" cy="2" r="1.6" /></g></svg>
      </button>
      {open ? (
        <div class="menu" role="menu" ref={menu} data-edit-only aria-label={`Options for ${section.title}`} onKeyDown={onMenuKey}>
          {items.map((it) => (
            <button type="button" role="menuitem" class="menu-item" key={it.act} data-act={it.act} aria-disabled={it.off ? "true" : undefined} title={it.reason} onClick={() => pick(it)}>{it.text}</button>
          ))}
        </div>
      ) : null}
    </span>
  );
}
