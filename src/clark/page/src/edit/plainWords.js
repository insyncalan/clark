// Item 1005: some fields moved onto the one editor (RichField) but are still stored, published and exported as plain text (a milestone's
// Client wording, a picture's caption). The editor hands back HTML; this turns it into the plain text those fields keep: one line per
// paragraph or list item, or with `oneLine` all of it on one line (a caption is one line). Never markup.  The next-line character (U+0085) is not a space to the
// browser, so it is named here: one line never holds a line break of any kind.
import { richWords } from "../logic/richWords.js";

export function plainFromEditor(html, oneLine = false) {
  const text = richWords(html == null ? "" : String(html)).replace(/\r\n?/g, "\n");
  return (oneLine ? text.replace(/[\s\u0085]+/g, " ") : text.split("\n").map((l) => l.replace(/[ \t]+$/, "")).join("\n")).trim();
}
