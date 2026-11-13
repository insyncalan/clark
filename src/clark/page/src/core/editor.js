// clarkEditor (#66): the page's one rich-text editor. Every editable rich field (a report headline, a use case's standing, a text
// section's body) is one of these and nothing else is; tests/test_one_editor_gate.py counts them and greps for any other.
// Adapted from creaite's creaiteEditor: no Markdown, no head shift, no claims, no images, no email set. Its value is HTML, and it
// is always the HTML the cleaner returns (richHtml.js), so what the editor says it holds is what the server will store.
//
// The editor never changes a field by being opened: `html()` gives the stored text back as it was until the document is edited.
// A paste is cleaned before it enters (the same cleaner as the server). Links keep only an address the cleaner accepts. The editor
// adds no <style> (injectCSS: false): the page's own CSS draws it, and the enforced style rules would block a run-time one.
//
//   const ed = clarkEditor(el, { profile: "rich" | "plain", html: stored, onSave, onCancel, onChange, keyHook, onError })
//   ed.html()   the cleaned HTML ("rich") or the plain text ("plain"); the stored text itself when nothing was edited
//   ed.written() what the document says now, edited or not (the tests compare it with the cleaner)
//   ed.dirty()  whether the document differs from the one it opened with
//   ed.run(name, arg), ed.can(name), ed.active(name)   the toolbar's commands (see COMMANDS)
//   ed.focus(), ed.destroy()
// Keys: Cmd or Ctrl + Enter saves (onSave), Esc cancels (onCancel). A plain profile also saves on Enter (one line).
import { createEditor } from "tiptap";
import { cleanHtml, href, SanitiseError } from "../logic/cleanHtml.js";
import { toHtml, forEditor } from "./richHtml.js";

export { SanitiseError };

// Left out of the vendored feature set: Markdown and the raw-HTML nodes, code, images, and the claim mark.
const DROP = new Set(["markdown", "htmlBlock", "htmlBlockFromMarked", "htmlInline", "literal", "image", "code"]);

function rich(list) {
  return list.filter((e) => !DROP.has(e.name)).map((e) => {
    if (e.name === "starterKit") {
      return e.configure({ heading: { levels: [1, 2, 3] }, codeBlock: false, underline: false, code: false, dropcursor: false,
        gapcursor: false, link: false, trailingNode: false, horizontalRule: {}, blockquote: {}, strike: {} });
    }
    if (e.name === "link") {
      return e.configure({ openOnClick: false, autolink: false, linkOnPaste: false, defaultProtocol: "https",
        isAllowedUri: (url) => !!href(url), HTMLAttributes: { rel: "noopener noreferrer", target: null, class: null } });
    }
    return e;
  });
}

const textOf = (doc) => (doc.content || []).map((p) => (p.content || []).map((n) => (n.type === "hardBreak" ? " " : n.text || "")).join("")).join("\n");

// A paste goes through the cleaner before the editor reads it. Text the cleaner refuses (too long) pastes as nothing.
function cleanPaste(html) {
  try { return cleanHtml(html); } catch (e) { return ""; }
}

// A one-line field: a paste is its words on one line, whatever markup or paragraphs it came with.
function pasteWords(html) {
  const t = document.createElement("template");
  t.innerHTML = cleanPaste(html).replace(/<\/(p|li|h[1-6]|blockquote|div)>|<(br|hr)\s*\/?>/gi, " ");          // the cleaner first: a script's text is never words
  const words = (t.content.textContent || "").replace(/[\s\u0085]+/g, " ").trim();
  return `<p>${words.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</p>`;
}

const COMMANDS = {
  bold: (c) => c.toggleBold(), italic: (c) => c.toggleItalic(), strike: (c) => c.toggleStrike(),
  h1: (c) => c.toggleHeading({ level: 1 }), h2: (c) => c.toggleHeading({ level: 2 }), h3: (c) => c.toggleHeading({ level: 3 }),
  paragraph: (c) => c.setParagraph(),
  bullet: (c) => c.toggleBulletList(), numbered: (c) => c.toggleOrderedList(), checklist: (c) => c.toggleTaskList(),
  quote: (c) => c.toggleBlockquote(), rule: (c) => c.setHorizontalRule(),
  undo: (c) => c.undo(), redo: (c) => c.redo(),
};
export const COMMAND_NAMES = Object.keys(COMMANDS).concat(["link", "unlink"]);

