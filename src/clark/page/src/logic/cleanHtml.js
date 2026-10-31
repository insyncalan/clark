// The page's copy of the rich-text cleaner (#66): a port of src/clark/sanitise.py, step for step, so that cleanHtml(x) is the same
// string as sanitise.clean_html(x) for every x (tests/test_clean_html_parity.py runs both over a large corpus and compares byte
// for byte). Python is the authority: the store cleans on every save, and this copy only lets the editor show what will be kept.
// Not a DOMParser filter on purpose: a browser's parser is a different, changing parser, and the two copies must not disagree.
//
// Plain JS, no library, no DOM. Where Python and JavaScript differ the port says so: strings here are UTF-16, so lengths are
// counted in code points; Unicode tables are never taken from the browser (sanitiseTables.js holds Python's, as numbers); and
// the places where Python's case-insensitive match is wider than JavaScript's (dotless i, long s) are written out.
import { ENTITIES, LEGACY, BAD_ADDRESS } from "./sanitiseTables.js";

export const MAX_CHARS = 200000;      // the longest field accepted, and the longest result
const MAX_DEPTH = 50;                 // open tags nested deeper than this are removed (their text stays)
const MAX_HREF = 8000;
const MAX_BLANK_RUN = 5;              // blank lines (empty paragraphs) in a row that are kept; a longer run is cut to this (#84)

const set = (words) => new Set(words.split(" "));
const ALLOWED = set("p br strong em s h1 h2 h3 ul ol li blockquote hr a input");
const VOID = set("br hr input");
const INLINE = set("strong em s a");
const PARAGRAPH = set("p h1 h2 h3");
const ENDS_PARAGRAPH = set("p h1 h2 h3 ul ol li blockquote hr");
const DROP_WITH_CONTENT = set("script style iframe object applet form svg math template noscript noembed noframes textarea select title xmp plaintext head");
const BLOCKS = set("address article aside caption center dd details dialog dir div dl dt fieldset figcaption figure footer form h4 h5 h6 header hgroup legend listing main menu nav optgroup option pre section summary table tbody td tfoot th thead tr");
const BREAKING = set("p br h1 h2 h3 ul ol li blockquote hr");     // ALLOWED - INLINE - {input}: the written tags that start a line
const EMPTY_FOREIGN = set("svg math");
const RAW_TEXT = set("script style textarea title xmp iframe noembed noframes noscript plaintext");
const BREAKS = set("p br h1 h2 h3 ul ol li blockquote hr");
const SPACE = " \t\n\r\f";

// The cleaner's error: a field too long, or not text. The message is Python's, word for word.
export class SanitiseError extends Error {
  constructor(message) {
    super(message);
    this.name = "SanitiseError";
  }
}

// ----- Python's own rules, written out
// Python's `re.I` is Unicode-aware and wider than JavaScript's: i also matches U+0130 and U+0131, s matches U+017F, k matches
// U+212A (checked over every code point on 3.9 and 3.15). The patterns below spell those out instead of using the i flag.
const WIDER = { i: "\u0130\u0131", s: "\u017f", k: "\u212a" };
const ci = (word) => word.replace(/[a-z]/g, (c) => `[${c}${c.toUpperCase()}${WIDER[c] || ""}]`);

// str.isspace(): what Python's strip() removes (JavaScript's trim() differs: it takes U+FEFF and leaves U+001C-U+001F, U+0085).
const isPySpace = (n) => (n >= 9 && n <= 13) || (n >= 0x1c && n <= 0x20) || n === 0x85 || n === 0xa0 || n === 0x1680 ||
  (n >= 0x2000 && n <= 0x200a) || n === 0x2028 || n === 0x2029 || n === 0x202f || n === 0x205f || n === 0x3000;

function pyStrip(s) {
  let a = 0, b = s.length;
  while (a < b && isPySpace(s.charCodeAt(a))) a++;
  while (b > a && isPySpace(s.charCodeAt(b - 1))) b--;
  return s.slice(a, b);
}

// len(): code points, not UTF-16 units. (Up to MAX_CHARS units can never be more than that many code points.)
function codePoints(s) {
  let n = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff && i + 1 < s.length && (s.charCodeAt(i + 1) & 0xfc00) === 0xdc00) i++;
    n++;
  }
  return n;
}

const withCommas = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

