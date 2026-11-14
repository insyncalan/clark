// Row 1180: the peek's flat chip row. One chip = a coloured icon, the value in words, an optional small sub-line word ("overdue 2 days",
// "Red kept") and a small chevron; a click, Enter, Space or Alt+Down opens its popover. The chip and the row are generic: the caller
// (Peek.jsx) says which fields to draw and gives each chip its popover as a function, so the existing pickers (StatusPick, OwnerPick,
// DuePick, PriorityPick, RatingPick) are used as they are. One popover is open at a time: the open key is the shared openCell signal
// of the table's cells, with a "peek:" key so the table's popover and the peek's are never both open. With no `pop` (a read-only peek:
// the published file, the Dashboard in View, a field that cannot be picked) the chip is drawn as a plain span: same look, no control.
import { useRef } from "preact/hooks";
import { Icon } from "./Icon.jsx";
import { iconClass } from "../iconColours.js";
import { openCell } from "../stores/openCell.js";

/** The row. `children`: PeekChip elements. */
export function PeekChips({ children, label = "Properties" }) {
  return <div class="pk-chips" role="group" aria-label={label}>{children}</div>;
}

/**
 * One chip.
 *  id       the item's id (for the popover key and the label)
 *  field    "status" | "owner" | "due" | "priority" | ... (the popover key and data-row, so the Changed flash can find the chip)
 *  name     the field's name in words ("Owner", "Needed by"); said by screen readers
 *  icon     an Icon name ("half", "user", "cal", "bars")
 *  tone     r | a | g | b | n: the icon's colour class; a tone is never the only signal, the value is written
 *  value    the value as words ("Open", "Omar Ali", "24-10-2026")
 *  sub      optional small word after the value ("overdue 2 days", "Red kept")
 *  subTone  optional: "late" draws the sub-line red
 *  late     true: the chip itself takes the red tint (an overdue date)
 *  flash    true: the Changed tag shows beside the chip (the existing flash)
 *  tip      optional hover text (a field that cannot be picked says why)
 *  pop      optional ({ anchor, close }) => element. Absent: read only. `close(back)`: back true puts focus on the chip.
 *  place    popover key prefix, default "peek"
 */
export function PeekChip({ id, field, name, icon, tone = "n", value, sub, subTone, late, flash, tip, pop, place = "peek", children }) {
  const button = useRef(null);
  const body = (
    <>
      <span class={`pkc-ic ${iconClass(tone)}`}><Icon name={icon} /></span>
      <span class="pkc-tx"><span class="pkc-v">{children || value}</span>{sub ? <em class={`pkc-sub pk-chip-sub${subTone ? " " + subTone : ""}`}>{sub}</em> : null}</span>
    </>
  );
  const cls = `pkc${late ? " late" : ""}${flash ? " flash" : ""}`;
  const changed = flash ? <span class="tag chg">Changed</span> : null;
  if (!pop) {
    return <span class={`${cls} ro`} data-row={field} data-flash={flash ? "1" : undefined} data-tip={tip || undefined} role="group" aria-label={`${name}: ${value}${sub ? ", " + sub : ""}`}>{body}{changed}</span>;
  }
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
