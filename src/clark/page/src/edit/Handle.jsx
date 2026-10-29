// The handle in the margin of a section (Edit only): Alt+Up and Alt+Down on it move the section, and dragging it does too.
// The drag uses pointer events (not the browser's own drag and drop), so a mouse, a pen and a finger all work and the handle
// stays the same element, keeping focus.
import { useRef } from "preact/hooks";
import { moveUp, moveDown } from "./actions.js";
import { startDrag } from "./drag.js";

export function Handle({ section, count }) {
  const ref = useRef(null);

  const onKeyDown = (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    if (e.key === "ArrowUp") moveUp(section.id, "report", "handle"); else moveDown(section.id, "report", "handle");
  };

  const onPointerDown = (e) => startDrag(e, ref.current, section.id, count);

  return (
    <button type="button" class="handle" ref={ref} data-edit-only data-drag aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"
      aria-label={`Move ${section.title}. Press Alt with the up or down arrow, or drag.`} onKeyDown={onKeyDown} onPointerDown={onPointerDown}>
      <svg viewBox="0 0 12 18" width="12" height="18" aria-hidden="true" focusable="false">
        <g fill="currentColor"><circle cx="3" cy="3" r="1.5" /><circle cx="9" cy="3" r="1.5" /><circle cx="3" cy="9" r="1.5" /><circle cx="9" cy="9" r="1.5" /><circle cx="3" cy="15" r="1.5" /><circle cx="9" cy="15" r="1.5" /></g>
      </svg>
    </button>
  );
}
