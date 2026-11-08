// What the Files and links templates' Edit parts send (#96): the whole content of the section in one change (one step, one Undo,
// place "report"), and the checks made before it is sent, in the store's own words (src/clark/section_kinds/doclinks.py, onedoc.py,
// linkcard.py), so a person reads why and what to do instead of a general refusal. Pure but for change().
import { change } from "../../stores/changes.js";
import { contentOf } from "../../templates/files.js";

export const LABEL_MAX = 120;
export const BAD_LABEL = `Words for a file or link must be one line of ${LABEL_MAX} characters at most. Shorten them and try again.`;

// The stored content of a section of `type`, as an object to change (never the page's guess: the body clark sent).
export function stored(section) {
  const c = contentOf(section);
  return c && c.v === 1 ? c : { v: 1 };
}

// Typed words made storable: one line, tabs and line breaks as spaces, spaces at the ends dropped.
export const oneLine = (text) => String(text || "").replace(/[\t\r\n]+/g, " ").trim();
// A box of words as paragraphs: one per line, empty lines dropped.
export const paragraphsOf = (text) => String(text || "").split(/\r?\n/).map(oneLine).filter(Boolean);

// The words of a card or a note as the editor opens them: its HTML, or (a section saved by an older clark) its lines made into paragraphs.
const escaped = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
// A line break in HTML is a space; the section's content may hold none (the store refuses one in any field), so none is sent.
export const noBreaks = (html) => String(html || "").replace(/[\r\n]+/g, " ");
export function wordsAsHtml(html, lines) {
  if (typeof html === "string" && html.trim()) return html;
  return (Array.isArray(lines) ? lines : []).filter((t) => typeof t === "string" && t.trim()).map((t) => `<p>${escaped(t)}</p>`).join("");
}

// "" when `items` are at most `most` paragraphs of at most `each` characters; else the words `refusal`.
export function linesProblem(list, most, each, refusal) {
  return list.length > most || list.some((p) => Array.from(p).length > each) ? refusal : "";
}
export const labelProblem = (text) => (Array.from(text).length > LABEL_MAX ? BAD_LABEL : "");

// Save `content` as the section's whole content: resolves to the reply, or null when nothing was saved (the toast says why).
export function saveContent(section, content, words) {
  return change({ op: "update", id: section.id, changes: { body: JSON.stringify({ ...content, v: 1 }) }, place: "report" }, words);
}
