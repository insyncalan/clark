// The one quiet control of a section (Edit only, #101): a grip with a "+" under it, in the page's left margin, outside the
// section's own box so it never moves or narrows the section. The grip drags to move (edit/drag.js), a click, Enter or Space opens
// its menu, and Alt+Up and Alt+Down on it move the section by rows. The "+" adds a section below (edit/addSection.js).
// Faint at rest, clear when the section is hovered or has focus, and while the menu is open (shell.css).
import { useEffect, useRef } from "preact/hooks";
import { moveUp, moveDown, setHidden, besideNext, fullWidth, canStep, canBeside, inPair, remove } from "./actions.js";
import { startDrag } from "./drag.js";
import { askToAdd } from "./addSection.js";
import { note } from "./notes.js";
import { useMenuState } from "../components/Menu.jsx";

// An item that cannot apply stays in the menu, unavailable, with the reason on it.
const why = (r) => (r.ok || r.quiet ? {} : { off: true, reason: r.message });
const DELETABLE = ["text", "needs"];             // the types the store lets a person delete (changes.py): a text section and one that carries content
const MOVED = 4;                               // px: more than this between press and release was a drag, not a click

export function Gutter({ section, count }) {
  const [open, setOpen] = useMenuState();
  const grip = useRef(null), menu = useRef(null), down = useRef(null);
  const canDelete = DELETABLE.includes(section.type);

  const items = (() => {
    const out = [
      { act: "add", text: "Add a template below…", run: () => askToAdd(section.id, grip.current) },
      { act: "up", text: "Move up", ...why(canStep(section.id, -1)), run: () => moveUp(section.id, "menu", "options") },
      { act: "down", text: "Move down", ...why(canStep(section.id, 1)), run: () => moveDown(section.id, "menu", "options") },
      inPair(section.id)
        ? { act: "full", text: "Full width", run: () => fullWidth(section.id, "menu", "options") }
        : { act: "beside", text: "Place beside the next section", ...why(canBeside(section.id)), run: () => besideNext(section.id, "menu", "options") },
      section.hidden
        ? { act: "show", text: "Include in the published page", run: () => setHidden(section.id, false, "menu", "options") }
        : { act: "hide", text: "Leave out of the published page", run: () => setHidden(section.id, true, "menu", "options") },
    ];
    if (canDelete) out.push({ act: "delete", text: "Delete section", run: () => remove(section.id, "menu") });
    return out;
  })();

  const close = (back) => { setOpen(false); if (back && grip.current) grip.current.focus(); };

  useEffect(() => {
    if (!open) return undefined;
    const enabled = menu.current && menu.current.querySelector("[role=menuitem]:not([aria-disabled=true])");
    if (enabled) enabled.focus();
    const away = (e) => { if (menu.current && !menu.current.contains(e.target) && !grip.current.contains(e.target)) setOpen(false); };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [open]);

  const onKeyDown = (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    if (e.key === "ArrowUp") moveUp(section.id, "report", "handle"); else moveDown(section.id, "report", "handle");
  };
  const onPointerDown = (e) => { down.current = [e.clientX, e.clientY]; startDrag(e, grip.current, section.id, count); };
  const onClick = (e) => {
    const d = down.current; down.current = null;
    if (d && e.detail !== 0 && Math.hypot(e.clientX - d[0], e.clientY - d[1]) > MOVED) return;      // the end of a drag
    setOpen(!open);
  };

  const onMenuKey = (e) => {
    const all = Array.from(menu.current.querySelectorAll("[role=menuitem]"));      // an unavailable item can be reached too: its reason is read out
    const at = all.indexOf(document.activeElement);
    if (e.key === "Escape") { e.preventDefault(); close(true); }
    else if (e.key === "Tab") setOpen(false);
    else if (e.key === "ArrowDown") { e.preventDefault(); if (all.length) all[(at + 1) % all.length].focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); if (all.length) all[(at - 1 + all.length) % all.length].focus(); }
    else if (e.key === "Home") { e.preventDefault(); if (all.length) all[0].focus(); }
    else if (e.key === "End") { e.preventDefault(); if (all.length) all[all.length - 1].focus(); }
  };

  const pick = (item) => {
    if (item.off) { note(item.reason); return; }      // an unavailable item says why, on screen and to a screen reader
    close(item.act !== "delete" && item.act !== "add");      // a deleted section's focus goes to a neighbour; the dialog takes its own
    item.run();
  };

  return (
    <div class={`sec-ctl${open ? " open" : ""}`}>
      <button type="button" class="handle" ref={grip} data-edit-only data-drag data-options aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown" title="Drag to move · click for options"
        aria-label={`Move or change ${section.title}`} onKeyDown={onKeyDown} onPointerDown={onPointerDown} onClick={onClick}>
        <svg viewBox="0 0 12 18" width="12" height="18" aria-hidden="true" focusable="false">
          <g fill="currentColor"><circle cx="3" cy="3" r="1.5" /><circle cx="9" cy="3" r="1.5" /><circle cx="3" cy="9" r="1.5" /><circle cx="9" cy="9" r="1.5" /><circle cx="3" cy="15" r="1.5" /><circle cx="9" cy="15" r="1.5" /></g>
        </svg>
      </button>
      <button type="button" class="plus" data-edit-only data-add title="Add a template below" aria-label={`Add a template below ${section.title}`} onClick={(e) => askToAdd(section.id, e.currentTarget)}>
        <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true" focusable="false"><path d="M6 1v10M1 6h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none" /></svg>
      </button>
      {section.hidden ? (
        <span class="eye" role="img" aria-label="Left out of the published page" title="Left out of the published page">
          <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
            <g fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M1.5 8s2.3-4 6.5-4 6.5 4 6.5 4-2.3 4-6.5 4S1.5 8 1.5 8z" /><circle cx="8" cy="8" r="1.8" /><path d="M2.5 13.5l11-11" /></g>
          </svg>
        </span>
      ) : null}
      {open ? (
        <div class="menu" role="menu" ref={menu} data-edit-only aria-label={`Options for ${section.title}`} onKeyDown={onMenuKey}>
          {items.map((it) => [
            <button type="button" role="menuitem" class="menu-item" key={it.act} data-act={it.act} aria-disabled={it.off ? "true" : undefined}
              aria-describedby={it.off ? `why-${section.id}-${it.act}` : undefined} onClick={() => pick(it)}>{it.text}</button>,
            it.off ? <div class="menu-why" key={`${it.act}-why`} id={`why-${section.id}-${it.act}`} role="none">{it.reason}</div> : null,
          ])}
        </div>
      ) : null}
    </div>
  );
}
