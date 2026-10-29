// BL-301 part A (development only): creaite's exact Markdown writer ("a custom exact writer;
// creaite's Markdown style; stored text never changes").
//
// It writes a Tiptap document (editor.getJSON(), public) as Markdown itself, without Tiptap's serialiser, so no private
// method is patched. Two rules:
//   1. What was read is written back as it was. The parse side (source.js) keeps each written form in the document
//      (italic "*" or "_", a bare or bracketed link, a table's source, HTML and comments, a backslash escape, an entity).
//   2. What is new is written in creaite's style: md_normalise's form (docx_tools.py): "_italic_", "**bold**", "- "
//      bullets, "1. " numbers per level, nested items indented 2 spaces, "### " headings, "> " quotes, blank lines
//      between blocks; text as it is, escaped only where it would otherwise read differently.
// Each block is checked by parsing what was written (editor.markdown.parse, public) and comparing the content; when it
// differs the block is written again more cautiously (italic with "*", links in brackets, then text escaped), so a
// text never silently changes meaning. writeMarkdown returns the Markdown and whether every block came back the same.
import { FORM_ATTRS } from "./source.js";

const MARK_ORDER = ["link", "bold", "italic", "strike", "underline", "code"];
const ATTEMPTS = [{}, { italicStar: true }, { linkBracket: true }, { italicStar: true, linkBracket: true },
  { italicStar: true, linkBracket: true, escape: true }];

const rank = (m) => {
  const i = MARK_ORDER.indexOf(m.type);
  return i < 0 ? MARK_ORDER.length : i;
};
const sameMark = (a, b) => a.type === b.type && JSON.stringify(a.attrs || {}) === JSON.stringify(b.attrs || {});

/** Text escaped so that Markdown reads it back as the same characters (used only when the plain text didn't). */
function escapeText(text, atLineStart, inTable) {
  // "_" between two letters or digits never opens or closes emphasis, and "<" only starts HTML before a letter, "/", "!"
  // or "?": those stay as they are (a_b_c, x < y).
  let out = text.replace(/[\\`*[\]~]|_(?![A-Za-z0-9])|(?<![A-Za-z0-9])_|<(?=[A-Za-z/!?])/g, "\\$&")
    .replace(/&(?=#?[A-Za-z0-9]+;)/g, "\\&");
  if (inTable) out = out.replace(/\|/g, "\\|");
  const lead = (s) => s.replace(/^(\s*)([#>+=-]|\d+(?=[.)]))/, (all, sp, c) => (/\d/.test(c) ? `${sp}${c}\\` : `${sp}\\${c}`));
  out = out.split("\n").map((line, i) => (i > 0 || atLineStart ? lead(line) : line)).join("\n");
  return out;
}

/** The opening and closing Markdown of a mark. */
function delimiters(mark, opt, text) {
  const a = mark.attrs || {};
  switch (mark.type) {
    case "bold": return [a.delim || "**", a.delim || "**"];
    case "italic": {
      const d = opt.italicStar ? "*" : a.delim || "_";
      return [d, d];
    }
    case "strike": return ["~~", "~~"];
    case "code": {
      const runs = (text.match(/`+/g) || []).map((r) => r.length);
      const kept = a.delim && /^(`+) ?$/.exec(a.delim);
      if (kept && !runs.includes(kept[1].length)) return [a.delim, [...a.delim].reverse().join("")];
      const n = runs.length ? Math.max(...runs) + 1 : 1;
      const pad = text.includes("`") || (/^ .* $/.test(text) && text.trim()) ? " " : "";   // `` a`b ``
      return ["`".repeat(n) + pad, pad + "`".repeat(n)];
    }
    case "link": {
      const form = opt.linkBracket ? null : a.form === undefined || a.form === null
        ? (text === a.href && /^(https?:\/\/|mailto:)\S+$/.test(a.href || "") ? "bare" : null) : a.form;
      if (form === "bare") return ["", ""];
      if (form === "angle") return ["<", ">"];
      const title = a.title ? ` "${String(a.title).replace(/"/g, '\\"')}"` : "";
      const href = /[\s()]/.test(a.href || "") && !/^[^\s()]*(\([^\s()]*\)[^\s()]*)*$/.test(a.href || "")
        ? `<${a.href}>` : a.href || "";
      return ["[", `](${href}${title})`];
    }
    default: return ["", ""];
  }
}

/** The text a run of inline nodes holds under one mark from index `i` (for a link's or a code span's whole text). */
function spanText(nodes, i, mark) {
  let s = "";
  for (let j = i; j < nodes.length; j++) {
    const n = nodes[j];
    if (!(n.marks || []).some((m) => sameMark(m, mark))) break;
    s += n.type === "text" ? n.text : "";
  }
  return s;
}

