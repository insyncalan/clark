// Row 1223: the ONE framing model of the Full width image (an imagecap section's body of version 2), pure (no DOM, nothing sent): the shape's
// ratio, the part of the original a frame shows, the limits of a height, the crop box, and the way a frame is stored.
//
// THE FRAME (what the page works with): { shape?: "16:9"|"banner"|"free" (none: the whole image), fx?, fy?: the focus, 0..1 (none: .5),
//   ratio?: width / height (free only), crop?: { x, y, w, h } fractions of the original, fit?: "stretch" (none: centre),
//   fill?: "brand"|"plain" (none: blur) }. An all-default frame is {}.
// WHAT IS STORED (section_kinds/imagecap.py, version 2, flat in the body, whole numbers only, a key only when it is not the default):
//   shape, ratio (thousandths), fx, fy (0..1000), crop [x0, y0, x1, y1] (0..1000), fit, fill. bodyFields makes them, frameOfBody reads them.
// The original is never changed: the frame says how to look at it, and clark makes the framed copy from the original and these numbers.
// Words and the shape names are fullImageWords.js's.
import { UNRULED_SHAPES, UNRULED_FITS, UNRULED_FILLS, UNRULED_FLATTEST, UNRULED_TALLEST, UNRULED_SMALL_WIDE } from "./fullImageWords.js";

const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));
const num = (v, lo, hi, d) => (typeof v === "number" && Number.isFinite(v) ? clamp(v, lo, hi) : d);
const r4 = (n) => Math.round(n * 10000) / 10000;

// The frame as stored, rebuilt: only known keys, only values that are not the default (an all-default frame is {}).
export function cleanFrame(f) {
  const v = f && typeof f === "object" && !Array.isArray(f) ? f : {};
  const out = {};
  if (UNRULED_SHAPES.includes(v.shape) && v.shape !== "whole") out.shape = v.shape;
  const fx = r4(num(v.fx, 0, 1, 0.5)), fy = r4(num(v.fy, 0, 1, 0.5));
  if (fx !== 0.5) out.fx = fx;
  if (fy !== 0.5) out.fy = fy;
  if (out.shape === "free") out.ratio = r4(num(v.ratio, 0.05, UNRULED_FLATTEST, 16 / 9));
  const c = v.crop;
  if (c && typeof c === "object") {
    const w = num(c.w, MIN_BOX, 1, 1), h = num(c.h, MIN_BOX, 1, 1);
    const crop = { x: r4(num(c.x, 0, 1 - w, 0)), y: r4(num(c.y, 0, 1 - h, 0)), w: r4(w), h: r4(h) };
    if (crop.w < 1 || crop.h < 1) out.crop = crop;
  }
  if (UNRULED_FITS.includes(v.fit) && v.fit !== "centre") out.fit = v.fit;
  if (UNRULED_FILLS.includes(v.fill) && v.fill !== "blur") out.fill = v.fill;
  return out;
}

// The part of the original (pixels) the frame starts from: the crop, or the whole.
export function baseOf(info, frame) {
  const c = frame && frame.crop;
  const w = info.w, h = info.h;
  return c ? { x: c.x * w, y: c.y * h, w: c.w * w, h: c.h * h } : { x: 0, y: 0, w, h };
}

// The frame's width / height: the whole (or cropped) image's own, a fixed shape's, or the free ratio.
export function aspectOf(info, frame) {
  const f = frame || {};
  if (f.shape === "16:9") return 16 / 9;
  if (f.shape === "banner") return 3;
  if (f.shape === "free" && f.ratio > 0) return f.ratio;
  const b = baseOf(info, f);
  return b.w / b.h;
}

