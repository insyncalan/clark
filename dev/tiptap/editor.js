// BL-301 part A groundwork (development only): the minimal Tiptap editor that dev/tools/tiptap.py bundles into one IIFE
// (window.CreaiteTiptap), and that the round-trip gate (dev/tools/tiptap_roundtrip.py) runs in headless Chrome.
// The dashboard's one editor (BL-301 A, src/core/editor.js `creaiteEditor`) imports this module, vendored, as "tiptap".
//
// Saving uses creaite's exact writer (writer.js), not Tiptap's serialiser: the parse side (source.js) keeps each text's
// written form in the document, and the writer gives it back byte for byte. `markdownOf` is what
// BL-301's wrapper will call on save.
import { Editor, Extension, Mark, Node, mergeAttributes } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import { closeHistory } from "@tiptap/pm/history";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "@tiptap/markdown";
import Image from "@tiptap/extension-image";
import { TaskList, TaskItem } from "@tiptap/extension-list";
import { TableKit } from "@tiptap/extension-table";
import { BoldForm, BulletListForm, CodeForm, HardBreakForm, HtmlBlock, HtmlBlockFromMarked, HtmlInline, ItalicForm, LinkForm, Literal,
  OrderedListForm, TableForm } from "./source.js";
import { writeMarkdown } from "./writer.js";

// What the dashboard's wrapper builds its own pieces from (the claim mark, the image's figure, the keys).
export { Extension, Mark, Node, mergeAttributes, Plugin, PluginKey };
// BL-301 B (Notes): decorations, for the note's wiki links and item chips (drawn, never written).
export { Decoration, DecorationSet };
// #175 (Notes): ProseMirror's closeHistory(tr), so the Notes editor can start a new undo step (core/editor.js cxUndoSteps).
export { closeHistory };

/** The pinned Tiptap version this file was written and gated against (tiptap.py's PINNED, set by the bundler). */
export const PINNED = typeof __TIPTAP_PINNED__ === "undefined" ? null : __TIPTAP_PINNED__;   // eslint-disable-line no-undef

// StarterKit's link, bold, code, italic, hard break and lists are replaced by the versions that keep their written form
// (source.js). Underline is off: creaite's Markdown has no underline (md_runs, the Word reports), and Tiptap's "++x++"
// would also read "C++ and C++" as underlined.
const STARTER = { link: false, bold: false, code: false, italic: false, hardBreak: false, bulletList: false, orderedList: false,
  underline: false };
const base = () => [StarterKit.configure(STARTER), BoldForm, CodeForm, ItalicForm, LinkForm.configure({ openOnClick: false }),
  HardBreakForm, BulletListForm, OrderedListForm, HtmlBlock, HtmlBlockFromMarked, HtmlInline, Literal, Image];

// A plain-text field (the peek's text, Prep's notes): paragraphs only, one a line, no Markdown and no marks, so what is
// stored stays plain text (the dashboard's wrapper loads and saves the lines itself).
const PLAIN = { blockquote: false, bold: false, bulletList: false, code: false, codeBlock: false, hardBreak: false,
  heading: false, horizontalRule: false, italic: false, listItem: false, listKeymap: false, orderedList: false,
  strike: false, link: false, underline: false, trailingNode: false };

// Each place switches on what it needs (BL-301 A): Current state has no tables; it has checklists since #134 (v2.2.0);
// Notes have everything.
const FEATURES = {
  plain: () => [StarterKit.configure(PLAIN)],
  current: () => [...base(), TaskList, TaskItem.configure({ nested: true }), Markdown],
  notes: () => [...base(), TaskList, TaskItem.configure({ nested: true }), TableKit.configure({ table: false }), TableForm,
    Markdown],
};

/** A Tiptap editor in `element` (a detached one when null; `{mount: el}` makes `el` itself the editable root), loaded
 * from Markdown, or from `html` or `json` when given. `extensions`: more extensions, or a function given the feature
 * set's list that returns the list to use (to replace one). Any other option goes to Tiptap's Editor as it is. */
