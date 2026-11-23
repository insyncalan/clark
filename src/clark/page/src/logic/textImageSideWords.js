// Row 1232 (the words are ruled and approved, the mock-up's text; listed in NEW-WORDS-1232.md). Text and Image Side by Side, Edit only. Pure: no DOM, no Preact; the Edit part and the tests read it.
export const PRINT_WIDE = 3000;            // row 1232: the print cap, 300 dpi (the ticket allows a lower one for this template; none chosen)
export const SLOT_ORIGINAL = "original";

export const WORDS = {
  toolbar: "Image and layout tools",
  groups: { shape: "Shape", where: "Where the image sits", width: "Width of the image", crop: "Crop" },
  fill: "Fill the height of the text",
  wide: "Wide (16:9)",
  shape: { "4:3": "Shape 4:3", square: "Shape square", whole: "Whole image" },
  place: { left: "Image on the left", right: "Image on the right", top: "Image on top", bottom: "Image underneath" },
  swap: "Swap image and text",
  share: { third: "Image takes a third", half: "Image takes a half", two: "Image takes two thirds" },
  crop: "Crop…",
  reset: "Reset framing",
  replace: "Replace the image",
  remove: "Remove the image",
  heading: "Heading",
  optional: "optional",
  text: "Text",
  describe: "Describe the image",
  describeHint: "for people who cannot see it",
  noDescription: "No description yet.",
  caption: "Caption",
  focus: "Focus point: what stays in view",
  empty: "Add some words, an image or both. Until then this section stays out of the published page.",
  choose: "Choose an image",
  drop: "or drop one here",
  making: "Making the image ready…",
  added: "Image added.",
  removed: "Image removed.",
  replaced: "Image replaced.",
  framed: "Image framing saved.",
  cropped: "Image cropped.",
  resetDone: "Image back to the whole image.",
  moved: "Image moved.",
  swapped: "Image and text swapped.",
  headingSaved: "Heading saved.",
  captionSaved: "Caption saved.",
  altSaved: "Description saved.",
  notFramed: "The image could not be framed. Nothing was changed.",
};
export const HELP = "Text and Image Side by Side: words beside a picture. Choose the picture, then use Image and layout tools to set its shape, its side and its width, to crop it, and to describe it for people who cannot see it.";
const px = (n) => Math.round(n).toLocaleString("en-GB");
// The note under the toolbar: the file, and what happened to it.
export const fileNote = (w, h) => `${px(w)} × ${px(h)} px file. Made smaller for print to ${px(PRINT_WIDE)} px at most (300 dpi). The published page carries only the part you see.`;

// What the Edit part offers for a width: the two places, the three shares (full only), the first shape's words.
export const placesFor = (half) => (half ? ["top", "bottom"] : ["left", "right"]);
export const SHARES = ["third", "half", "two"];
export const SHAPES = ["fill", "4:3", "square", "whole"];
// The body key a place is saved under, and its value ("" = the default, so the key is taken out).
export const placeField = (place) => (place === "left" ? { side: "left" } : place === "right" ? { side: "" } : place === "bottom" ? { half: "bottom" } : { half: "" });
export const placeOf = (v, half) => (half ? (v.half === "bottom" ? "bottom" : "top") : (v.side === "left" ? "left" : "right"));
export const swapped = (place) => ({ left: "right", right: "left", top: "bottom", bottom: "top" })[place];
// Shapes that clark cuts (it needs a PNG original for them, and for a crop).
export const cuts = (shape, crop) => shape === "4:3" || shape === "square" || !!crop;