// The part of the original, in pixels, the frame shows: the whole of the base along the side that fits, the focus along the other.
export function regionOf(info, frame) {
  const f = frame || {}, b = baseOf(info, f), ar = aspectOf(info, f);
  const fx = num(f.fx, 0, 1, 0.5), fy = num(f.fy, 0, 1, 0.5);
  if (ar > b.w / b.h) { const h = b.w / ar; return { x: b.x, y: b.y + (b.h - h) * fy, w: b.w, h }; }
  const w = b.h * ar;
  return { x: b.x + (b.w - w) * fx, y: b.y, w, h: b.h };
}

// The pixels of the framed copy: the part shown, at its own size; a small image (its base under the small width) is kept at its base
// width, so it is drawn as wide as it was before the shape cut some of it away (the part is then drawn a little larger).
export function outSize(info, frame) {
  const r = regionOf(info, frame), b = baseOf(info, frame);
  const w = b.w < UNRULED_SMALL_WIDE ? b.w : r.w;
  return { w: Math.max(1, Math.round(w)), h: Math.max(1, Math.round(w * r.h / r.w)) };
}

// Whether the frame shows the whole original (so the framed copy is the original itself).
export function isWhole(info, frame) {
  const r = regionOf(info, frame);
  return r.x < 0.5 && r.y < 0.5 && Math.abs(r.w - info.w) < 1 && Math.abs(r.h - info.h) < 1;
}

// Whether the shape cuts some of the base away (the focus point then matters, and is drawn).
export function cuts(info, frame) {
  const b = baseOf(info, frame), r = regionOf(info, frame);
  return r.w < b.w - 0.5 || r.h < b.h - 0.5;
}

// The width : height a drawn height may have: not flatter than 4:1, not taller than 70 percent of the window.
export function ratioLimits(drawnWide, windowHigh) {
  const hi = UNRULED_FLATTEST;
  const lo = Math.min(hi, drawnWide / Math.max(1, windowHigh * UNRULED_TALLEST));
  return { lo, hi };
}
// A height already taller than the limit is not pulled down by touching the handle: the limit is the window's, or the height it has.
export const ratioFor = (drawnWide, high, windowHigh, was = 0) => {
  const { lo, hi } = ratioLimits(drawnWide, Math.max(windowHigh, was / UNRULED_TALLEST));
  return r4(clamp(drawnWide / Math.max(1, high), lo, hi));
};

// The width the framed image is drawn at, inside a content width: its own size (centred), or all of it when stretched.
export function drawnWide(frame, regionWide, contentWide) {
  return frame && frame.fit === "stretch" ? contentWide : Math.min(contentWide, Math.max(1, Math.round(regionWide)));
}

// ---- the crop box (fractions of the original) --------------------------------------------------------------------------
export const MIN_BOX = 0.05;                                 // the smallest side of a crop box
export const wholeBox = () => ({ x: 0, y: 0, w: 1, h: 1 });
export const startBox = (frame) => (frame && frame.crop) || { x: 0.1, y: 0.1, w: 0.8, h: 0.8 };
const fitBox = (b) => {
  const w = clamp(b.w, MIN_BOX, 1), h = clamp(b.h, MIN_BOX, 1);
  return { x: r4(clamp(b.x, 0, 1 - w)), y: r4(clamp(b.y, 0, 1 - h)), w: r4(w), h: r4(h) };
};
export const moveBox = (b, dx, dy) => fitBox({ ...b, x: b.x + dx, y: b.y + dy });
// Drag one corner ("nw" "ne" "sw" "se") by (dx, dy) fractions; the opposite corner stays where it is.
export function resizeBox(b, corner, dx, dy) {
  let x0 = b.x, y0 = b.y, x1 = b.x + b.w, y1 = b.y + b.h;
  if (corner.includes("w")) x0 = clamp(x0 + dx, 0, x1 - MIN_BOX); else x1 = clamp(x1 + dx, x0 + MIN_BOX, 1);
  if (corner.includes("n")) y0 = clamp(y0 + dy, 0, y1 - MIN_BOX); else y1 = clamp(y1 + dy, y0 + MIN_BOX, 1);
  return fitBox({ x: x0, y: y0, w: x1 - x0, h: y1 - y0 });
}
// Arrow keys: a step of 2 percent moves the box; with Shift it makes the box larger or smaller instead.
export function nudgeBox(b, dx, dy, resize = false) {
  const step = 0.02;
  return resize ? fitBox({ ...b, w: b.w + dx * step, h: b.h + dy * step }) : fitBox({ ...b, x: b.x + dx * step, y: b.y + dy * step });
}
// Apply: the frame with this box as its crop (a box over the whole image is no crop). Use the whole image: the crop taken off.
export const applyCrop = (frame, box) => cleanFrame({ ...frame, crop: box });
export const useWholeImage = (frame) => cleanFrame({ ...frame, crop: undefined });

