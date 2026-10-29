// BL-301 part A (development only): the parse side of creaite's exact Markdown writer.
//
// Tiptap's document holds what a text says, not how it was written: "*x*" and "_x_" are the same italic, "https://u"
// and "[https://u](https://u)" the same link, and an HTML comment has no node at all. These extensions keep the written
// form beside the content, so the writer (writer.js) can give a text back byte for byte, and fall back to creaite's own
// style for anything typed new. Each uses only Tiptap's public extension API (`extend`, `addAttributes`,
// `parseMarkdown` calling `this.parent`, `markdownTokenizer`): no private method is touched.
//
//   italic       delim   "*" or "_"            (new text: "_", creaite's style)
//   bold         delim   "**" or "__"          (new text: "**")
//   code         delim   the opening backticks, and a space when one was taken off each end ("` a `")
//   link         form    "bare", "angle" or null for [text](href)  (new: bare when the text is its own address)
//   hardBreak    raw     "  \n", "\\\n", more trailing spaces, or "<br>"   (new: "  \n"; in a table cell "<br>")
//   bulletList   bullet  "-", "*" or "+"       (new: "-")
//   orderedList  delim   "." or ")"            (new: ".")
//   table        source  the table's Markdown as written; written back while the table's content is unchanged
//   htmlBlock / htmlInline  nodes holding HTML verbatim: comments (upstream drops them), tags (upstream turns <b> into **)
//   literal      a mark on a backslash escape ("\_") or an entity ("&amp;"): the written form and the text it gives
//
// None of these attributes is rendered into the editor's HTML; they ride along in the document and its undo history.
import { Extension, Node, Mark, mergeAttributes } from "@tiptap/core";
import { Bold } from "@tiptap/extension-bold";
import { Code } from "@tiptap/extension-code";
import { Italic } from "@tiptap/extension-italic";
import { Link } from "@tiptap/extension-link";
import { HardBreak } from "@tiptap/extension-hard-break";
import { BulletList, OrderedList } from "@tiptap/extension-list";
import { Table } from "@tiptap/extension-table";

/** An attribute kept in the document only: never rendered to HTML, never read from pasted HTML. */
const formAttr = () => ({ default: null, rendered: false, parseHTML: () => null, keepOnSplit: true });

/** The form attributes the writer reads; equal documents may differ in these alone (see writer.js `sameContent`). */
export const FORM_ATTRS = ["delim", "form", "raw", "bullet", "source"];

/** `ext` extended with form attributes `names`, and its parseMarkdown result given `formOf(token)`'s values. */
function keepForm(ext, names, formOf) {
  return ext.extend({
    addAttributes() {
      const own = this.parent ? this.parent() : {};
      return { ...own, ...Object.fromEntries(names.map((n) => [n, formAttr()])) };
    },
    parseMarkdown(token, helpers) {
      const result = this.parent(token, helpers);
      const form = formOf(token);
      const add = (r) => {
        if (!r || typeof r !== "object") return r;
        r.attrs = { ...(r.attrs || {}), ...form };
        return r;
      };
      return Array.isArray(result) ? result.map(add) : add(result);
    },
  });
}

const raw = (t) => String((t && t.raw) || "");

