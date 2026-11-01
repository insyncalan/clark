// The arrow keys on a list (#194): one cursor shared by the Work items table and board. No J or K: arrows and Enter only. Plain JS, so the table (components/WorkItems.jsx)
// and the board (edit/Board.jsx) each add one line and keep their own rules.
import { signal } from "@preact/signals";
import { openPeek } from "./stores/report.js";

export const cursor = signal("");                // the id of the row or card that is the list's one tab stop

/** The one tab stop of a list: the cursor if it is drawn, else the first. */
export function stopOf(ids) { return ids.includes(cursor.value) ? cursor.value : ids.length ? ids[0] : ""; }

/** Open the peek of the cursor's item. */
export function openAt(id) { openPeek(id, "item"); }

/** The index a movement key gives in a list of `count` (Up/Left back, Down/Right on, Home, End); -1 when the key is not one. */
export function moveTo(key, at, count, keys) {
  const k = keys || ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"];
  if (!k.includes(key) || count < 1) return -1;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  const j = at + (key === "ArrowUp" || key === "ArrowLeft" ? -1 : 1);
  return Math.max(0, Math.min(count - 1, j));
}

/** A key on a board card's own button: arrows move card to card in reading order, Home and End to the first and last. */
export function cardKeys(e, id) {
  if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.target !== e.currentTarget) return;
  const cards = Array.from(e.currentTarget.closest(".board").querySelectorAll(".bc-main")), j = moveTo(e.key, cards.indexOf(e.currentTarget), cards.length);
  if (j < 0) return;
  e.preventDefault();
  const to = cards[j];
  to.focus();
}
