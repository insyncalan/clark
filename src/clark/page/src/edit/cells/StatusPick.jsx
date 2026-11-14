// #80: the Status picker, for one work item: the statuses its kind may have (a made decision is never offered Pending). Made on a
// pending decision carries "Can't be undone" in small print, so the person knows before the pick.
// `onPick(value)` makes the change; `onClose(back)` closes it, with focus back on `anchor` when `back` is true. The peek (#42) can
// use it as it is.
import { MenuPick } from "./MenuPick.jsx";
import { statusChoices, statusNote } from "../itemEdit.js";
import { todayIso } from "../../workItems.js";
import { statusIcon } from "../../menuIcons.js";

export function StatusPick({ row, anchor, onPick, onClose }) {
  // Items 1182, 1183 (ruled): a risk or issue is Open, Closed or Cancelled and no more, in the peek and in the table alike. Its colour is set only
  // from impact and likelihood (the peek's Rating chip and matrix, or the Impact and Likelihood boxes), never from this menu.
  const choices = statusChoices(row).map((s) => ({ value: s, text: s, note: statusNote(row, s), ...statusIcon(row, s, todayIso()) }));
  return <MenuPick anchor={anchor} label={`Status of ${row.id}`} current={row.status}
    onPick={onPick} onClose={onClose} choices={choices} />;
}