export const ItalicForm = keepForm(Italic, ["delim"], (t) => ({ delim: raw(t).startsWith("_") ? "_" : "*" }));
export const BoldForm = keepForm(Bold, ["delim"], (t) => ({ delim: raw(t).startsWith("__") ? "__" : "**" }));
export const LinkForm = keepForm(Link, ["form"], (t) => {
  const r = raw(t);
  return { form: r.startsWith("<") ? "angle" : r.startsWith("[") ? null : "bare" };
});
export const CodeForm = keepForm(Code, ["delim"], (t) => {
  const r = raw(t);
  const ticks = /^`+/.exec(r)[0];
  const inner = r.slice(ticks.length, r.length - ticks.length);
  return { delim: ticks + (inner.length > 2 && inner.startsWith(" ") && inner.endsWith(" ") && inner.trim() ? " " : "") };
});
export const HardBreakForm = keepForm(HardBreak, ["raw"], (t) => ({ raw: raw(t) || null }));
export const BulletListForm = keepForm(BulletList, ["bullet"], (t) => {
  const m = /^\s*([-*+])/.exec(raw(t));
  return { bullet: m ? m[1] : null };
});
export const OrderedListForm = keepForm(OrderedList, ["delim"], (t) => {
  const m = /^\s*\d+([.)])/.exec(raw(t));
  return { delim: m ? m[1] : null };
});
export const TableForm = keepForm(Table, ["source"], (t) => ({ source: raw(t).replace(/\n+$/, "") || null }));

/** The end of an HTML comment that starts at `src[at]` ("<!--"), or -1 when it never closes. */
function commentEnd(src, at) {
  const close = src.indexOf("-->", at + 4);
  return close < 0 ? -1 : close + 3;
}

const rawAttr = () => ({ raw: { default: "", rendered: false, parseHTML: (el) => el.getAttribute("data-raw") || "" } });

/** Block-level HTML, kept verbatim and shown as a small read-only chip (its text, never as markup). An HTML comment
 * (such as BL-89's pane marker or the template's guidance) is read by its own tokenizer, as CommonMark's HTML block of
 * type 2: from "<!--" to the end of the line holding the first "-->", or to the end of the text when it never closes.
 * Other block HTML comes from marked's own html token (HtmlBlockFromMarked). Upstream drops a comment, leaving an empty
 * paragraph, and turns other HTML into whatever the schema makes of it. */
export const HtmlBlock = Node.create({
  name: "htmlBlock",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes: rawAttr,
  parseHTML: () => [{ tag: "div[data-md-html]" }],
  renderHTML: ({ node, HTMLAttributes }) =>
    ["div", mergeAttributes(HTMLAttributes, { "data-md-html": "", "data-raw": node.attrs.raw, contenteditable: "false" }),
      node.attrs.raw],
  markdownTokenName: "htmlBlock",
  markdownTokenizer: {
    name: "htmlBlock",
    level: "block",
    start: (src) => {
      const m = /(^|\n) {0,3}<!--/.exec(src);
      return m ? m.index + m[1].length : -1;
    },
    tokenize(src) {
      const m = /^ {0,3}<!--/.exec(src);
      if (!m) return undefined;
      const end = commentEnd(src, m[0].length - 4);
      let stop = end < 0 ? src.length : src.indexOf("\n", end);
      if (stop < 0) stop = src.length;
      return { type: "htmlBlock", raw: src.slice(0, stop + (src[stop] === "\n" ? 1 : 0)), text: src.slice(0, stop) };
    },
  },
  parseMarkdown: (token, h) => h.createNode("htmlBlock", { raw: token.text }),
});

/** marked's block html token (any HTML block but a comment) as an htmlBlock, its trailing line ends left to the blank
 * lines between blocks. An inline html token is left alone here: Tiptap reads it before any handler (HtmlInline). */
export const HtmlBlockFromMarked = Extension.create({
  name: "htmlBlockFromMarked",
  markdownTokenName: "html",
  parseMarkdown: (token, h) =>
    token.block ? h.createNode("htmlBlock", { raw: String(token.raw || token.text || "").replace(/\n+$/, "") }) : null,
});

const BR = /^<br\s*\/?>$/i;
const INLINE_TAG = /^<\/?[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z_:][\w.:-]*(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*\s*\/?>/;

/** Inline HTML (a comment, or an opening or closing tag such as <b>, </b> or <br>), kept verbatim as a read-only chip.
 * Its own tokenizer reads it before marked does, so Tiptap never turns <b>x</b> into **x**: the text stays as written. */
export const HtmlInline = Node.create({
  name: "htmlInline",
  group: "inline",
  inline: true,
  atom: true,
  addAttributes: rawAttr,
  parseHTML: () => [{ tag: "span[data-md-html]" }],
  renderHTML: ({ node, HTMLAttributes }) =>
    ["span", mergeAttributes(HTMLAttributes, { "data-md-html": "", "data-raw": node.attrs.raw, contenteditable: "false" }),
      node.attrs.raw],
  markdownTokenName: "htmlInline",
  markdownTokenizer: {
    name: "htmlInline",
    level: "inline",
    start: (src) => {
      const m = /<[!/A-Za-z]/.exec(src);
      return m ? m.index : -1;
    },
    tokenize(src) {
      if (src.startsWith("<!--")) {
        const end = commentEnd(src, 0);
        return end < 0 ? undefined : { type: "htmlInline", raw: src.slice(0, end), text: src.slice(0, end) };
      }
      const m = INLINE_TAG.exec(src);
      return m ? { type: "htmlInline", raw: m[0], text: m[0] } : undefined;
    },
  },
  // "<br>" is a hard break kept as written (raw "<br>"): it is how a break inside a table cell is written (writer.js),
  // and so typed breaks in a cell survive save, load and save.
  parseMarkdown: (token, h) => (BR.test(token.text) ? h.createNode("hardBreak", { raw: token.text })
    : h.createNode("htmlInline", { raw: token.text })),
});

const ESCAPABLE = /^\\([!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~])/;
const ENTITY = /^&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});/;

/** The character an entity stands for, as the browser decodes it (null when it isn't one). */
function decodeEntity(entity) {
  const el = document.createElement("textarea");
  el.innerHTML = entity;
  return el.value === entity ? null : el.value;
}

/** A backslash escape or an HTML entity as written: the text it gives, with the written form (`raw`) and that text
 * (`text`) in the mark, so the writer gives the same bytes back while the text is unchanged. Not inclusive: typing next
 * to it never extends it. */
export const Literal = Mark.create({
  name: "literal",
  inclusive: false,
  excludes: "",
  addAttributes: () => ({ raw: formAttr(), text: formAttr() }),
  parseHTML: () => [],
  renderHTML: ({ HTMLAttributes }) => ["span", HTMLAttributes, 0],
  markdownTokenName: "literal",
  markdownTokenizer: {
    name: "literal",
    level: "inline",
    start: (src) => {
      const m = /\\[!-/:-@[-`{-~]|&(?:#|[A-Za-z])/.exec(src);
      return m ? m.index : -1;
    },
    tokenize(src) {
      let m = ESCAPABLE.exec(src);
      if (m) return { type: "literal", raw: m[0], text: m[1] };
      m = ENTITY.exec(src);
      if (!m) return undefined;
      const text = decodeEntity(m[0]);
      return text === null ? undefined : { type: "literal", raw: m[0], text };
    },
  },
  parseMarkdown: (token, h) => h.applyMark("literal", [h.createTextNode(token.text)], { raw: token.raw, text: token.text }),
});
