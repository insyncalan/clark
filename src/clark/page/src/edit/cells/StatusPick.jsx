// #80: the Status picker, for one work item: the statuses its kind may have (a made decision is never offered Pending). Made on a
// pending decision carries "Can't be undone" in small print, so the person knows before the pick.
// Item 1183: a risk or issue is offered Open, Closed and Cancelled only; its Rating (Red, Amber, Green) is set from the 3 x 3 matrix (RatingPick), not here.
// `onPick(value)` makes the change; `onClose(back)` closes it, with focus back on `anchor` when `back` is true. The peek (#42) can
// use it as it is.
import { MenuPick } from "./MenuPick.jsx";
import { statusChoices, statusNote } from "../itemEdit.js";
import { todayIso } from "../../workItems.js";
import { statusIcon } from "../../menuIcons.js";

export function StatusPick({ row, anchor, onPick, onClose }) {
  const choices = statusChoices(row).map((s) => ({ value: s, text: s, note: statusNote(row, s), ...statusIcon(row, s, todayIso()) }));
  return <MenuPick anchor={anchor} label={`Status of ${row.id}`} current={row.status} onPick={onPick} onClose={onClose} choices={choices} />;
}