export function createEditor(element, { markdown = "", features = "current", html, json, extensions, ...options } = {}) {
  const make = FEATURES[features];
  if (!make) throw new Error(`unknown features: ${features}`);
  const list = typeof extensions === "function" ? extensions(make()) : [...make(), ...(extensions || [])];
  const content = json !== undefined ? { content: json } : html !== undefined ? { content: html }
    : { content: markdown, contentType: "markdown" };
  return new Editor({ element: element || document.createElement("div"), extensions: list, ...content, ...options });
}

/** What the document can't hold, kept around it: the line ending (CRLF when every line ends so) and the blank lines and
 * trailing spaces before and after the text. `inner` is what the editor is given. */
export function envelope(text) {
  const crlf = /\r\n/.test(text) && !/(^|[^\r])\n/.test(text) && !/\r(?!\n)/.test(text);
  const t = crlf ? text.replace(/\r\n/g, "\n") : text;
  const head = /^(?:[ \t]*\n)*/.exec(t)[0];
  const tail = /\s*$/.exec(t.slice(head.length))[0];
  return { crlf, head, tail, inner: t.slice(head.length, t.length - tail.length) };
}

/** `markdown` (an editor's text) wrapped back in its envelope. */
export function wrap(env, markdown) {
  const t = env.head + markdown + env.tail;
  return env.crlf ? t.replace(/\n/g, "\r\n") : t;
}

/** The document `md` parses to, as the schema makes it (default attributes filled, adjacent texts joined), so it compares
 * with editor.getJSON(); an empty document when the schema refuses it. */
export function parser(editor) {
  return (md) => {
    try {
      return editor.schema.nodeFromJSON(editor.markdown.parse(md)).toJSON();
    } catch (e) {
      return { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: `(unreadable: ${e})` }] }] };
    }
  };
}

/** {markdown, faithful}: the editor's document (or `json`, a document of this editor's schema, such as getJSON() with
 * the marks Markdown doesn't hold taken out) as Markdown, by creaite's exact writer. */
export function markdownOf(editor, json) {
  return writeMarkdown(json || editor.getJSON(), parser(editor));
}

/** `editor`'s Markdown by `mode` ("exact": creaite's writer; "upstream": Tiptap's own getMarkdown, for comparison, its
 * faithfulness unknown), the editor then destroyed. */
function save(editor, mode) {
  try {
    return mode === "upstream" ? { markdown: editor.getMarkdown(), faithful: null } : markdownOf(editor);
  } finally {
    editor.destroy();
  }
}

/** {markdown, faithful}: what the editor gives back for `markdown`, loaded then saved (the exact writer keeps the
 * envelope around the document). */
export function roundTrip(markdown, features = "current", mode = "exact") {
  if (mode === "upstream") return save(createEditor(null, { markdown, features }), mode);
  const env = envelope(markdown);
  const out = save(createEditor(null, { markdown: env.inner, features }), mode);
  return { ...out, markdown: wrap(env, out.markdown) };
}

/** {markdown, faithful}: what the writer gives for `html` (content as typed or pasted into the editor: no written form,
 * so creaite's own style). */
export function fromHtml(html, features = "current", mode = "exact") {
  const make = FEATURES[features];
  if (!make) throw new Error(`unknown features: ${features}`);
  return save(new Editor({ element: document.createElement("div"), extensions: make(), content: html }), mode);
}

/** roundTrip (or, with `html`, fromHtml) for many texts at once: [{out, faithful}] or [{error}], in order. */
export function roundTripAll(texts, features = "current", mode = "exact", html = false) {
  return texts.map((t) => {
    try {
      const r = html ? fromHtml(t, features, mode) : roundTrip(t, features, mode);
      return { out: r.markdown, faithful: r.faithful };
    } catch (e) {
      return { error: String((e && e.message) || e) };
    }
  });
}
