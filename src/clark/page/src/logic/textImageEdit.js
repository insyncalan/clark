// Row 1232, Text and Image Side by Side (a textimage section with a body of version 2): what its Edit toolbar offers and the words on it,
// in one place. Pure: no DOM, no Preact; the Edit part and the tests read it. The names are the approved ones (the measured spec, rows 7 to 11).
// Position follows the section width: a full width section puts the image left or right (`side`) and takes a share of the width (`share`);
// a half width section puts it on top or underneath (`half`). Each width keeps its own choice, so only the keys of the width in use are written.
export const SIDES = ["left", "right"];
export const HALVES = ["top", "bottom"];
export const SHARES = ["third", "half", "two"];
export const SHAPES = ["fill", "4:3", "square", "whole"];

export const TOOLBAR = "Image and layout tools";
export const GROUP = { shape: "Shape", position: "Where the image sits", share: "Image width" };
export const NAMES = {
  fill: "Fill the height of the text", wide: "Wide (16:9)", "4:3": "Shape 4:3", square: "Shape square", whole: "Whole image",
  left: "Image on the left", right: "Image on the right", top: "Image on top", bottom: "Image underneath", swap: "Swap image and text",
  third: "Image takes a third", half: "Image takes a half", two: "Image takes two thirds",
  replace: "Replace the image", remove: "Remove the image",
};
export const FIELDS = {
  heading: "Heading", optional: "optional", text: "Text", describe: "Describe the image", describeHint: "for people who cannot see it",
  noDescription: "No description yet.", caption: "Caption",
};

// The width the section is drawn at: a section that shares its row is half width.
export const isHalf = (slot) => slot === "left" || slot === "right";

// The choices of the Position group for this width, in the order drawn: [{ key, field, value }].
export const positions = (half) => (half ? HALVES.map((k) => ({ key: k, field: "half", value: k })) : SIDES.map((k) => ({ key: k, field: "side", value: k })));

// What is chosen now (the stored defaults: the image on the right, on top, a half wide, filling the height).
export function chosen(v) {
  const b = v && typeof v === "object" ? v : {};
  return {
    side: b.side === "left" ? "left" : "right",
    half: b.half === "bottom" ? "bottom" : "top",
    share: b.share === "third" || b.share === "two" ? b.share : "half",
    shape: SHAPES.includes(b.shape) ? b.shape : "fill",
  };
}

// The stored fields that set one choice. The stored default is "nothing" (""), which takes the key out of the body.
const DEFAULT = { side: "right", half: "top", share: "half", shape: "fill" };
export const setting = (field, value) => ({ [field]: value === DEFAULT[field] ? "" : value });

// Swap: the other choice of this width's two, as the fields to store.
export function swapped(v, half) {
  const c = chosen(v);
  return half ? setting("half", c.half === "top" ? "bottom" : "top") : setting("side", c.side === "left" ? "right" : "left");
}

// The Shape group: the first choice is Fill the height of the text at full width and Wide (16:9) at half width (Fill the height is Wide when the text is not beside it).
export const shapes = (half) => SHAPES.map((k) => ({ key: k, name: k === "fill" && half ? NAMES.wide : NAMES[k], icon: k === "fill" && half ? "16:9" : k }));

// The words under the toolbar: the size of the file the person added and what was done to it (the print cap, 3,000 px at 300 dpi).
export const PRINT_WIDE = 3000;
export const px = (n) => Math.round(n).toLocaleString("en-GB");
export const fileNote = (w, h) => (w && h ? `${px(w)} × ${px(h)} px file. Made smaller for print to ${px(PRINT_WIDE)} px at most (300 dpi). The published page carries only the part you see.` : "");
