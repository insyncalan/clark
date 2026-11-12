// Item 1005: a field the store keeps as one line of plain text (the Movement form's Who agreed it, Reason and Source; a RAID card's
// Own words) is typed in the one editor. What the editor gives back (its HTML) is reduced to its words, the paragraphs joined by a
// space and the spaces made single, because the store refuses a line break there. Text for a text node, never markup.
import { richWords } from "./richWords.js";

export function plainLine(html) {
  return richWords(html).replace(/[\s\u0085]+/g, " ").trim();
}
