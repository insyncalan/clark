// Row 1292 (feature 9): what Copy puts on the clipboard, the question Ask again sends, and the question Up-arrow brings back.
// The answer is drawn from askFormat.js's blocks; the copy is made from the same blocks, so what is pasted is what is read.
import { parseAnswer } from "./askFormat.js";

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const htmlNodes = (list) => list.map((n) => n.t === "strong" ? "<strong>" + htmlNodes(n.c) + "</strong>" : n.t === "em" ? "<em>" + htmlNodes(n.c) + "</em>" : n.t === "code" ? "<code>" + esc(n.v) + "</code>" : esc(n.v)).join("");
const plainNodes = (list) => list.map((n) => n.c ? plainNodes(n.c) : n.v).join("");
const htmlLines = (lines) => lines.map(htmlNodes).join("<br>");
const plainLines = (lines) => lines.map(plainNodes).join("\n");

/** The answer as formatted text (bold, headings, lists) that pastes into Word or an email. Every word is escaped. */
export function answerHtml(text) {
  return parseAnswer(text).map((b) => {
    if (b.t === "h") return "<h" + (b.level + 2) + ">" + htmlNodes(b.c) + "</h" + (b.level + 2) + ">";
    if (b.t === "p") return "<p>" + htmlLines(b.lines) + "</p>";
    if (b.t === "pre") return "<pre><code>" + esc(b.v) + "</code></pre>";
    return "<" + b.t + (b.t === "ol" && b.start !== 1 ? " start=\"" + Number(b.start) + "\"" : "") + ">" + b.items.map((it) => "<li>" + htmlLines(it) + "</li>").join("") + "</" + b.t + ">";
  }).join("");
}

/** The same answer as plain text: marks gone, lists as "- " and "1. ", a blank line between blocks. */
export function answerPlain(text) {
  return parseAnswer(text).map((b) => {
    if (b.t === "h") return plainNodes(b.c);
    if (b.t === "p") return plainLines(b.lines);
    if (b.t === "pre") return b.v;
    const first = b.t === "ol" ? b.start : 1;
    return b.items.map((it, k) => (b.t === "ol" ? (first + k) + ". " : "- ") + plainLines(it)).join("\n");
  }).join("\n\n");
}

/** Puts both forms on the clipboard (the plain form alone where the browser cannot take both). Resolves true when it worked. */
export async function copyAnswer(text, nav = typeof navigator === "undefined" ? null : navigator, Item = typeof ClipboardItem === "undefined" ? null : ClipboardItem) {
  try {
    const html = answerHtml(text), plain = answerPlain(text);
    const cb = nav && nav.clipboard;
    if (!cb) return false;
    if (Item && typeof cb.write === "function") await cb.write([new Item({ "text/html": new Blob([html], { type: "text/html" }), "text/plain": new Blob([plain], { type: "text/plain" }) })]);
    else await cb.writeText(plain);
    return true;
  } catch (e) { return false; }
}

const isQuestion = (t) => !!t && t.role === "user" && !t.kind && typeof t.text === "string" && t.text.trim() !== "";

/** Copy and Ask again go under an answer in words, not under a problem line, a change card, or the person's own turn. */
export const hasActions = (t) => !!t && t.role === "assistant" && !t.kind && typeof t.text === "string" && t.text.trim() !== "";

/** The question that gave answer `i`: the nearest question before it. "" when there is none. */
export function questionBefore(turns, i) {
  for (let k = i - 1; k >= 0; k--) if (isQuestion(turns[k])) return turns[k].text;
  return "";
}

/** Up-arrow in an empty box: the person's questions, newest first. `at` is how many were brought back already (0 for the first press);
 *  returns {text, at} for the next one, stopping at the oldest, or null when there is no question. */
export function recallStep(turns, at) {
  const mine = turns.filter(isQuestion);
  if (!mine.length) return null;
  const n = Math.min(mine.length, at + 1);
  return { text: mine[mine.length - n].text, at: n };
}
