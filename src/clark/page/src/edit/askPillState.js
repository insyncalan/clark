// Row 1332: the three counts that order the suggestions, worked out from the rows the page already holds.
import { isOpen, isLate, ownerOf } from "../workItems.js";
import { tiles } from "../glanceTiles.js";

/** { overdue: late open items, red: high risks and issues (the tile's own count), noOwner: open items nobody owns } */
export function stateOf(rows, today) {
  const list = Array.isArray(rows) ? rows : [];
  const open = list.filter((r) => isOpen(r));
  const high = tiles(list, today).find((t) => t.key === "risks");
  return {
    overdue: list.filter((r) => isLate(r, today)).length,
    red: high ? high.value : 0,
    noOwner: open.filter((r) => !ownerOf(r.owner).initials).length,
  };
}
