// The editor's two conversions (#66). Tiptap's own HTML carries attributes and wrappers the cleaner would drop (a checklist is a
// label, a span and a div), so the editor never uses getHTML(): it writes the document itself, in the shape sanitise.py returns,
// and then runs that through cleanHtml, so what it hands out is always exactly what the server will keep.
//   toHtml(doc)        a Tiptap document (editor.getJSON()) as cleaned HTML
//   forEditor(clean)   cleaned HTML in the form Tiptap reads (a checklist marked with data-type)
import { cleanHtml } from "../logic/cleanHtml.js";

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escAttr = (s) => esc(s).replace(/"/g, "&quot;");

// Marks nest in one fixed order, so the same text always gives the same string: link outside, then strong, em, s.
const ORDER = ["link", "bold", "italic", "strike"];
const TAGS = { bold: "strong", italic: "em", strike: "s" };

function text(node) {
  let s = esc(node.text || "");
  const marks = (node.marks || []).slice().sort((a, b) => ORDER.indexOf(a.type) - ORDER.indexOf(b.type));
  for (const m of marks.slice().reverse()) {
    if (m.type === "link") {
      const a = m.attrs && m.attrs.href;
      if (typeof a === "string" && a) s = `<a href="${escAttr(a)}" rel="noopener noreferrer">${s}</a>`;
    } else if (TAGS[m.type]) s = `<${TAGS[m.type]}>${s}</${TAGS[m.type]}>`;
  }
  return s;
}

function kids(node) {
  return (node.content || []).map(block).join("");
}

function block(node) {
  switch (node.type) {
    case "text": return text(node);
    case "hardBreak": return "<br>";
    case "paragraph": return `<p>${kids(node)}</p>`;
    case "heading": {
      const n = Math.min(3, Math.max(1, Number(node.attrs && node.attrs.level) || 1));
      return `<h${n}>${kids(node)}</h${n}>`;
    }
    case "bulletList": return `<ul>${kids(node)}</ul>`;
    case "orderedList": return `<ol>${kids(node)}</ol>`;
    case "taskList": return `<ul>${kids(node)}</ul>`;
    case "listItem": return `<li>${kids(node)}</li>`;
    case "taskItem": return `<li><input type="checkbox"${node.attrs && node.attrs.checked ? " checked" : ""}>${kids(node)}</li>`;
    case "blockquote": return `<blockquote>${kids(node)}</blockquote>`;
    case "horizontalRule": return "<hr>";
    default: return kids(node);          // anything the allow-list has no tag for keeps its words
  }
}

/** The document as cleaned HTML. An empty document ("one empty paragraph") is "". */
export function toHtml(doc) {
  const out = (doc && doc.content ? doc.content : []).map(block).join("");
  return cleanHtml(out === "<p></p>" ? "" : out);
}

/** `clean` (already cleaned) in the form the editor loads: each checklist marked for Tiptap, its checkbox taken out. Uses the
 * browser's parser on text the cleaner wrote, which holds nothing but the allow-list, so there is nothing to run. */
export function forEditor(clean) {
  if (!clean || clean.indexOf("<input") < 0) return clean || "";
  const doc = new DOMParser().parseFromString(`<body>${clean}</body>`, "text/html");
  doc.body.querySelectorAll("ul").forEach((ul) => {
    const items = [...ul.children].filter((c) => c.tagName === "LI");
    if (!items.length || !items.every((li) => li.firstElementChild && li.firstElementChild.tagName === "INPUT")) return;
    ul.setAttribute("data-type", "taskList");
    items.forEach((li) => {
      const box = li.firstElementChild;
      li.setAttribute("data-type", "taskItem");
      li.setAttribute("data-checked", box.hasAttribute("checked") ? "true" : "false");
      box.remove();
    });
  });
  doc.body.querySelectorAll("input").forEach((i) => i.remove());
  return doc.body.innerHTML;
}
