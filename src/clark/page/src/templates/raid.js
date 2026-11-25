// RAID cards (#96, store types "raid3" and "raid4"): the pure part both of their view and Edit parts use. No DOM, no Preact.
// A card holds a work item's id and where its words come from (src/clark/section_kinds/raid3.py has the content and its rules):
//   { id, source: "client" | "own" | "latest", own }
// The served page reads a section's body (a JSON text) and keeps only the cards publish would keep (logic/publishable.js); the
// published file carries the cards already chosen ({ id, text }) and the rows it kept in its own data, so both end up the same list.
import { publishable, rulesFor } from "../logic/publishable.js";
import { dateWords } from "./safe.js";
import { colourOf } from "../workItems.js";
import { richWords } from "../logic/richWords.js";

export const SIZES = { raid3: 3, raid4: 4 };
export const MANY = 8;          // row 1270: a raid4 body of version 2 (the one library card RAID cards) holds up to eight cards, three or four across
export const OWN_MAX = 400;
export const SOURCES = [["client", "Client wording"], ["own", "Own words"], ["latest", "Latest update"]];
const ID = /^[A-Z][A-Z0-9]{2,6}-(?:([AD])-)?[0-9]{3}$/;
const KIND_OF = { A: "actions", D: "decisions" };

// The kind a card's id belongs to: "raid" (ABC-001), "actions" (ABC-A-001), "decisions" (ABC-D-001), or "" for anything else.
export function kindOfId(id) {
  const m = ID.exec(String(id));
  return m ? (m[1] ? KIND_OF[m[1]] : "raid") : "";
}

// The cards a body holds: [{ id, source, own }]. Anything that is not the saved shape is no cards (never throws).
export function parse(body) {
  let v;
  try { v = typeof body === "string" && body ? JSON.parse(body) : null; } catch (e) { return []; }
  if (!v || !Array.isArray(v.cards)) return [];
  return v.cards.filter((c) => c && typeof c.id === "string" && kindOfId(c.id))
    .map((c) => ({ id: c.id, source: c.source === "own" || c.source === "latest" ? c.source : "client", own: typeof c.own === "string" ? c.own : "", show: showOf(c.show) }));
}

// Row 1270: what a card shows besides its description, { latest, meta, rating }; a key that is not written reads as on.
export const SHOW_KEYS = ["latest", "meta", "rating"];
export function showOf(v) {
  const out = {};
  if (v && typeof v === "object") for (const k of SHOW_KEYS) if (typeof v[k] === "boolean") out[k] = v[k];
  return out;
}
export const shows = (show, key) => !(show && show[key] === false);

// A body's version 2 choice of cards across (3 or 4), or 0 for a body of version 1 (or none), which keeps the number its type has.
export function acrossOf(body) {
  let v;
  try { v = typeof body === "string" && body ? JSON.parse(body) : null; } catch (e) { return 0; }
  return v && v.v === 2 && (v.across === 3 || v.across === 4) ? v.across : 0;
}

// What a raid section draws: how many cards across and the most it holds. The file carries `across` for version 2 (section.across).
export function layoutOf(section, size) {
  const file = Array.isArray(section && section.cards);
  const across = file ? (section.across === 3 || section.across === 4 ? section.across : 0) : acrossOf(section && section.body);
  return across ? { across, max: MANY } : { across: size, max: size };
}

// The body to save for these cards (the server rebuilds it as the one canonical text). `across` (3 or 4) writes version 2.
export function bodyOf(cards, across = 0) {
  const list = cards.map((c) => {
    const one = c.own ? { id: c.id, source: c.source, own: c.own } : { id: c.id, source: c.source };
    if (across && c.show && Object.keys(c.show).length) one.show = showOf(c.show);
    return one;
  });
  return JSON.stringify(across ? { v: 2, across, cards: list } : { v: 1, cards: list });
}

// The words under a card, as the published file chooses them (raid3.py _words).
export function wordsOf(card, row) {
  if (card.source === "own") return richWords(card.own).split(/\s+/).filter(Boolean).join(" ");      // row 1288: the editor's HTML (or an older plain line), as one line of words
  if (card.source === "latest") return kindOfId(card.id) === "actions" ? richWords(row && row.latest_update).trim() : "";
  return richWords(row && row.client_message).trim() || (row ? titleOf(row, kindOfId(card.id)) : "");
}