function checkLength(n, tidied) {
  if (n > MAX_CHARS) {
    if (tidied) {
      throw new SanitiseError(`That text is too long: it comes to ${withCommas(n)} characters once it is tidied up for saving (a symbol such as & takes more room then), and the most one field can hold is ${withCommas(MAX_CHARS)}.`);
    }
    throw new SanitiseError(`That text is too long: it is ${withCommas(n)} characters as written, and the most one field can hold is ${withCommas(MAX_CHARS)}.`);
  }
}

const isAsciiAlpha = (c) => c.length === 1 && ((c >= "a" && c <= "z") || (c >= "A" && c <= "Z"));
const isAsciiAlnum = (c) => isAsciiAlpha(c) || (c.length === 1 && c >= "0" && c <= "9");

// ----- Escaping and addresses
const CONTROL = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff]/gu;    // u: only a lone surrogate matches, never half of a pair
const ADDRESS = new RegExp(`^(?:${ci("http")}${ci("s")}?://[^/?#]|${ci("mailto")}:[^\\n]|#)`);

const textEscape = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\xa0/g, "&nbsp;");
const attrEscape = (t) => t.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function badInAddress(n) {
  let lo = 0, hi = BAD_ADDRESS.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1, r = BAD_ADDRESS[mid];
    if (n < r[0]) hi = mid - 1;
    else if (n > r[1]) lo = mid + 1;
    else return true;
  }
  return false;
}

// The address a link may point to, tidied, or null (sanitise.href).
export function href(value) {
  if (value === null || value === undefined) return null;
  const v0 = value.replace(/[\t\n\r]/g, "");
  let a = 0, b = v0.length;                                    // strip every character up to U+0020 from both ends (a loop: a
  while (a < b && v0.charCodeAt(a) <= 32) a++;                 // regex for this is slow on a long run of spaces)
  while (b > a && v0.charCodeAt(b - 1) <= 32) b--;
  const v = v0.slice(a, b);
  if (!v || (v.length > MAX_HREF && codePoints(v) > MAX_HREF) || !ADDRESS.test(v)) return null;
  for (const c of v) {
    if (badInAddress(c.codePointAt(0))) return null;
  }
  return v.split(" ").join("%20");
}

// ----- Character references (html.unescape and the attribute rule, with Python's table)
const INVALID_CHARREFS = new Map([[0x00, "\ufffd"], [0x0d, "\r"], [0x80, "\u20ac"], [0x81, "\x81"], [0x82, "\u201a"], [0x83, "\u0192"],
  [0x84, "\u201e"], [0x85, "\u2026"], [0x86, "\u2020"], [0x87, "\u2021"], [0x88, "\u02c6"], [0x89, "\u2030"], [0x8a, "\u0160"],
  [0x8b, "\u2039"], [0x8c, "\u0152"], [0x8d, "\x8d"], [0x8e, "\u017d"], [0x8f, "\x8f"], [0x90, "\x90"], [0x91, "\u2018"],
  [0x92, "\u2019"], [0x93, "\u201c"], [0x94, "\u201d"], [0x95, "\u2022"], [0x96, "\u2013"], [0x97, "\u2014"], [0x98, "\u02dc"],
  [0x99, "\u2122"], [0x9a, "\u0161"], [0x9b, "\u203a"], [0x9c, "\u0153"], [0x9d, "\x9d"], [0x9e, "\u017e"], [0x9f, "\u0178"]]);

function invalidCodepoint(n) {                                  // removed outright: controls, and the noncharacters
  return (n >= 1 && n <= 8) || n === 0x0b || (n >= 0x0e && n <= 0x1f) || (n >= 0x7f && n <= 0x9f) || (n >= 0xfdd0 && n <= 0xfdef) ||
    ((n & 0xfffe) === 0xfffe && n <= 0x10ffff);
}

const inTable = (name) => (name.endsWith(";") ? ENTITIES.has(name.slice(0, -1)) : LEGACY.has(name));
const valueOf = (name) => ENTITIES.get(name.endsWith(";") ? name.slice(0, -1) : name);

// html._replace_charref: `s` is what follows the "&".
function replaceCharref(s) {
  if (s[0] === "#") {
    const num = s[1] === "x" || s[1] === "X" ? parseInt(s.slice(2).replace(/;$/, ""), 16) : parseInt(s.slice(1).replace(/;$/, ""), 10);
    if (INVALID_CHARREFS.has(num)) return INVALID_CHARREFS.get(num);
    if ((num >= 0xd800 && num <= 0xdfff) || num > 0x10ffff) return "\ufffd";
    if (invalidCodepoint(num)) return "";
    return String.fromCodePoint(num);
  }
  if (inTable(s)) return valueOf(s);
  const cps = Array.from(s);                                    // the longest name that is in the table
  for (let x = cps.length - 1; x > 1; x--) {
    const head = cps.slice(0, x).join("");
    if (LEGACY.has(head)) return ENTITIES.get(head) + cps.slice(x).join("");
  }
  return "&" + s;
}

