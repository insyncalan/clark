// #80: the Priority picker, for an action (a RAID item's priority comes from its impact and likelihood; a decision has none).
// The same props as StatusPick, so the peek (#42) can use it as it is. Row 1282: a risk's or issue's opens the peek's own Impact x Likelihood
// matrix (PeekRating.jsx), one shared component, so the list and the peek cannot drift.
import { MenuPick } from "./MenuPick.jsx";
import { Matrix } from "../PeekRating.jsx";
import { PRIORITIES } from "../itemEdit.js";
import { priorityIcon } from "../../menuIcons.js";

export function PriorityPick({ row, anchor, onPick, onClose, place }) {
  if (row.kind !== "action") return <Matrix row={row} anchor={anchor} onClose={onClose} place={place || "cell"} />;
  return <MenuPick anchor={anchor} label={`Priority of ${row.id}`} current={row.priority} onPick={onPick} onClose={onClose}
    choices={PRIORITIES.map((p) => ({ value: p, text: p, ...priorityIcon(p) }))} />;
}
