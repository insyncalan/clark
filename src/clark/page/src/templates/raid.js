// RAID cards (#96, store types "raid3" and "raid4"): the pure part both of their view and Edit parts use. No DOM, no Preact.
// A card holds a work item's id and where its words come from (src/clark/section_kinds/raid3.py has the content and its rules):
//   { id, source: "client" | "own" | "latest", own }
// The served page reads a section's body (a JSON text) and keeps only the cards publish would keep (logic/publishable.js); the
// published file carries the cards already chosen ({ id, text }) and the rows it kept in its own data, so both end up the same list.
import { publishable, rulesFor } from "../logic/publishable.js";
import { dateWords } from "./safe.js";

export const SIZES = { raid3: 3, raid4: 4 };
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
    .map((c) => ({ id: c.id, source: c.source === "own" || c.source === "latest" ? c.source : "client", own: typeof c.own === "string" ? c.own : "" }));
}

// The body to save for these cards (the server rebuilds it as the one canonical text).
export function bodyOf(cards) {
  return JSON.stringify({ v: 1, cards: cards.map((c) => (c.own ? { id: c.id, source: c.source, own: c.own } : { id: c.id, source: c.source })) });
}

// The words under a card, as the published file chooses them (raid3.py _words).
export function wordsOf(card, row) {
  if (card.source === "own") return card.own || "";
  if (card.source === "latest") return kindOfId(card.id) === "actions" ? String((row && row.latest_update) || "").trim() : "";
  return String((row && row.client_message) || "").trim();
}

export const titleOf = (row, kind) => String((kind === "decisions" ? row.decision : row.description) || "").trim();
export function kindWords(row, kind) {
  return kind === "raid" ? (String(row.type || "").toLowerCase() === "issue" ? "Issue" : "Risk") : kind === "actions" ? "Action" : "Decision";
}
// The line under a card's title: status, owner and the date that matters, in plain words.
export function metaOf(row, kind) {
  const who = kind === "decisions" ? row.made_by : row.owner;
  const day = kind === "decisions" ? (row.status === "Pending" ? row.needed_by : row.date) : row.due_date;
  const label = kind === "decisions" ? (row.status === "Pending" ? "needed by" : "made") : "due";
  const bits = [row.status ? String(row.status) : "", who && who !== "TBC" ? `owner ${who}` : "", dateWords(day) ? `${label} ${dateWords(day)}` : ""];
  return bits.filter(Boolean).join(" · ");
}

// The rules for the served page's data. The published file needs none: it holds only the rows publish kept.
export function rulesOf(data) {
  return rulesFor({
    code: data && data.project && data.project.code, hidden: ((data && data.report_hidden) || []).map((h) => (h && h.item_id) || h), labelRules: (data && data.label_rules) || [],
    labels: (data && data.labels) || {}, sections: (data && data.report_sections) || [],
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
  const cards = file ? section.cards.filter((c) => c && typeof c.id === "string").map((c) => ({ id: c.id, text: typeof c.text === "string" ? c.text : "" })) : parse(section && section.body);
  const rules = file ? null : rulesOf(data);
  const out = [];
  for (const c of cards) {
    const found = rowOf(data, c.id);
    if (!found || (rules && !publishable(found.row, found.kind, rules))) continue;
    out.push({ id: c.id, kind: found.kind, row: found.row, text: file ? c.text : wordsOf(c, found.row) });
    if (out.length === size) break;
  }
  return out;
}
