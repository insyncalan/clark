// The arrow keys on a list (#194): one cursor shared by the Work items table and board, the peek following it, and focus coming
// back to the cursor when the peek closes. No J or K: arrows and Enter only. Plain JS, so the table (components/WorkItems.jsx)
// and the board (edit/Board.jsx) each add one line and keep their own rules.
import { signal } from "@preact/signals";
import { peek, openPeek, closePeek } from "./stores/report.js";

export const cursor = signal("");                // the id of the row or card that is the list's one tab stop

/** The one tab stop of a list: the cursor if it is drawn, else the first. */
export function stopOf(ids) { return ids.includes(cursor.value) ? cursor.value : ids.length ? ids[0] : ""; }

/** Whether an item's peek is open. */
export function peekIsOpen() { const p = peek.value; return !!p && p.kind === "item"; }

/** With a peek open, it follows the cursor to another item of the list it was opened from. */
export function followPeek(id) { if (peekIsOpen() && peek.value.id !== id) openPeek(id, "item"); }

/** Open the peek of the cursor's item. */
export function openAt(id) { openPeek(id, "item"); }

/** Close the peek if one is open (the Left key). Returns whether it did. */
export function closeAt() { if (!peekIsOpen()) return false; closePeek(); return true; }

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
  followPeek(to.closest("[data-id]").dataset.id);
}

/** When the peek closes and focus has fallen to the page, put it back on the cursor's row or card. Returns the stop function. */
export function keepFocusOnClose() {
  let was = !!peek.peek();
  return peek.subscribe((p) => {
    const now = !!p;
    if (was && !now) setTimeout(() => {
      const a = document.activeElement;
      if (a && a !== document.body && a !== document.documentElement) return;
      const el = cursor.value ? document.querySelector(`#work tr[data-id="${cursor.value}"], #work .bc-main[data-cursor="${cursor.value}"]`) : null;
      if (el) el.focus();
    }, 0);
    was = now;
  });
}
