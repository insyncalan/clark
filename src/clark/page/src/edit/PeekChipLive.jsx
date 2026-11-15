// Row 1180: the editor's interactive chip (a button that opens the field's popover). Edit only: the published file draws the plain span in
// components/PeekChips.jsx and holds none of this.
import { useRef } from "preact/hooks";
import { Icon } from "../components/Icon.jsx";
import { openCell } from "../stores/openCell.js";

export function PeekChipLive({ id, field, name, value, sub, tip, pop, place, cls, body, changed, flash }) {
  const button = useRef(null);
  const k = `${place}:${id}:${field}`, open = openCell.value === k;
  const close = (back) => { if (openCell.value === k) openCell.value = ""; if (back && button.current) button.current.focus(); };
  const down = (e) => {
    if (e.key === "Escape" && open) { e.preventDefault(); e.stopPropagation(); close(true); }
    else if (e.key === "ArrowDown" && e.altKey && !open) { e.preventDefault(); openCell.value = k; }
  };
  return (
    <span class={`${cls} has-pop`} data-row={field} data-flash={flash ? "1" : undefined}>
      <button type="button" class="pkc-btn" ref={button} data-edit-only data-cell={k} data-tip={tip || undefined} aria-haspopup="dialog" aria-expanded={open ? "true" : "false"}
        aria-label={`${name} of ${id}: ${value}${sub ? ", " + sub : ""}. Change`} onClick={(e) => { e.stopPropagation(); openCell.value = open ? "" : k; }} onKeyDown={down}>
        {body}
        <span class="pkc-car"><Icon name="chevdown" /></span>
      </button>
      {changed}
      {open ? pop({ anchor: button, close }) : null}
    </span>
  );
}
