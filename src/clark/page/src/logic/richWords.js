// Item 1005: the words of a field that moved onto the one rich editor, for the places that show plain text (a card's words, the search).
// A value that is the editor's HTML (what the server stores, or the published file carries, is already cleaned: its text is escaped
// and it holds only the allowed tags) is reduced to its text; anything else is an old plain text and is returned as it is. The result
// is text for a text node or a search, never markup. No cleaner here: the published page carries this file, and the editor's cleaner stays out of it.
export const HTML_START = /^[ \t\n\r\f\v]*<(?:p|h[123]|ul|ol|blockquote|hr)[ \t\n\r\f\v/>]/i;

export function richWords(value) {
  const s = value == null ? "" : String(value);
  if (!HTML_START.test(s)) return s;
  return s.replace(/<\/?(?:p|h[123]|ul|ol|li|blockquote)(?=[\s/>])[^>]*>|<(?:br|hr)\s*\/?>/gi, "\n").replace(/<[^>]*>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&nbsp;/g, "\u00a0").replace(/&amp;/g, "&").replace(/\n{2,}/g, "\n").trim();
}