export const titleOf = (row, kind) => String((kind === "decisions" ? row.decision : row.description) || "").trim();
export function kindWords(row, kind) {
  return kind === "raid" ? (String(row.type || "").toLowerCase() === "issue" ? "Issue" : "Risk") : kind === "actions" ? "Action" : "Decision";
}
// The label above a card's words (row 1270): the part of the item the card shows.
export function partWords(row, kind) {
  return kind === "raid" ? (String(row.type || "").toLowerCase() === "issue" ? "The issue" : "The risk") : kind === "actions" ? "The action" : (row.status === "Pending" ? "The decision needed" : "The decision");
}
// The line under a card's title: status, owner and the date that matters, in plain words.
export function metaBits(row, kind) {
  const who = kind === "decisions" ? row.made_by : row.owner;
  const day = kind === "decisions" ? (row.status === "Pending" ? row.needed_by : row.date) : row.due_date;
  const label = kind === "decisions" ? (row.status === "Pending" ? "needed by" : "made") : "due";
  const bits = [row.status ? String(row.status) : "", who && who !== "TBC" ? `owner ${who}` : "", dateWords(day) ? `${label} ${dateWords(day)}` : ""];
  return bits.filter(Boolean);
}
// The rating a risk or issue card shows, as a word (Red, Amber, Green, Not rated), and the tone the card's edge and band take.
// An action and a decision carry no rating: no word, the brand tone.
export function ratingOf(row, kind) {
  if (kind !== "raid") return { word: "", tone: "rc-b" };
  const c = colourOf(row && row.priority);
  return { word: c.word, tone: "rc-" + c.class };
}
// The impact and likelihood a risk or issue card shows in its foot line ("impact high", "likelihood medium"); nothing unless both are set.
export function ratingBits(row, kind) {
  if (kind !== "raid" || !row || !row.impact || !row.likelihood) return [];
  return [`impact ${String(row.impact).toLowerCase()}`, `likelihood ${String(row.likelihood).toLowerCase()}`];
}
// The item's latest update as plain words ("" when it has none), for every kind of card.
export const latestOf = (row) => richWords(row && row.latest_update).trim();
export const metaOf = (row, kind) => metaBits(row, kind).join(" · ");

// The rules for the served page's data. The published file needs none: it holds only the rows publish kept.
export function rulesOf(data) {
  return rulesFor({
    code: data && data.project && data.project.code, hidden: ((data && data.report_hidden) || []).map((h) => (h && h.item_id) || h), labelRules: (data && data.label_rules) || [],
    labels: (data && data.labels) || {}, sections: (data && data.report_sections) || [], deleted: !!(data && data.sections_deleted),
  });
}

// The row a card points at, or null.
export function rowOf(data, id) {
  const kind = kindOfId(id);
  const row = kind && data && Array.isArray(data[kind]) ? data[kind].find((r) => r && r.id === id) : null;
  return row ? { kind, row } : null;
}

// What the section shows: [{ id, kind, row, text }] in the cards' order. In the file (section.cards, already chosen and kept) a
// card whose row is missing is dropped; in the served page a card is kept only when publishable() keeps its row, as publish does.
export function cardsOf(section, data, size) {
  const file = Array.isArray(section && section.cards);
  const cards = file ? section.cards.filter((c) => c && typeof c.id === "string").map((c) => ({ id: c.id, text: typeof c.text === "string" ? c.text : "", show: showOf(c.show) })) : parse(section && section.body);
  const rules = file ? null : rulesOf(data);
  const out = [];
  for (const c of cards) {
    const found = rowOf(data, c.id);
    if (!found || (rules && !publishable(found.row, found.kind, rules))) continue;
    out.push({ id: c.id, kind: found.kind, row: found.row, text: file ? c.text : wordsOf(c, found.row), show: c.show });
    if (out.length === size) break;
  }
  return out;
}
