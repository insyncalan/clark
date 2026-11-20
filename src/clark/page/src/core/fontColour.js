// Row 1364: the font colour mark of the one rich editor. Its value is one of six names (the same fixed set the cleaners keep, logic/cleanHtml.js
// FONT_COLOURS); it is written as <span class="rt-c-<name>"> (core/richHtml.js) and drawn by the Theme's rules.css from the theme's own tokens, so
// a colour follows the theme and no hex is ever stored. Automatic is no mark at all.
import { Mark, mergeAttributes } from "tiptap";
import { FONT_COLOURS } from "../logic/cleanHtml.js";

export const FONT_COLOUR_NAMES = FONT_COLOURS;
/** [name, words] for the palette, in its order. The words are the swatch's tooltip and name. */
export const SWATCHES = [["grey", "Grey"], ["brand", "Brand"], ["red", "Red"], ["amber", "Amber"], ["green", "Green"], ["blue", "Blue"]];

const fromClass = (el) => {
  const m = /^rt-c-([a-z]+)$/.exec(el.getAttribute("class") || "");
  return m && FONT_COLOURS.includes(m[1]) ? m[1] : null;
};

export const FontColour = Mark.create({
  name: "fontColour",
  addAttributes: () => ({ colour: { default: null, parseHTML: fromClass, renderHTML: (a) => (a.colour ? { class: `rt-c-${a.colour}` } : {}) } }),
  parseHTML: () => [{ tag: "span", getAttrs: (el) => (fromClass(el) ? {} : false) }],
  renderHTML: ({ HTMLAttributes }) => ["span", mergeAttributes(HTMLAttributes), 0],
});
