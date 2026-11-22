// Row 1233 (gal 2): the words and numbers of the Image gallery's Classic Edit part (edit/templates/GalleryClassic.jsx), in one place. The words are the
// ruled ones (the approved mock-up's, and the product rulings on #1233 of 20-11); the rest wait for approval in handover/newwords-1233-gal.md.
// "image", never "picture", on screen. Pure: no DOM, no Preact; the page and the tests read it.
export const MOST = 6;                       // gallery.py SLOTS
export const FILE_MB = 10;                   // server.py IMAGE_FILE_MB, gallery.py PICTURE_MAX
export const PRINT_WIDE = 1600;              // gallery.py WIDTH_MAX
export const MOST_BYTES = 1024 * 1024;       // gallery.py ORIGINAL_MAX, decoded
export const COLUMNS = [2, 3];
export const SHAPES = ["4:3", "square", "16:9", "whole"];

export const WORDS = {
  toolbar: "Gallery tools",
  selected: "Selected image",
  replace: "Replace the selected image",
  remove: "Remove the selected image",          // gal 3: the toolbar bin (new word, newwords C)
  binTitle: "Remove this image",              // gal 3: the title of the bin on a tile (spec row 8)
  moveTitle: "Drag to move",                  // gal 4: the title of the dots on a tile (spec row 7)
  moveName: (n) => `Move image ${n}`,        // gal 4: their accessible name (spec row 7)
  binName: (n) => `Remove image ${n}`,       // gal 3: its accessible name (spec row 8)
  removed: "Image removed.",                  // gal 3: the 1232 approved word (textImageSideWords.js); the toast carries Undo
  add: "Add an image",
  full: "Six is the most",
  tile: "Add an image",
  empty: "Choose images, or drop them here (up to six)",   // AP6 (spec row 6, ruled)
  describe: (n) => `Selected image ${n}: describe it`,
  describeHint: "for people who cannot see it",
  redTitle: "No description yet",            // AP9: the title of the red mark on a tile (spec row 9, ruled)
  noDescription: "No description yet.",
  caption: "Caption",
  optional: "optional",
  note: (n) => `${n} of ${MOST} images. Each is made smaller to keep the file light (up to ${PRINT_WIDE.toLocaleString("en-GB")} px wide). The published page carries only the part you see in each tile.`,
  seventh: "A gallery holds up to six images. Remove one to add another.",
  some: (taken, given) => `Added ${taken} of the ${given} files. A gallery holds up to six images.`,
  tooBig: `That file is too big. Choose one under ${FILE_MB} MB.`,
  added: "Image added.",
  replaced: "Image replaced.",
  making: "Making the image ready…",
  select: (n) => `Image ${n}`,
};
