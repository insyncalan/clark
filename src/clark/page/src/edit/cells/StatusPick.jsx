// #80: the Status picker, for one work item: the statuses its kind may have (a made decision is never offered Pending). Made on a
// pending decision carries "Can't be undone" in small print, so the person knows before the pick.
// `onPick(value)` makes the change; `onClose(back)` closes it, with focus back on `anchor` when `back` is true. The peek (#42) can
// use it as it is.
import { MenuPick } from "./MenuPick.jsx";
import { statusChoices, statusNote, ratingChoices } from "../itemEdit.js";
import { colourOf } from "../../workItems.js";

export function StatusPick({ row, anchor, onPick, onClose }) {
  // A risk or issue also has a Rating section (Red, Amber, Green): its colour is set from impact and likelihood (D-12).
  const rating = ratingChoices(row);
  const choices = statusChoices(row).map((s) => ({ value: s, text: s, note: statusNote(row, s) }));
  if (rating.length) choices.push({ heading: "Rating" }, ...rating.map((w) => ({ value: `rating:${w}`, text: w })));
  const open = row.status === "Open";
  return <MenuPick anchor={anchor} label={`Status of ${row.id}`} current={rating.length && open ? [row.status, `rating:${colourOf(row.priority).word}`] : row.status}
    onPick={onPick} onClose={onClose} choices={choices} />;
}