// ---- the focus (the part a shape keeps in view) ---------------------------------------------------------------------------
// A step of a key press moves the focus 5 percent along the side the shape cuts.
export const nudgeFocus = (frame, key, sign) => cleanFrame({ ...frame, [key]: (frame && typeof frame[key] === "number" ? frame[key] : 0.5) + sign * 0.05 });

// ---- reset ---------------------------------------------------------------------------------------------------------------
export const resetFrame = () => ({});
export const sameFrame = (a, b) => JSON.stringify(cleanFrame(a)) === JSON.stringify(cleanFrame(b));

// ---- the stored body <-> the frame ------------------------------------------------------------------------------------------
const thousandths = (n, lo, hi) => Math.round(clamp(n, lo, hi) * 1000);
// The flat body fields of a frame: every key is given, undefined when it is the default, so saving them takes the old one out.
export function bodyFields(frame) {
  const f = cleanFrame(frame);
  const out = { shape: f.shape, ratio: undefined, fx: undefined, fy: undefined, crop: undefined, fit: f.fit, fill: f.fill };
  if (f.shape === "free") out.ratio = thousandths(f.ratio, 0.25, UNRULED_FLATTEST);
  if (f.fx !== undefined) out.fx = thousandths(f.fx, 0, 1);
  if (f.fy !== undefined) out.fy = thousandths(f.fy, 0, 1);
  if (f.crop) {
    let x0 = Math.round(f.crop.x * 1000), y0 = Math.round(f.crop.y * 1000);
    let x1 = Math.round((f.crop.x + f.crop.w) * 1000), y1 = Math.round((f.crop.y + f.crop.h) * 1000);
    if (x1 - x0 < 10) { x0 = Math.max(0, x1 - 10); x1 = x0 + 10; }
    if (y1 - y0 < 10) { y0 = Math.max(0, y1 - 10); y1 = y0 + 10; }
    out.crop = [x0, y0, x1, y1];
  }
  return out;
}
// The frame a stored body holds (anything it does not hold is the default; a value that is not a whole number in range is ignored).
export function frameOfBody(v) {
  const b = v && typeof v === "object" ? v : {};
  const int = (n, lo, hi) => (Number.isInteger(n) && n >= lo && n <= hi ? n : undefined);
  const raw = { shape: b.shape, fit: b.fit, fill: b.fill };
  const fx = int(b.fx, 0, 1000), fy = int(b.fy, 0, 1000), ratio = int(b.ratio, 250, 4000);
  if (fx !== undefined) raw.fx = fx / 1000;
  if (fy !== undefined) raw.fy = fy / 1000;
  if (ratio !== undefined) raw.ratio = ratio / 1000;
  const c = b.crop;
  if (Array.isArray(c) && c.length === 4 && c.every((n) => Number.isInteger(n) && n >= 0 && n <= 1000) && c[2] - c[0] >= 10 && c[3] - c[1] >= 10) {
    raw.crop = { x: c[0] / 1000, y: c[1] / 1000, w: (c[2] - c[0]) / 1000, h: (c[3] - c[1]) / 1000 };
  }
  return cleanFrame(raw);
}
