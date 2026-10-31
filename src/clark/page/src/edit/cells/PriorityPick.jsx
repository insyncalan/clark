// #80: the Priority picker, for an action (a RAID item's priority comes from its impact and likelihood; a decision has none).
// The same props as StatusPick, so the peek (#42) can use it as it is.
import { MenuPick } from "./MenuPick.jsx";
import { PRIORITIES } from "../itemEdit.js";

export function PriorityPick({ row, anchor, onPick, onClose }) {
  return <MenuPick anchor={anchor} label={`Priority of ${row.id}`} current={row.priority} onPick={onPick} onClose={onClose}
    choices={PRIORITIES.map((p) => ({ value: p, text: p }))} />;
}
