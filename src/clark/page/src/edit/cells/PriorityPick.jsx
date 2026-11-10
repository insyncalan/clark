// #80: the Priority picker, for an action (a RAID item's priority comes from its impact and likelihood; a decision has none).
// The same props as StatusPick, so the peek (#42) can use it as it is. Item 210: a risk's or issue's opens RatingPick instead.
import { MenuPick } from "./MenuPick.jsx";
import { RatingPick } from "./RatingPick.jsx";
import { PRIORITIES } from "../itemEdit.js";
import { priorityIcon } from "../../menuIcons.js";

export function PriorityPick({ row, anchor, onPick, onClose }) {
  if (row.kind !== "action") return <RatingPick row={row} anchor={anchor} onPick={onPick} onClose={onClose} />;
  return <MenuPick anchor={anchor} label={`Priority of ${row.id}`} current={row.priority} onPick={onPick} onClose={onClose}
    choices={PRIORITIES.map((p) => ({ value: p, text: p, ...priorityIcon(p) }))} />;
}
