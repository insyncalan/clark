// Row 1233 (the Image gallery's Edit page): the words and numbers, in one place. Words are ruled (the approved 1233 lines in NEW-WORDS);
// the numbers in them come from the constants here, never typed into the text. "image", never "picture", on screen. Pure: no DOM.
import { STARTING_TEXT } from "../edit/startingText.js";
export const SLOTS = ["1", "2", "3", "4", "5", "6"];
export const MOST_IMAGES = SLOTS.length;
export const PICTURE_MAX = 10 * 1024 * 1024;       // gallery.py PICTURE_MAX: what a person may add (decoded)
export const ORIGINAL_MAX = 1024 * 1024;           // gallery.py ORIGINAL_MAX: what the page sends (a larger PNG is made smaller in steps)
export const WIDTH_MAX = 1600;                     // gallery.py WIDTH_MAX: px wide at most
export const V1_LONGEST = 1200;                    // a version 1 body keeps its 1.0.7 limits (gallery.py V1_PICTURE_MAX)
export const V1_MOST = 400 * 1024;
export const FILE_MB = PICTURE_MAX / (1024 * 1024);
export const SHAPES = { "4:3": "s43", square: "s11", "16:9": "s169", whole: "swhole" };

// The slots that hold an image, in the order shown: a version 2 body's `order`, then the rest in slot order.
export function shownSlots(v, pics) {
  const said = v && v.v === 2 && Array.isArray(v.order) ? v.order.filter((s) => SLOTS.includes(s)) : [];
  return [...new Set([...said, ...SLOTS])].filter((s) => typeof pics[s] === "string" && pics[s]);
}
export const freeSlots = (pics) => SLOTS.filter((s) => !(typeof pics[s] === "string" && pics[s]));

export const WORDS = {
  empty: STARTING_TEXT.gallery.empty[0],           // the one line of the empty area; ruled in startingText.js (Row 1251), not typed twice
  addTile: "Add an image",
  full: "A gallery holds up to six images. Remove one to add another.",
  tooBig: (mb = FILE_MB) => `That file is too big. Choose one under ${mb} MB.`,
  partial: (added, files, full) => `Added ${added} of the ${files} files.${full ? " A gallery holds up to six images." : ""}`,   // the second sentence only when the gallery is now full
  count: (n) => `${n} of ${MOST_IMAGES} images. Each is made smaller to keep the file light (up to ${WIDTH_MAX.toLocaleString("en-GB")} px wide). The published page carries only the part you see in each tile.`,
  tile: (n) => `Image ${n}`,
  describe: (n) => `Selected image ${n}: describe it`,
  describeHint: "for people who cannot see it",
  noDescription: "No description yet.",
  caption: "Caption",
  optional: "optional",
  added: "Image added.",
  making: "Making the image ready…",
  altSaved: "Description saved.",
  captionSaved: "Caption saved.",
};
