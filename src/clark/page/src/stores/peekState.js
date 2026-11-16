// The peek's width and whether it spans the screen (#42). The width is kept in this browser (localStorage, wrapped: it can throw or
// come back empty in a private window) so a reload and the next item keep it. "Across the whole screen" is for now only.
import { signal } from "@preact/signals";

import { MIN, DEFAULT, limit } from "../peek/width.js";
export { MIN, DEFAULT, limit };
const KEY = "clark.peekWidth";

function saved() {
  try { const n = Number(localStorage.getItem(KEY)); return n ? limit(n) : DEFAULT; } catch (e) { return DEFAULT; }
}

export const width = signal(saved());
export const wide = signal(false);

/** Set the width (kept between MIN and the window minus 32 px, item 1202) and remember it. */
export function setWidth(w) {
  width.value = limit(w);
  try { localStorage.setItem(KEY, String(width.value)); } catch (e) { /* the width still holds for this visit */ }
}

/** Double-click on the edge: back to the default, and forget the saved one. */
export function resetWidth() {
  width.value = limit(DEFAULT);
  try { localStorage.removeItem(KEY); } catch (e) { /* as above */ }
}

// Which history tab shows under the peek in Edit: "all", "activity", "updates" or "source" (row 1180). Memory only; View has no tabs.
export const peekTab = signal("all");

// The rule for the peek and multi-select (#195), in peek/follow.js so it can be checked without the page.
export { peekFollowsSelection } from "../peek/follow.js";
