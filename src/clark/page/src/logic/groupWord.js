// Row 1304: Group by in the Work items filter field. The field list ends with the word `group:`, and after it the field offers the choices
// the Group by icon menu has (the same GROUPS, in the same order; the board has no Nothing). Pure functions, no DOM and no store: the
// filter box (components/FilterLine.jsx) owns the state. `group:` is not a filter: it is never kept in the line, a pick sets the grouping
// (the one state the icon menu shows too) and leaves nothing in the box.
import { GROUPS, DEFAULT_STATE, boardGroup, groupLabel } from "./board.js";

export const GROUP_NOTE = "How the list is grouped";
export const BOARD_NOTHING = "A board is always grouped, so choose one of its seven groupings.";
export const START_GROUP = DEFAULT_STATE.group;

const low = (s) => String(s || "").toLowerCase();
const ids = (onBoard) => GROUPS.map((g) => g.id).filter((id) => !onBoard || id !== "nothing");

/** The group choice (or "") the table or board shows now. */
export const currentGroup = (group, onBoard) => (onBoard ? boardGroup(group) : group);

/** The rows the field offers for the word being typed: the `group:` row (last in the field list) or, after `group:`, the choices.
 *  Each: {kind, ins, label, note?, group?: id, checked?, close}. [] when the word is neither. */
export function groupRows(word, current, onBoard) {
  const w = low(word), i = w.indexOf(":");
  if (i < 0) return !w || "group".startsWith(w) ? [{ kind: "field", ins: "group:", label: "group:", note: GROUP_NOTE, icon: "group", close: false }] : [];
  if (w.slice(0, i) !== "group") return [];
  const part = w.slice(i + 1).replace(/"/g, "");
  return GROUPS.filter((g) => ids(onBoard).includes(g.id) && (g.id.startsWith(part) || low(g.label).startsWith(part)))
    .map((g) => ({ kind: "value", ins: `group:${g.id}`, label: g.label, group: g.id, checked: g.id === current, close: true }));
}

const WORD = /(^|\s)(group:[a-z]*)(?=\s|$)/gi;
const prefixOf = (v, onBoard) => ids(onBoard).concat(onBoard ? ["nothing"] : []).some((id) => id.startsWith(low(v)));

/** The text with each `group:<start of a choice>` word replaced by letters of the same length, so the parser reads it as a plain word and
 *  never calls it an unknown field; `unmask` puts the typed letters back into the drawn pieces. */
export function mask(text, onBoard) {
  return String(text || "").replace(WORD, (m, lead, w) => (prefixOf(w.slice(6), onBoard) ? lead + "x".repeat(w.length) : m));
}
export function unmask(pieces, text) {
  let at = 0;
  return pieces.map((p) => { const t = String(text).slice(at, at + p.text.length); at += p.text.length; return { ...p, text: t }; });
}

/** A complete `group:<choice>` word the caret has moved past (a space follows it): {id, text, caret} with the word taken out, or null. */
export function takeGroup(text, caret, onBoard) {
  const s = String(text || "");
  const re = /(^|\s)(group:([a-z]+))(?=\s)/gi;
  let m;
  while ((m = re.exec(s))) {
    const start = m.index + m[1].length, end = start + m[2].length, id = low(m[3]);
    if (end >= caret || !GROUPS.some((g) => g.id === id)) continue;
    let e = end;
    while (e < s.length && /\s/.test(s[e])) e++;
    return { id, board: onBoard && id === "nothing", text: s.slice(0, start) + s.slice(e), caret: Math.max(0, caret - (e - start)) };
  }
  return null;
}

/** The chip text and whether it can be removed, or null: shown when the grouping is not the start one. */
export function groupChip(group, onBoard) {
  const g = currentGroup(group, onBoard);
  return g === START_GROUP ? null : { text: `Group by: ${groupLabel(g)}`, cross: !onBoard };
}
