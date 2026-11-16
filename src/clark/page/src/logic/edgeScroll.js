// Row 1214: how far the page scrolls while a section is dragged near the top or bottom of the window. Pure: numbers in, a number out.
// Same feel as the board's drag (edit/Board.jsx): a 56 px edge band, a step of min(24, ceil(depth / 3)) px per frame.
export const EDGE = 56;
export const MAX_STEP = 24;

const step = (depth) => Math.min(MAX_STEP, Math.ceil(depth / 3));

// y: the pointer's height in the window. top: the window's top edge for this purpose (the bottom of the sticky bar).
// bottom: the window's height. Returns the pixels to scroll down (positive), up (negative) or 0.
export function edgeStep(y, top, bottom, edge = EDGE) {
  if (![y, top, bottom].every(Number.isFinite)) return 0;
  if (bottom - top < edge * 2) return 0;          // a window too short to have two bands: no scrolling, never a jitter
  if (y > bottom - edge) return step(y - (bottom - edge));
  if (y < top + edge) return -step(top + edge - y);
  return 0;
}
