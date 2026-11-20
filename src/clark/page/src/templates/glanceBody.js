// Glance template (row 1264, slice 4): the body of a "glancetemplate" section as the Edit part reads and writes it. Pure: no DOM, no
// clock. The same reading as section_kinds/glancetemplate.py upgrade (every field at its default) and the same canonical writing as its
// check (a field that holds its default is not sent). Typed tiles (bespoke) are changed here by the tile editor (slice 6): added, replaced,
// dropped or hidden, one new body each; the text is trimmed and a field that holds its default is left out, as the server's check does.
import { tiles, TILE_TITLES, HEALTH_WORDS, shownRag, tileWord } from "../glanceTiles.js";
import { source } from "./notes.js";
import { TONES } from "./glanceLimits.js";

export const BUILT_IN = ["health", "overdue", "risks", "decisions"];
export const SETTLED = BUILT_IN.slice(1);
const OUTLINES = ["R", "A", "G", "N"];
export const PER_ROWS = [3, 4];       // tiles on a line at full width (row 1264 slice 9), as section_kinds/glancetemplate.py PER_ROW; half width always draws 2
export const PER_ROW = 4;             // the default, not stored
const flag = (v, d) => (typeof v === "boolean" ? v : d);

/** The body with every field present, as upgrade() in the Python kind gives it. */
export function readBody(section) {
  const v = source(section), h = v.health && typeof v.health === "object" ? v.health : {}, b = v.builtin && typeof v.builtin === "object" ? v.builtin : {};
  const bespoke = (Array.isArray(v.bespoke) ? v.bespoke : []).filter((t) => t && typeof t === "object" && typeof t.id === "string" && !BUILT_IN.includes(t.id));
  const ids = [...BUILT_IN, ...bespoke.map((t) => t.id)], order = [];
  for (const i of [...(Array.isArray(v.order) ? v.order.filter((i) => ids.includes(i)) : []), ...ids]) if (!order.includes(i)) order.push(i);
  const builtin = {};
  for (const n of SETTLED) { const s = b[n] && typeof b[n] === "object" ? b[n] : {}; builtin[n] = { hidden: flag(s.hidden, false), outline: OUTLINES.includes(s.outline) ? s.outline : "" }; }
  const fresh = !(section && ((section.content && typeof section.content === "object") || (typeof section.body === "string" && section.body)));      // never written: a NEW template starts with the health eye off (ticket 1264); a body with no health field is an existing page and shows it
  return { v: 1, health: { shown: flag(h.shown, !fresh), own_row: flag(h.own_row, false) }, per_row: PER_ROWS.includes(v.per_row) ? v.per_row : PER_ROW, order, builtin, bespoke };
}

/** One own tile as it is sent: id and label, the typed fields trimmed and left out when empty, the tone left out when neutral, hidden when true. */
export function cleanTile(t) {
  const out = { id: t.id, label: String(t.label || "").trim() };
  for (const k of ["figure", "tag", "note"]) { const v = typeof t[k] === "string" ? t[k].trim() : ""; if (v) out[k] = v; }
  if (TONES.includes(t.tone) && t.tone !== "neutral") out.tone = t.tone;
  if (t.hidden === true) out.hidden = true;
  return out;
}

/** The id for a new own tile: "t" and the lowest number no tile of the section has. */
export function nextId(u) {
  const used = new Set(u.bespoke.map((t) => t.id));
  let n = 1;
  while (used.has(`t${n}`)) n++;
  return `t${n}`;
}

