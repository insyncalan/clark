// Row 1217: an ask clark answer drawn formatted. The answer is model text and is never read as markup: this module turns a small, listed
// set of marks into plain data (blocks of nodes) and the panel draws that data with elements it makes itself, every word in a text node.
// The listed marks: **bold**, *italic* and _italic_, `code`, ``` fenced code ```, # to ###### headings, "- " "* " "+ " bullets, "1. " numbers,
// a blank line between paragraphs, a single line break kept. Everything else (links, images, tables, quotes, any < >) stays as the text it is.
// The stored answer is never changed; this only decides how the text is drawn, so the claims check (it reads the server's copy) and the
// kept chats see the model's own words.

const ESC = /^[\s]/;
const bounded = (s, a, b) => s.slice(a, b).length > 0 && !ESC.test(s[a]) && !ESC.test(s[b - 1]);
const wordChar = (c) => !!c && /[A-Za-z0-9]/.test(c);

/** One line's text as nodes: {t:"text",v} {t:"strong",c} {t:"em",c} {t:"code",v}. A mark with no closing partner stays as written. */
export function inline(s) {
  const out = [];
  let buf = "";
  const flush = () => { if (buf) { out.push({ t: "text", v: buf }); buf = ""; } };
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    if (c === "`") {
      const j = s.indexOf("`", i + 1);
      if (j > i + 1) { flush(); out.push({ t: "code", v: s.slice(i + 1, j) }); i = j + 1; continue; }
    } else if (c === "*" && s[i + 1] === "*") {
      const j = s.indexOf("**", i + 2);
      if (j > i + 2 && bounded(s, i + 2, j)) { flush(); out.push({ t: "strong", c: inline(s.slice(i + 2, j)) }); i = j + 2; continue; }
    } else if (c === "*" || c === "_") {
      let j = s.indexOf(c, i + 1);
      while (j > 0 && c === "*" && s[j + 1] === "*" && j + 1 < s.length) j = s.indexOf(c, j + 2);   // a bold inside the italic is not its end
      if (j > i + 1 && bounded(s, i + 1, j) && (c === "*" || (s[i - 1] !== "_" && s[i + 1] !== "_" && s[j - 1] !== "_" && s[j + 1] !== "_" && !wordChar(s[i - 1]) && !wordChar(s[j + 1])))) {   // a doubled underscore (window.__x) is text
        flush(); out.push({ t: "em", c: inline(s.slice(i + 1, j)) }); i = j + 1; continue;
      }
    }
    buf += c; i++;
  }
  flush();
  return out;
}

const HEAD = /^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$/;
const BULLET = /^[ \t]*[-*+][ \t]+(.*)$/;
const NUMBER = /^[ \t]*(\d{1,4})[.)][ \t]+(.*)$/;
const FENCE = /^ {0,3}```/;

/** The answer's blocks: {t:"h",level,c} {t:"p",lines:[nodes]} {t:"ul"|"ol",start,items:[[lines]]} {t:"pre",v}. */
export function parseAnswer(text) {
  const lines = String(text == null ? "" : text).replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let para = null, list = null;
  const endPara = () => { if (para) { blocks.push({ t: "p", lines: para.map(inline) }); para = null; } };
  const endAll = () => { endPara(); list = null; };
  for (let n = 0; n < lines.length; n++) {
    const line = lines[n];
    if (FENCE.test(line)) {
      endAll();
      const body = [];
      n++;
      while (n < lines.length && !FENCE.test(lines[n])) body.push(lines[n++]);
      blocks.push({ t: "pre", v: body.join("\n") });
      continue;
    }
    if (!line.trim()) { endAll(); continue; }
    let m = HEAD.exec(line);
    if (m) { endAll(); blocks.push({ t: "h", level: Math.min(m[1].length, 3), c: inline(m[2]) }); continue; }
    m = BULLET.exec(line);
    const num = m ? null : NUMBER.exec(line);
    if (m || num) {
      endPara();
      const kind = m ? "ul" : "ol";
      if (!list || list.t !== kind) { list = { t: kind, start: num ? Number(num[1]) : 1, items: [] }; blocks.push(list); }
      list.items.push([inline(m ? m[1] : num[2])]);
      continue;
    }
    if (list && /^[ \t]+\S/.test(line)) { list.items[list.items.length - 1].push(inline(line.trim())); continue; }   // a wrapped item line
    list = null;
    (para || (para = [])).push(line.trim());
  }
  endPara();
  return blocks;
}

/** For an answer that arrives in pieces: the text so far with an unfinished mark closed or dropped, so no lone "**" shows. Not used by a
 *  whole answer (the answer comes in one piece today); here so a streamed one cannot flash symbols. */
export function closeOpen(text) {
  let s = String(text == null ? "" : text);
  const fences = (s.match(/^ {0,3}```/gm) || []).length;
  if (fences % 2) return s + "\n```";
  const at = s.lastIndexOf("\n") + 1, last = s.slice(at);
  const bold = (last.match(/\*\*/g) || []).length;
  if (bold % 2) return /\*\*\s*$/.test(last) ? s.replace(/\s*\*\*\s*$/, "") : s.replace(/\s+$/, "") + "**";
  if ((last.match(/`/g) || []).length % 2) return /`\s*$/.test(last) ? s.replace(/\s*`\s*$/, "") : s.replace(/\s+$/, "") + "`";
  return s.replace(/(^|[ \t])[*_]$/, "$1");
}