const REFERENCE = /&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)/gu;       // u: {1,32} counts code points, as in Python
const HUGE_NUMBER = /&#(?:[0-9]{9,}|[xX][0-9a-fA-F]{9,});?/g;

// One reference in an attribute value: a name without its semicolon is left as written when the next character is "=" or an
// ASCII letter or digit (`&region=eu` in an address is not "(R)ion=eu").
function attributeReference(whole, name) {
  if (name[0] === "#" || inTable(name)) return replaceCharref(name);
  const cps = Array.from(name);
  for (let size = cps.length - 1; size > 1; size--) {
    if (LEGACY.has(cps.slice(0, size).join(""))) {
      const following = cps[size];                              // size < length, so there is always one
      if (following === "=" || isAsciiAlnum(following)) return whole;
      return ENTITIES.get(cps.slice(0, size).join("")) + cps.slice(size).join("");
    }
  }
  return whole;
}

function decode(text, attribute) {
  if (!text.includes("&")) return text;
  text = text.replace(HUGE_NUMBER, "\ufffd");
  return attribute ? text.replace(REFERENCE, attributeReference) : text.replace(REFERENCE, (whole, name) => replaceCharref(name));
}

// ----- Reading the markup (one pass, each step moves forward)
const TAG_NAME = /[a-zA-Z][^ \t\n\r\f/>]*/y;
const SPACES_AND_SLASHES = /[ \t\n\r\f/]*/y;
const SPACES = /[ \t\n\r\f]*/y;
const ATTR_NAME = /[^ \t\n\r\f/>][^ \t\n\r\f/>=]*/y;
const UNQUOTED = /[^ \t\n\r\f>]*/y;
const RAW_END = {};
for (const name of RAW_TEXT) RAW_END[name] = new RegExp(`</${ci(name)}(?=[ \\t\\n\\r\\f/>])`, "g");
const COMMENT_END = /--!?>/g;

function at(re, text, pos) {                                    // re.match(text, pos) for a sticky pattern
  re.lastIndex = pos;
  return re.exec(text);
}

function search(re, text, pos) {                                // re.search(text, pos) for a global pattern
  re.lastIndex = pos;
  return re.exec(text);
}

// The attributes of the tag whose name has just ended at `pos`: [attrs, selfClosing, position after the ">"], or null if the text
// ends first.
function readTag(text, pos) {
  const attrs = [], n = text.length;
  for (;;) {
    const end = pos + at(SPACES_AND_SLASHES, text, pos)[0].length;
    if (end >= n) return null;
    if (text[end] === ">") return [attrs, text[end - 1] === "/" && end > pos, end + 1];
    const m = at(ATTR_NAME, text, end);
    const name = m[0].toLowerCase();
    pos = end + m[0].length;
    let after = pos + at(SPACES, text, pos)[0].length;
    let value = "";
    if (after < n && text[after] === "=") {
      after += 1;
      after += at(SPACES, text, after)[0].length;
      if (after >= n) return null;
      if (text[after] === '"' || text[after] === "'") {
        const close = text.indexOf(text[after], after + 1);
        if (close < 0) return null;
        value = text.slice(after + 1, close);
        pos = close + 1;
      } else {
        const u = at(UNQUOTED, text, after);
        value = u[0];
        pos = after + u[0].length;
      }
    }
    attrs.push([name, decode(value, true)]);
  }
}

