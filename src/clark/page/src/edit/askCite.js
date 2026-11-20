// Row 1292: numbered citations. The answer is model text; the server says which real items it names (reply.items, first mention first, each once).
// This module only decides where the numbers go: after each mention of a named item's ID, the number that item has in the Used line. It reads no markup.
const ESCAPE = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** The kind an ID opens: "milestone" (-M-), "usecase" (-U-, no peek: it has its own page) or "item". */
export function kindOf(id) {
  return /-M-/.test(id) ? "milestone" : /-U-/.test(id) ? "usecase" : "item";
}

/** The sources an answer shows: the items it named that open beside the panel, numbered 1.. in the order given. [{n, id, kind}] */
export function sourcesOf(items) {
  const out = [], seen = new Set();
  for (const i of Array.isArray(items) ? items : []) {
    if (!i || typeof i.id !== "string" || !i.id || seen.has(i.id) || kindOf(i.id) === "usecase") continue;
    seen.add(i.id);
    out.push({ n: out.length + 1, id: i.id, kind: kindOf(i.id) });
  }
  return out;
}

/** One text as pieces: {t:"text", v} and {t:"cite", id, n} after each whole-word mention of a source's ID. With no sources the text comes back whole. */
export function pieces(text, sources) {
  const s = String(text == null ? "" : text);
  if (!sources || !sources.length) return [{ t: "text", v: s }];
  const num = new Map(sources.map((x) => [x.id, x.n]));
  const re = new RegExp("(?<![A-Za-z0-9-])(" + sources.map((x) => ESCAPE(x.id)).sort((a, b) => b.length - a.length).join("|") + ")(?![A-Za-z0-9-])", "g");
  const out = [];
  let at = 0, m;
  while ((m = re.exec(s))) {
    out.push({ t: "text", v: s.slice(at, m.index + m[0].length) });
    out.push({ t: "cite", id: m[1], n: num.get(m[1]) });
    at = m.index + m[0].length;
  }
  if (at < s.length || !out.length) out.push({ t: "text", v: s.slice(at) });
  return out;
}