/** The body to send: defaults left out, so one content is always the same text. */
export function compact(u) {
  const out = { v: 1 };
  const health = {};
  if (!u.health.shown) health.shown = false;
  if (u.health.own_row) health.own_row = true;
  if (Object.keys(health).length) out.health = health;
  if (u.per_row !== PER_ROW) out.per_row = u.per_row;
  if (u.bespoke.length) out.bespoke = u.bespoke.map(cleanTile);
  const built = {};
  for (const n of SETTLED) { const s = {}; if (u.builtin[n].hidden) s.hidden = true; if (u.builtin[n].outline) s.outline = u.builtin[n].outline; if (Object.keys(s).length) built[n] = s; }
  if (Object.keys(built).length) out.builtin = built;
  const def = [...BUILT_IN, ...u.bespoke.map((t) => t.id)];
  if (u.order.join() !== def.join()) out.order = u.order;
  return out;
}

/** `u` with one change: {hide: [key, bool]} | {outline: [key, "" | R | A | G]} | {order: [ids]} | {ownRow: bool} | {perRow: 3 | 4} | {put: tile} (a new own tile goes last in the order, a known
 * id is replaced where it is) | {drop: id} (an own tile). A new object; `u` is not touched. */
export function withChange(u, c) {
  const n = { ...u, health: { ...u.health }, builtin: Object.fromEntries(SETTLED.map((k) => [k, { ...u.builtin[k] }])), order: u.order.slice(), bespoke: u.bespoke.map((t) => ({ ...t })) };
  if (c.hide) {
    const [key, hidden] = c.hide, own = n.bespoke.find((t) => t.id === key);
    if (own) own.hidden = hidden; else if (key === "health") n.health.shown = !hidden; else n.builtin[key].hidden = hidden;
  }
  if (c.put) {
    const at = n.bespoke.findIndex((t) => t.id === c.put.id);
    if (at < 0) { n.bespoke.push({ ...c.put }); n.order.push(c.put.id); } else n.bespoke[at] = { ...c.put };
  }
  if (c.drop) { n.bespoke = n.bespoke.filter((t) => t.id !== c.drop); n.order = n.order.filter((i) => i !== c.drop); }
  if (c.outline) n.builtin[c.outline[0]].outline = c.outline[1];
  if (c.order) n.order = c.order;
  if ("ownRow" in c) n.health.own_row = c.ownRow;
  if ("perRow" in c) n.per_row = c.perRow;
  return n;
}

/** All ids in `order` with `key` moved before `before` (a drawn id, or null: after the last drawn id). `drawn` are the ids the page shows. */
export function moved(order, key, before, drawn) {
  const rest = order.filter((i) => i !== key);
  const at = before === null ? Math.max(...drawn.filter((i) => i !== key).map((i) => rest.indexOf(i))) + 1 : rest.indexOf(before);
  rest.splice(at, 0, key);
  return rest;
}

/** The built-in tiles to draw, in the section's order, hidden ones kept (Edit draws them dimmed): the shape allTiles (glanceTiles.js) gives. */
export function builtinTiles(u, rows, today, project) {
  const by = Object.fromEntries(tiles(rows, today).map((t) => [t.key, t])), health = (project && project.health) || "";
  by.health = { key: "health", label: TILE_TITLES.health, value: health || "Not set", detail: "", rag: HEALTH_WORDS[health] || "n", filter: null, reason: (project && project.health_reason) || "" };
  return u.order.filter((k) => BUILT_IN.includes(k)).map((key) => {
    const outline = key === "health" ? "" : u.builtin[key].outline, rag = shownRag(outline, by[key].rag);
    return { ...by[key], hidden: key === "health" ? !u.health.shown : u.builtin[key].hidden, outline, auto: by[key].rag, rag, word: tileWord(key, rag, outline, HEALTH_WORDS[health] || "") };
  });
}

// Does an At a glance section of this report show Project health too? The built-in section (type glance) always does; the template (type glancetemplate) does
// while its own eye is on (readBody: a never-written one starts off). A section hidden from the published report does not count. (Row 1261.)
export const glanceShowsHealth = (sections) => (sections || []).filter((s) => !s.hidden).some((s) => s.type === "glance" || (s.type === "glancetemplate" && readBody(s).health.shown));