// The markup in `text` as emit("text", raw), emit("start", name, attrs, selfClosing) and emit("end", name).
function tokens(text, emit) {
  let pos = 0;
  const n = text.length;
  while (pos < n) {
    const lt = text.indexOf("<", pos);
    if (lt < 0) {
      emit("text", text.slice(pos));
      return;
    }
    if (lt > pos) emit("text", text.slice(pos, lt));
    pos = lt + 1;
    const nxt = text.slice(lt + 1, lt + 2);
    const after = text.slice(lt + 2, lt + 3);                   // what follows `</`
    if (text.startsWith("!--", pos)) {
      pos += 3;
      if (text.startsWith(">", pos) || text.startsWith("->", pos)) {          // `<!-->` and `<!--->` are whole comments
        pos += 1 + (text[pos] === "-" ? 1 : 0);
        continue;
      }
      const m = search(COMMENT_END, text, pos);
      pos = m ? m.index + m[0].length : n;
    } else if (nxt === "/" && after === ">") {                  // `</>`
      pos += 2;
    } else if (nxt === "!" || nxt === "?" || (nxt === "/" && !isAsciiAlpha(after))) {
      const close = text.indexOf(">", pos);                     // a bogus comment, up to the first >
      pos = close >= 0 ? close + 1 : n;
    } else if (nxt === "/" || isAsciiAlpha(nxt)) {
      const ending = nxt === "/";
      if (ending) pos += 1;
      const m = at(TAG_NAME, text, pos);
      const name = m[0].toLowerCase();
      const read = readTag(text, pos + m[0].length);
      if (read === null) return;
      pos = read[2];
      if (ending) {
        emit("end", name);
        continue;
      }
      emit("start", name, read[0], read[1]);
      if (name === "plaintext") return;
      if (RAW_TEXT.has(name)) {
        const r = search(RAW_END[name], text, pos);
        pos = r ? r.index : n;
      }
    } else {
      emit("text", "<");
    }
  }
}

// Receives the tokens and writes the clean markup. `out` is what is written; `stack` the tags open in it.
class Cleaner {
  constructor() {
    this.out = [];
    this.stack = [];
    this.skip = null;                  // inside a dropped element: its name, and how many of it are open
    this.nest = 0;
    this.gap = false;                  // a removed block tag was passed; the last thing written is text or inline
    this.running = false;
  }

  popTo(index) {
    while (this.stack.length > index) {
      this.running = INLINE.has(this.stack[this.stack.length - 1]);
      this.out.push(`</${this.stack.pop()}>`);
    }
  }

  write(piece, tag) {
    if (this.gap && this.running && !BREAKING.has(tag) && !SPACE.includes(piece[0])) this.out.push("\n");
    this.gap = false;
    this.running = !BREAKING.has(tag) && !piece.endsWith("\n");
    this.out.push(piece);
  }

  makeRoom(tag) {
    const stack = this.stack;
    if (tag === "a" && stack.includes("a")) this.popTo(stack.indexOf("a"));
    if (tag === "li") {
      for (let i = stack.length - 1; i >= 0; i--) {
        if (stack[i] === "ul" || stack[i] === "ol" || stack[i] === "blockquote") break;
        if (stack[i] === "li") {
          this.popTo(i);
          break;
        }
      }
    }
    if (ENDS_PARAGRAPH.has(tag)) {
      let i = stack.length - 1;
      while (i >= 0 && INLINE.has(stack[i])) i--;
      if (i >= 0 && PARAGRAPH.has(stack[i])) this.popTo(i);
    }
  }

  start(tag, attrs, selfClosing) {
    if (selfClosing && EMPTY_FOREIGN.has(tag)) return;
    if (this.skip) {
      if (tag === this.skip) this.nest += 1;
      return;
    }
    if (BLOCKS.has(tag)) this.gap = true;
    if (DROP_WITH_CONTENT.has(tag)) {
      this.skip = tag;
      this.nest = 1;
      return;
    }
    if (!ALLOWED.has(tag)) return;                              // the tag goes, its text stays
    const given = new Map();
    for (const [name, value] of attrs) if (!given.has(name)) given.set(name, value);   // the first of a repeated attribute counts
    this.makeRoom(tag);
    if (tag === "input") {
      if (pyStrip(given.has("type") ? given.get("type") : "").toLowerCase() !== "checkbox") return;
      const flags = ["checked", "disabled"].filter((k) => given.has(k)).map((k) => ` ${k}`).join("");
      this.write(`<input type="checkbox"${flags}>`, tag);
      return;
    }
    let opening;
    if (tag === "a") {
      const target = href(given.has("href") ? given.get("href") : null);
      if (target === null) return;                              // a link with no safe address is just its text
      opening = `<a href="${attrEscape(target)}" rel="noopener noreferrer">`;
    } else {
      opening = `<${tag}>`;
    }
    if (VOID.has(tag)) {
      this.write(opening, tag);
    } else if (this.stack.length < MAX_DEPTH) {
      this.write(opening, tag);
      this.stack.push(tag);
    }
  }

