// The peek's width rule (item 1202): 640 px to start, at least 420 px, at most the window width minus 32 px so the page stays in view.
// No imports, so it can be checked on its own.
export const MIN = 420;
export const DEFAULT = 640;
export const GAP = 32;

/** `w` as a whole number between MIN and the window width minus GAP (MIN wins in a window too small for both); the default for no number. */
export function limit(w, win = document.documentElement.clientWidth) {
  const top = Math.max(MIN, win - GAP), n = Math.round(Number(w));
  return Number.isFinite(n) ? Math.min(top, Math.max(MIN, n)) : DEFAULT;
}
