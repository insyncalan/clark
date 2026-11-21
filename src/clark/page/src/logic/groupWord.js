// The `group:` word of the filter field (row 1304): Group by offered in the box as well as in the Group by icon menu. Pure functions, no DOM.
// `g` is the page's grouping: {choices: [[id, label]], current, def, ...}. The choices are the ones the page's own Group by icon menu offers, and
// `current` is the same one the icon menu ticks (one state, two places to set it). A choice made here sets that state; it never stays as text in the box.
import { wordAt } from "./filterQueryUi.js";

export const GROUP_NOTE = "How the list is grouped";      // the note on the field row, as the approved mock-up draws it
const low = (s) => String(s == null ? "" : s).toLowerCase();
const slug = (s) => low(s).replace(/\s+/g, "-");

/** The choice a typed word names (its id, or its label with dashes for spaces), or null. */
export function choiceOf(g, w) {
  const x = slug(w);
  const c = g && (g.choices || []).find(([id, label]) => low(id) === x || slug(label) === x);
  return c ? c[0] : null;
}

/** The text of the chip, "" while the grouping is the page's own start (nothing to show). */
export const chipText = (g) => {
  if (!g || g.current === g.def) return "";
  const c = (g.choices || []).find(([id]) => id === g.current);
  return c ? `Group by: ${c[1]}` : "";
};

/** The suggestions for the word the caret is in, with the `group:` row added to the field list and, after `group:`, the page's choices. */
export function groupOptions(options, text, caret, g) {
  if (!g || !(g.choices || []).length) return options;
  const { word } = wordAt(text, caret), w = low(word), at = w.indexOf(":");
  if (w.startsWith("-")) return options;
  if (at < 0) return !w || "group:".startsWith(w) ? [...options, { kind: "field", ins: "group:", label: "group:", note: GROUP_NOTE, icon: "group", close: false }] : options;
  if (w.slice(0, at) !== "group") return options;
  const part = w.slice(at + 1).replace(/"/g, "");
  return g.choices.filter(([id, label]) => !part || low(id).includes(part) || low(label).includes(part))
    .map(([id, label]) => ({ kind: "value", ins: `group:${id}`, label, note: "", close: true, group: id, checked: id === g.current }));
}

/** Complete `group:value` words the caret has moved past (a space follows each) that name one of the page's choices: {id, text, caret}, the last one
 *  wins (a second `group:` replaces the first), or null. A word naming no choice stays in the text for the line's own sentence. */
export function takeGroup(text, caret, g) {
  if (!g) return null;
  const s = String(text || ""), re = /(^|\s)(group:([^\s"]+))(?=\s)/gi;
  let out = "", at = 0, back = 0, id = null, m;
  while ((m = re.exec(s))) {
    const start = m.index + m[1].length, end = start + m[2].length, c = choiceOf(g, m[3]);
    if (end >= caret || !c) continue;
    let e = end;
    while (e < s.length && /\s/.test(s[e])) e++;
    out += s.slice(at, start); at = e; id = c;
    back += Math.min(e, caret) - start;
  }
  return id === null ? null : { id, text: out + s.slice(at), caret: caret - back };
}

/** The sentence for a complete `group:value` word (a space follows it) that names a choice the page does not offer but the table does: `g.tableOnly` is
 *  [[id, label]] (on the board, "Nothing"). "" when there is none. */
export function groupMissing(g, text, caret) {
  if (!g || !(g.tableOnly || []).length) return "";
  const s = String(text || ""), re = /(^|\s)group:([^\s"]+)(?=\s)/gi;
  let m, out = "";
  while ((m = re.exec(s))) {
    const end = m.index + m[0].length, x = slug(m[2]), t = g.tableOnly.find(([id, label]) => low(id) === x || slug(label) === x);
    if (end < caret && t) out = `${t[1]} is for the table only.`;
  }
  return out;
}