  end(tag) {
    if (this.skip) {
      if (tag === this.skip) {
        this.nest -= 1;
        if (!this.nest) this.skip = null;
      }
      return;
    }
    if (tag === "br") {                                         // a browser reads `</br>` as `<br>`
      this.start("br", [], false);
      return;
    }
    if (BLOCKS.has(tag)) this.gap = true;
    if (ALLOWED.has(tag) && !VOID.has(tag) && this.stack.includes(tag)) this.popTo(this.stack.lastIndexOf(tag));
  }

  text(data) {
    if (!this.skip) {
      data = data.replace(CONTROL, "");
      if (data) this.write(textEscape(data));
    }
  }
}

const typeName = (x) => (Array.isArray(x) ? "list" : typeof x === "number" ? (Number.isInteger(x) ? "int" : "float") :
  typeof x === "boolean" ? "bool" : typeof x === "object" ? "dict" : typeof x);

// `html` (HTML the editor wrote) reduced to the allow-list, as one well-formed string. null, undefined and "" give "". A field that
// is already clean comes back byte for byte; cleaning the result again changes nothing. Throws SanitiseError (as Python raises it,
// with the same message) if `html` is not text, or is, or would come out, longer than MAX_CHARS.
export function cleanHtml(html) {
  if (html === null || html === undefined) return "";
  if (typeof html !== "string") throw new SanitiseError(`Rich text must be text, not ${typeName(html)}.`);
  if (html.length > MAX_CHARS) checkLength(codePoints(html), false);
  const cleaner = new Cleaner();
  tokens(html.replace(CONTROL, ""), (kind, a, b, c) => {
    if (kind === "text") cleaner.text(decode(a, false));
    else if (kind === "start") cleaner.start(a, b, c);
    else cleaner.end(a);
  });
  cleaner.popTo(0);
  const result = limitBlankLines(cleaner.out.join(""));
  if (result.length > MAX_CHARS) checkLength(codePoints(result), true);
  return result;
}

// A blank line, as the editor writes it: an empty paragraph, or one holding only a line break (a paragraph of only spaces is made
// empty first). Port of sanitise.limit_blank_lines (#84): a run of more than MAX_BLANK_RUN is cut to that; nothing else is touched.
const SPACE_ONLY = /<p>[ \t\n\r\f]+<\/p>/g;
const BLANK_TEXT = " \t\n\r\f\u00a0";                      // what a blank line may hold as text in plainText (no zero-width or wide spaces)
const BLANK_LINE_SOURCE = "<p>(?:<br>)?<\\/p>";
const BLANK_RUN = new RegExp(`(?:${BLANK_LINE_SOURCE}[ \\t\\n\\r\\f]*){${MAX_BLANK_RUN + 1},}`, "g");
const BLANK_LINE = new RegExp(BLANK_LINE_SOURCE, "g");

function limitBlankLines(markup) {
  if (!markup.includes("</p>")) return markup;
  return markup.replace(SPACE_ONLY, "<p></p>").replace(BLANK_RUN, (m) => m.match(BLANK_LINE).slice(0, MAX_BLANK_RUN).join(""));
}

function onlyBlankText(text) {                                  // str.strip(BLANK_TEXT) is empty
  for (const c of text) if (!BLANK_TEXT.includes(c)) return false;
  return true;
}

// The words in `html` (sanitise.plain_text): cleaned first, tags removed, references decoded, and paragraphs, list items and line
// breaks become a newline. Each blank line (an empty paragraph, or one of only spaces or &nbsp;) is one empty line, and the ends are
// trimmed. Not HTML: never put it back into a page unescaped.
export function plainText(html) {
  const parts = [];
  const found = [];
  tokens(cleanHtml(html), (kind, a) => found.push([kind, a]));
  let i = 0;
  while (i < found.length) {
    const [kind, a] = found[i];
    i += 1;
    if (kind === "text") parts.push(decode(a, false));
    else if (BREAKS.has(a) && parts.length && !parts[parts.length - 1].endsWith("\n")) parts.push("\n");
    if (kind === "start" && a === "p") {                        // a blank line: <p></p> or <p><br></p> is one empty line (#84)
      let j = i;
      if (j < found.length && found[j][0] === "text" && onlyBlankText(decode(found[j][1], false))) j += 1;
      else if (j < found.length && found[j][0] === "start" && found[j][1] === "br") j += 1;
      if (j < found.length && found[j][0] === "end" && found[j][1] === "p") {
        if (parts.length) parts.push("\n");
        i = j + 1;
      }
    }
  }
  return pyStrip(parts.join(""));
}