/** Inline content as Markdown. */
function writeInline(nodes, opt, ctx) {
  const parts = [];          // {k: "open"|"close"|"text", s}
  const stack = [];
  nodes = nodes || [];
  nodes.forEach((n, i) => {
    const marks = (n.marks || []).filter((m) => m.type !== "literal").sort((a, b) => rank(a) - rank(b));
    let keep = 0;
    while (keep < stack.length && marks.some((m) => sameMark(m, stack[keep].mark))) keep++;
    while (stack.length > keep) parts.push({ k: "close", s: stack.pop().close });
    for (const m of marks) {
      if (stack.some((s) => sameMark(s.mark, m))) continue;
      const [open, close] = delimiters(m, opt, spanText(nodes, i, m));
      parts.push({ k: "open", s: open });
      stack.push({ mark: m, close });
    }
    const inCode = marks.some((m) => m.type === "code");
    if (n.type === "text") {
      const lit = (n.marks || []).find((m) => m.type === "literal");
      if (lit && lit.attrs && lit.attrs.text === n.text && lit.attrs.raw) parts.push({ k: "text", s: lit.attrs.raw });
      else if (inCode) parts.push({ k: "text", s: n.text, code: true });
      else if (!opt.escape) parts.push({ k: "text", s: n.text });
      else parts.push({ k: "text", s: escapeText(n.text, i === 0 && ctx.lineStart, ctx.table) });
    } else if (n.type === "hardBreak") {
      // A table row is one line: a break in a cell is "<br>" there (it reads back as a hard break, source.js).
      const kept = (n.attrs && n.attrs.raw) || "  \n";
      parts.push({ k: "text", s: ctx.table && kept.includes("\n") ? "<br>" : kept, br: true });
    } else if (n.type === "htmlInline") {
      parts.push({ k: "text", s: (n.attrs && n.attrs.raw) || "" });
    } else if (n.type === "image") {
      parts.push({ k: "text", s: writeImage(n) });
    } else {
      parts.push({ k: "text", s: writeInline(n.content, opt, ctx) });
    }
  });
  while (stack.length) parts.push({ k: "close", s: stack.pop().close });
  // Markdown can't open a mark before a space or close one after it: such spaces go outside the delimiters (never a code
  // span's, whose spaces are its own).
  for (let i = 0; i < parts.length; i++) {
    if (parts[i].k !== "text" || parts[i].br || parts[i].code) continue;
    let j = i + 1;
    while (j < parts.length && parts[j].k === "close" && parts[j].s) j++;
    const trail = /[ \t]+$/.exec(parts[i].s);
    if (trail && j > i + 1) {
      parts[i].s = parts[i].s.slice(0, trail.index);
      parts.splice(j, 0, { k: "text", s: trail[0] });
    }
    let o = i - 1;
    while (o >= 0 && parts[o].k === "open" && parts[o].s) o--;
    const lead = /^[ \t]+/.exec(parts[i].s);
    if (lead && o < i - 1) {
      parts[i].s = parts[i].s.slice(lead[0].length);
      parts.splice(o + 1, 0, { k: "text", s: lead[0] });
      i++;
    }
  }
  return parts.map((p) => p.s).join("");
}

function writeImage(n) {
  const a = n.attrs || {};
  const title = a.title ? ` "${String(a.title).replace(/"/g, '\\"')}"` : "";
  return `![${String(a.alt || "").replace(/([[\]])/g, "\\$1")}](${a.src || ""}${title})`;
}

/** `text` with every line indented by `pad` (blank lines left empty); `first`: the first line too. */
const indent = (text, pad, first = true) =>
  text.split("\n").map((l, i) => ((i === 0 && !first) || !l ? l : pad + l)).join("\n");
const isList = (n) => /^(bullet|ordered|task)List$/.test(n.type);

/** A list, tight (items on consecutive lines). Everything inside an item after its first line is indented 2 spaces,
 * whatever the marker: creaite's style (md_normalise), and what Tiptap's own numbered-list reader takes off (it reads
 * "1. a  \n   b" as " b", so 3 spaces would not come back). */
function writeList(node, opt) {
  const a = node.attrs || {};
  return (node.content || []).map((item, i) => {
    const marker = node.type === "orderedList" ? `${(a.start || 1) + i}${a.delim || "."} ` : `${a.bullet || "-"} `;
    const box = item.type === "taskItem" ? (item.attrs && item.attrs.checked ? "[x] " : "[ ] ") : "";
    return (item.content || []).map((k, j) => {
      const body = writeBlock(k, opt);
      if (j === 0) return marker + box + indent(body, "  ", false);
      return (isList(k) ? "\n" : "\n\n") + indent(body, "  ");
    }).join("");
  }).join("\n");
}

function writeTableFresh(node, opt) {
  const rows = (node.content || []).map((row) => (row.content || []).map((cell) =>
    (cell.content || []).map((p) => writeInline(p.content, opt, { table: true })).join(" ")));
  const head = (node.content && node.content[0] && node.content[0].content) || [];
  const rule = head.map((c) => {
    const al = c.attrs && c.attrs.align;
    return al === "left" ? ":---" : al === "right" ? "---:" : al === "center" ? ":---:" : "---";
  });
  const line = (cells) => `| ${cells.join(" | ")} |`;
  return [line(rows[0] || []), line(rule), ...rows.slice(1).map(line)].join("\n");
}

