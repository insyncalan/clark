// Row 1292 (S7): what sits under an answer (Copy, Ask again) and the recall of the last question. The answer is model text and is never read
// as markup: the copy is built from askFormat.js's blocks, every word escaped, so only elements clark makes itself reach the clipboard.
import { parseAnswer } from "./askFormat.js";

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function nodesHtml(list) {
  return list.map((n) => n.t === "strong" ? "<strong>" + nodesHtml(n.c) + "</strong>"
    : n.t === "em" ? "<em>" + nodesHtml(n.c) + "</em>"
    : n.t === "code" ? "<code>" + esc(n.v) + "</code>"
    : esc(n.v)).join("");
}
function nodesPlain(list) {
  return list.map((n) => (n.t === "strong" || n.t === "em" ? nodesPlain(n.c) : n.v)).join("");
}
const linesHtml = (lines) => lines.map(nodesHtml).join("<br>");
const linesPlain = (lines) => lines.map(nodesPlain).join("\n");

/** The answer as HTML a word processor or a mail window keeps: headings, bold, italic, code, lists. */
export function answerHtml(text) {
  return parseAnswer(text).map((b) => {
    if (b.t === "h") return "<h" + (b.level + 2) + ">" + nodesHtml(b.c) + "</h" + (b.level + 2) + ">";
    if (b.t === "p") return "<p>" + linesHtml(b.lines) + "</p>";
    if (b.t === "pre") return "<pre><code>" + esc(b.v) + "</code></pre>";
    const start = b.t === "ol" && b.start !== 1 ? ' start="' + b.start + '"' : "";
    return "<" + b.t + start + ">" + b.items.map((it) => "<li>" + linesHtml(it) + "</li>").join("") + "</" + b.t + ">";
  }).join("");
}

/** The answer as plain text: marks gone, list markers kept, blocks one blank line apart. */
export function answerPlain(text) {
  return parseAnswer(text).map((b) => {
    if (b.t === "h") return nodesPlain(b.c);
    if (b.t === "p") return linesPlain(b.lines);
    if (b.t === "pre") return b.v;
    return b.items.map((it, k) => (b.t === "ol" ? b.start + k + ". " : "- ") + linesPlain(it)).join("\n");
  }).join("\n\n");
}

/** Puts the answer on the clipboard as HTML and as plain text; resolves true when it was written. */
export async function copyAnswer(text) {
  try {
    const nav = typeof navigator === "undefined" ? null : navigator;
    if (nav && nav.clipboard && typeof ClipboardItem !== "undefined" && nav.clipboard.write) {
      await nav.clipboard.write([new ClipboardItem({
        "text/html": new Blob([answerHtml(text)], { type: "text/html" }),
        "text/plain": new Blob([answerPlain(text)], { type: "text/plain" }),
      })]);
      return true;
    }
    if (nav && nav.clipboard && nav.clipboard.writeText) { await nav.clipboard.writeText(answerPlain(text)); return true; }
  } catch (e) { /* refused by the browser: the caller says so */ }
  return false;
}

const isQuestion = (t) => !!t && t.role === "user" && typeof t.text === "string" && !t.kind;

/** The person's latest question in the chat, or "". */
export function lastQuestion(list) {
  for (let i = list.length - 1; i >= 0; i--) if (isQuestion(list[i]) && list[i].text.trim()) return list[i].text;
  return "";
}

/** The question the answer at `at` replied to: the nearest question before it, or "". */
export function questionFor(list, at) {
  if (!(at >= 0 && at < list.length)) return "";
  for (let i = at - 1; i >= 0; i--) if (isQuestion(list[i]) && list[i].text.trim()) return list[i].text;
  return "";
}

/** Copy and Ask again go under an answer in words, not under a problem line, a change card, or the person's own turn. */
export const hasActions = (t) => !!t && t.role === "assistant" && !t.kind && typeof t.text === "string" && t.text.trim() !== "";
