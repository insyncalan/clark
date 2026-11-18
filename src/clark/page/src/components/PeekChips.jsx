// Row 1180: the peek's flat chip row. One chip = a coloured icon, the value in words, an optional small sub-line word ("overdue 2 days",
// "Red kept") and a small chevron; a click, Enter, Space or Alt+Down opens its popover. The chip and the row are generic: the caller
// (Peek.jsx) says which fields to draw and gives each chip its popover as a function, so the existing pickers (StatusPick, OwnerPick,
// DuePick, PriorityPick) are used as they are. One popover is open at a time: the open key is the shared openCell signal
// of the table's cells, with a "peek:" key so the table's popover and the peek's are never both open. With no `pop` (a read-only peek:
// the published file, the Dashboard in View, a field that cannot be picked) the chip is drawn as a plain span: same look, no control.
import { Icon } from "./Icon.jsx";
import { iconClass } from "../iconColours.js";

/** The row. `children`: PeekChip elements. */
export function PeekChips({ children, label = "Properties", cls = "" }) {
  return <div class={`pk-chips${cls ? " " + cls : ""}`} role="group" aria-label={label}>{children}</div>;
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
 *  subTone  optional: "late" or "kept" draws the sub-line as a red pill
 *  late     true: an overdue date; the chip keeps its normal fill, only the date text and the sub-word pill are red
 *  flash    true: the Changed tag shows beside the chip (the existing flash)
 *  tip      optional hover text (a field that cannot be picked says why)
 *  pop      optional ({ anchor, close }) => element. Absent: read only.
 *  Live     the editor's interactive chip (edit/PeekChipLive.jsx, handed down by tools); absent: read only, so a published file holds none of its code. `close(back)`: back true puts focus on the chip.
 *  place    popover key prefix, default "peek"
 */
export function PeekChip({ id, field, name, icon, tone = "n", value, sub, subTone, late, flash, tip, pop, Live, place = "peek", children }) {
  const body = (
    <>
      <span class={`pkc-ic ${iconClass(tone)}`}><Icon name={icon} /></span>
      <span class="pkc-tx"><span class="pkc-v">{children || value}</span>{sub ? <em class={`pkc-sub pk-chip-sub${subTone ? " " + subTone : ""}`}>{sub}</em> : null}</span>
    </>
  );
  const cls = `pkc${late ? " late" : ""}${flash ? " flash" : ""}`;
  const changed = flash ? <span class="tag chg">Changed</span> : null;
  if (!pop || !Live) {
    return <span class={`${cls} ro`} data-row={field} data-flash={flash ? "1" : undefined} data-tip={tip || undefined} role="group" aria-label={`${name}: ${value}${sub ? ", " + sub : ""}`}>{body}{changed}</span>;
  }
  return <Live id={id} field={field} name={name} value={value} sub={sub} tip={tip} pop={pop} place={place} cls={cls} body={body} changed={changed} flash={flash} />;
}