const ACTIVE = { bold: ["bold"], italic: ["italic"], strike: ["strike"], h1: ["heading", { level: 1 }], h2: ["heading", { level: 2 }],
  h3: ["heading", { level: 3 }], bullet: ["bulletList"], numbered: ["orderedList"], checklist: ["taskList"], quote: ["blockquote"],
  link: ["link"] };

// Item 1005: the cleaner drops the next-line character (U+0085) as a control, which glued the words either side of it. It is a space.
function nelToSpace(node) {
  if (node && typeof node.text === "string") return { ...node, text: node.text.replace(/\u0085/g, " ") };
  return node && node.content ? { ...node, content: node.content.map(nelToSpace) } : node;
}

export function clarkEditor(el, { profile = "rich", html = "", onSave, onCancel, onChange, keyHook, onError, oneLine = false } = {}) {
  const plain = profile === "plain";
  const bare = plain || oneLine;                     // oneLine (item 1005): the rich profile's HTML in and out, but paragraphs only: no marks, no lists, no input rules, a paste is its words on one line
  const stored = html || "";
  let initial = null, done = false;
  let start = "";
  if (!plain) {
    try { start = forEditor(cleanHtml(stored)); } catch (e) { start = ""; }
  }
  const save = () => {
    if (!onSave) return;
    let out;
    try { out = handle.html(); } catch (e) { if (onError) { onError(e); return; } throw e; }       // a field the cleaner refuses (too long)
    onSave(out);
  };
  const keys = (view, e) => {
    if (e.isComposing) return false;
    if (keyHook && keyHook(e)) return true;          // an open menu takes its keys first
    if (e.key === "Escape") { e.preventDefault(); if (onCancel) onCancel(); return true; }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); return true; }
    if (e.key === "Enter" && plain && !e.shiftKey) { e.preventDefault(); save(); return true; }
    return false;
  };
  const editor = createEditor(el, {
    features: bare ? "plain" : "current",
    html: plain ? `<p></p>` : start,
    extensions: bare ? undefined : rich,
    injectCSS: false,
    editorProps: { handleKeyDown: keys, transformPastedHTML: oneLine ? pasteWords : cleanPaste,
      attributes: { class: "clark-ed", "aria-label": plain ? "Text" : "Rich text", "aria-multiline": plain ? "false" : "true", role: "textbox" } },
    onUpdate: () => { if (onChange) onChange(handle); },
    onSelectionUpdate: () => { if (onChange) onChange(handle); },
  });
  if (plain) editor.commands.setContent(`<p>${stored.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</p>`, { emitUpdate: false });
  initial = editor.state.doc;
  const handle = {
    editor,
    dirty: () => !editor.state.doc.eq(initial),
    written: () => (plain ? textOf(editor.getJSON()) : toHtml(nelToSpace(editor.getJSON()))),
    html() {
      if (!this.dirty()) return stored;
      return this.written();
    },
    can: (name) => { const f = COMMANDS[name]; return !!f && f(editor.can().chain().focus()).run(); },
    active: (name) => { const a = ACTIVE[name]; return !!a && editor.isActive(...a); },
    run(name, arg) {
      const c = editor.chain().focus();
      if (name === "link") {
        const a = href(arg || "");
        if (!a) return false;
        return c.extendMarkRange("link").setLink({ href: a }).run();
      }
      if (name === "unlink") return c.extendMarkRange("link").unsetLink().run();
      const f = COMMANDS[name];
      return f ? f(c).run() : false;
    },
    linkAddress: () => (editor.getAttributes("link") || {}).href || "",
    focus: () => editor.commands.focus("end"),
    destroy() { if (!done) { done = true; editor.destroy(); } },
  };
  editor.view.dom.cxed = handle;
  return handle;
}
