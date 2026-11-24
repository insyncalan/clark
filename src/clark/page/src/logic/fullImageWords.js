// Row 1223: every word and number of the Image template (an imagecap section with a body of version 2), in one place. Words
// are ruled. "image", never "picture", on
// screen. Pure: no DOM, no Preact; the page's Edit and View parts and the tests read it.

// The body keys are the framing's (logic/fullImageFrame.js says how a frame is stored). The slots: pictures.original is what the person
// added; pictures.image is the framed copy clark makes from it (the page never sends it).
export const SLOT_FRAMED = "image";
export const SLOT_ORIGINAL = "original";
export const SHAPES = ["whole", "16:9", "banner", "free"];
export const FITS = ["centre", "stretch"];
export const FILLS = ["blur", "brand", "plain"];

// Numbers: the print width (300 dpi across about 257 mm), the small-image width, the flattest and tallest a height may be.
export const PRINT_WIDE = 3000;
export const SMALL_WIDE = 600;
export const FLATTEST = 4;               // width : height, at most
export const TALLEST = 0.7;              // of the window's height
export const MOST_BYTES = 3 * 1024 * 1024;   // the original and the framed copy, each, decoded (imagecap.py ORIGINAL_MAX, FRAMED_MAX)
export const PAGE_INCHES = 257 / 25.4;   // the content width of A4 landscape

export const WORDS = {
  name: "Image",
  description: "One image, framed as you choose, with an optional caption.",
  holds: ["Image", "Caption (optional)"],
  hint: "Choose an image. Until then this section stays out of the published report.",
  choose: "Choose an image",
  drop: "or drop one here",
  making: "Making the image ready…",
  added: "Image added.",
  removed: "Image taken out.",
  framed: "Image framing saved.",
  replaced: "Image replaced.",
  describe: "Describe the image",
  describeNote: "Add a description, so someone who cannot see the image knows what it shows.",
  caption: "Caption",
  addCaption: "+ Add a caption",
  removeCaption: "Remove caption",
  captionSaved: "Caption saved.",
  altSaved: "Description saved.",
  toolbar: "Image tools",
  shape: { whole: "Whole image", "16:9": "Shape 16:9", banner: "Strip 3:1", free: "Free height" },
  shapeTip: { whole: "Whole: the image as it is", "16:9": "16:9: a wide screen shape", banner: "Strip 3:1: a wide, low strip", free: "Free: drag the handle to set the height" },
  crop: "Crop...",
  cropTip: "Crop: choose the part to keep",
  reset: "Reset",
  resetTip: "Reset: back to the whole image",
  centre: "Centre at its own size",
  stretch: "Stretch to full width",
  fill: { blur: "Fill with a blurred copy", brand: "Fill with the brand colour", plain: "Fill plain" },
  replace: "Replace image",
  remove: "Remove image",
  focus: "Focus point",
  focusHelp: "Drag, or use the arrow keys: what stays in view when the shape cuts some of the image away.",
  height: "Image height",
  cropBox: "Crop box",
  cropHelp: "Drag the box or its corners. Arrow keys move it; with Shift they resize it.",
  corner: { nw: "Crop box, top left corner", ne: "Crop box, top right corner", sw: "Crop box, bottom left corner", se: "Crop box, bottom right corner" },
  cropped: "Image cropped.",
  resetDone: "Image back to the whole image.",
  across: (n) => `${n} percent across`,
  down: (n) => `${n} percent down`,
  pixels: (n) => `${n} pixels`,
  total: (mb) => `Images in this report: ${mb} MB of the 5 MB a published page can hold, with everything else on it.`,
  totalNear: " That is close to the most. Take an image out or add smaller ones, or Publish will refuse the page.",
  apply: "Apply",
  cancel: "Cancel",
  whole: "Use the whole image",
  notAnImage: "That file isn't an image that can go in the report. Choose a PNG, JPEG or WebP image.",
  unreadable: "That image could not be read. Choose another one.",
  tooBig: "That image is too large, even made smaller. Choose a smaller one.",
  notFramed: "The image could not be framed. Nothing was changed.",
};

const px = (n) => Math.round(n).toLocaleString("en-GB");

// The note under the toolbar: what the file is and what happened to it. `info` is the body's info; `framedWide` the framed copy's width.
export function fileNote(info, framedWide) {
  if (!info || !info.w) return "";
  const from = info.from && info.from > info.w ? info.from : 0;
  const wide = framedWide || info.w;
  if (from) return `${px(from)} px, made smaller for print to ${px(info.w)} px`;
  if (wide < SMALL_WIDE) return `${px(wide)} px: it sits centred at its own size, not stretched.`;
  const dpi = Math.round(wide / PAGE_INCHES / 10) * 10;
  if (dpi >= 300) return `${px(wide)} px: sharp, about ${dpi} dpi if printed full width.`;
  return `${px(wide)} px: sharp on screen, about ${dpi} dpi if printed full width, below the 300 dpi target`;
}