function writeBlock(node, opt) {
  const a = node.attrs || {};
  switch (node.type) {
    case "paragraph": return writeInline(node.content, opt, { lineStart: true });
    case "heading": return `${"#".repeat(a.level || 3)} ${writeInline(node.content, opt, { lineStart: false })}`;
    case "blockquote":
      return writeBlocks(node.content, opt).split("\n").map((l) => (l ? `> ${l}` : ">")).join("\n");
    case "bulletList": case "orderedList": case "taskList": return writeList(node, opt);
    case "codeBlock": {
      const text = (node.content || []).map((t) => t.text).join("");
      const fence = /```/.test(text) ? "~~~" : "```";
      return `${fence}${a.language || ""}\n${text}\n${fence}`;
    }
    case "horizontalRule": return "---";
    case "image": return writeImage(node);
    case "htmlBlock": return a.raw || "";
    case "table":
      return a.source && opt.sameAsSource && opt.sameAsSource(node) ? a.source : writeTableFresh(node, opt);
    default: return writeInline(node.content, opt, { lineStart: true });
  }
}

function writeBlocks(nodes, opt) {
  return (nodes || []).map((n) => writeBlock(n, opt)).join("\n\n");
}

/** A copy of a document without the written forms (FORM_ATTRS, literal marks), adjacent texts merged and spaces moved
 * out of marks' edges: what has to be the same for two documents to say the same thing. */
export function content(json) {
  const clean = (n) => {
    const out = { type: n.type };
    if (n.attrs) {
      const attrs = Object.fromEntries(Object.entries(n.attrs).filter(([k, v]) => !FORM_ATTRS.includes(k) && v !== null));
      if (n.type === "htmlBlock" || n.type === "htmlInline") attrs.raw = n.attrs.raw;
      if (Object.keys(attrs).length) out.attrs = attrs;
    }
    if (n.type === "text") {
      out.text = n.text;
      const marks = (n.marks || []).filter((m) => m.type !== "literal").map(clean)
        .sort((x, y) => JSON.stringify(x).localeCompare(JSON.stringify(y)));
      if (marks.length) out.marks = marks;
    }
    if (n.content) out.content = merge(n.content.map(clean));
    return out;
  };
  const merge = (list) => {
    const out = [];
    for (const n of list) {
      if (n.type === "text" && n.marks) {           // a space at a mark's edge counts as outside it
        const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(n.text);
        if (m[1]) out.push({ type: "text", text: m[1] });
        if (m[2]) out.push({ ...n, text: m[2] });
        if (m[3]) out.push({ type: "text", text: m[3] });
        continue;
      }
      out.push(n);
    }
    const merged = [];
    for (const n of out) {
      const p = merged[merged.length - 1];
      if (p && p.type === "text" && n.type === "text" && JSON.stringify(p.marks || []) === JSON.stringify(n.marks || [])) {
        p.text += n.text;
      } else merged.push({ ...n });
    }
    return merged;
  };
  return clean(json);
}

const same = (a, b) => JSON.stringify(content(a)) === JSON.stringify(content(b));

/** {markdown, faithful}: the document `json` as Markdown, each block checked with `parse` (Markdown → document JSON).
 * `faithful` is false when some block (or the whole) would read back differently however it is written. */
export function writeMarkdown(json, parse) {
  const sameAsSource = (table) => {
    const back = parse(table.attrs.source).content || [];
    return back.length === 1 && same(back[0], table);
  };
  let faithful = true;
  // Empty paragraphs at the end are the editor's (Tiptap's TrailingNode adds one after a final list or table), never
  // the text's: what followed the last block is kept by the envelope (editor.js) instead.
  const nodes = [...(json.content || [])];
  while (nodes.length > 1 && nodes[nodes.length - 1].type === "paragraph" && !(nodes[nodes.length - 1].content || []).length) {
    nodes.pop();
  }
  // An empty paragraph straight after a list can't be written: the list takes in the blank lines, so the next load
  // would lose it and the next save differ (BL-301's notes gate: save, load, save gives the same bytes). It is layout,
  // not content, and is left out (as the trailing ones are), so the first save is already the stable one.
  for (let i = nodes.length - 1; i > 0; i--) {
    const empty = nodes[i].type === "paragraph" && !(nodes[i].content || []).length;
    let j = i - 1;
    while (j >= 0 && nodes[j].type === "paragraph" && !(nodes[j].content || []).length) j--;
    if (empty && j >= 0 && isList(nodes[j])) nodes.splice(i, 1);
  }
  json = { ...json, content: nodes };
  const blocks = nodes.map((node) => {
    let first = null;
    for (const attempt of ATTEMPTS) {
      const md = writeBlock(node, { ...attempt, sameAsSource });
      if (first === null) first = md;
      if (node.type === "paragraph" && !(node.content || []).length) return md;
      const back = parse(md).content || [];
      if (back.length === 1 && same(back[0], node)) return md;
    }
    faithful = false;
    return first;
  });
  const markdown = blocks.join("\n\n");
  if (faithful && !same(parse(markdown), json)) faithful = false;
  return { markdown, faithful };
}
