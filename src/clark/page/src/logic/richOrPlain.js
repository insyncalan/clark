// Item 1005: a field that moved onto the one rich editor keeps its column, so an old row holds plain text and a new one holds the
// editor's HTML. This is the page's copy of sanitise.rich_or_plain (tests/test_rich_or_plain_parity.py runs both over a corpus and
// compares byte for byte): a stored value is HTML when it starts with one of the tags the cleaner's output starts with, anything
// else is plain text and is escaped into one paragraph per line. Either way the result is cleanHtml of it, never the stored text.
import { cleanHtml } from "./cleanHtml.js";
import { HTML_START } from "./richWords.js";

// Python's `[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff]`, as cleanHtml and the server strip it.
const CONTROL = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff]/gu;       // eslint-disable-line no-control-regex
export { HTML_START };

const escapeText = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;");

/** Plain text as HTML: every character escaped, one paragraph per line (a blank line is an empty paragraph). */
export function legacyToHtml(text) {
  if (text == null) return "";
  const lines = String(text).replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/^\n+|\n+$/g, "").split("\n");
  return /[^\s]|\ufeff/.test(lines.join("")) ? lines.map((l) => `<p>${escapeText(l)}</p>`).join("") : "";
}

/** A stored rich-or-legacy value as clean HTML ("" for none). Throws SanitiseError as cleanHtml does. */
export function richOrPlain(value) {
  if (value == null || value === "") return "";
  if (typeof value !== "string") return cleanHtml(value);
  return cleanHtml(HTML_START.test(value) ? value : legacyToHtml(value.replace(CONTROL, "")));
}
