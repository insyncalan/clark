// The At a glance tiles on the Dashboard (#79; rules as in glance.py, the reference, and the prototype's glanceData): plain
// functions with no DOM and no clock (today is passed in). Each tile counts with the SAME filter state it opens Work items with
// (filters.js applyFilters), so the number on a tile is always the number of rows in the list it opens.
import { applyFilters, initial, setType, setFilter } from "./filters.js";
import { isOpen, dueField, showDate, dayNumber, plural } from "./workItems.js";

const state = (type, field, values) => setFilter(setType(initial(), type), field, values, false);

// Overdue actions: open actions due before today. High risks and issues: open risks, issues, assumptions and dependencies rated
// Urgent or High. Decisions needed: decisions still Pending.
export const FILTERS = {
  overdue: state("action", "due", ["overdue"]),
  risks: state("risk", "priority", ["Urgent", "High"]),
  decisions: state("decision", "status", ["Pending"]),
};
export const HEALTH_WORDS = { "On track": "g", "At risk": "a", "Off track": "r" };

/** The tiles after Project health, in order: [{key, label, value, detail, rag ("g" "a" "r"), filter}]. */
export function tiles(rows, today) {
  const n = (s) => applyFilters(rows, s, today).length;
  const open = (type) => rows.filter((r) => isOpen(r) && (type === "action" ? r.kind === "action" : r.kind !== "action" && r.kind !== "decision")).length;
  const over = n(FILTERS.overdue), high = n(FILTERS.risks), dec = applyFilters(rows, FILTERS.decisions, today);
  const dates = dec.map((r) => dueField(r)).filter((d) => dayNumber(d) !== null).sort();
  const risksOpen = open("risk");
  return [
    { key: "overdue", label: "Overdue actions", value: over, detail: `of ${plural(open("action"), "open action")}`, rag: over ? "r" : "g", filter: FILTERS.overdue },
    { key: "risks", label: "High risks and issues", value: high, detail: high ? `of ${risksOpen} open` : risksOpen ? "None high" : "None open", rag: high ? "r" : risksOpen ? "a" : "g", filter: FILTERS.risks },
    { key: "decisions", label: "Decisions needed", value: dec.length, detail: dates.length ? `Oldest ${showDate(dates[0])}` : dec.length ? "No date set" : "None waiting", rag: dec.length ? "a" : "g", filter: FILTERS.decisions },
  ];
}

// The optional Not reviewed tile (#160): open items not reviewed in N days. It is not one of the four starting tiles, so `tiles` does
// not return it; the Dashboard adds it only when the eye has turned it on. Its filter is the Freshness filter, in Open mode, so the
// number is the number of rows in the list it opens. `days` is the project's setting (stores/review.js), passed in with today.
export function notReviewedTile(rows, today, days) {
  const filter = setFilter(initial(), "reviewed", ["stale"], false);
  const value = applyFilters(rows, filter, today).length;
  return { key: "stale", label: "Not reviewed", value, detail: `in ${plural(days, "day")}`, rag: value ? "a" : "g", filter };
}

// A tile's status in words as well as colour (#140: colour is never the only signal; the prototype's C.tileWord, views.js). The
// word follows the colour the tile shows, automatic or set by hand: green "On track", amber "At risk", red "Off track". Three tiles
// say it more exactly: red Overdue actions are "Overdue", amber Decisions needed are "Waiting", and High risks and issues are
// "Watch" (amber) or "High" (red), so a count of risks never reads as late. Project health's word sits beside a pill that may say
// something else, so it says what it is: "Tile colour: Off track". No colour has no word. Never a colour name.
export const TILE_WORDS = { g: "On track", a: "At risk", r: "Off track" };
export const TILE_WORDS_OF = { overdue: { r: "Overdue" }, decisions: { a: "Waiting" }, risks: { a: "Watch", r: "High" } };
const OPTIONAL_WORDS_OF = { stale: { a: "Needs a look" } };      // the optional tile (#160); kept apart so TILE_WORDS_OF stays the prototype's table
export const HEALTH_WORD_LABEL = "Tile colour: ";

/** The plain word for a tile, or "" for none. `key` is the tile (health, overdue, risks, decisions); `rag` is the colour it shows
 *  ("g" "a" "r", or "n"/"" for no colour; capitals are taken too); `outline` is its glance_tiles.outline ("" automatic, "R" "A" "G"
 *  set by hand, "N" No colour by hand). Project health keeps its pill, so it gets a word only when its colour is set by hand and
 *  differs from the pill's (`pill`: the pill's letter, as HEALTH_WORDS gives it), labelled "Tile colour: " so it is not read as a
 *  second health. */
export function tileWord(key, rag, outline = "", pill = "") {
  const hand = String(outline || "").toLowerCase(), c = hand === "n" ? "" : String(rag || "").toLowerCase();
  if (key === "health") return TILE_WORDS[hand] && hand !== String(pill || "").toLowerCase() && TILE_WORDS[c] ? HEALTH_WORD_LABEL + TILE_WORDS[c] : "";
  return (TILE_WORDS_OF[key] || OPTIONAL_WORDS_OF[key] || {})[c] || TILE_WORDS[c] || "";
}

// ── The tiles as the page draws them (#45) ───────────────────────────────────────────────────────────────────────────────
// The rows of glance_tiles (hidden, outline, sort_order) say which tiles show, in what order and with what outline. A project with
// no rows yet has the four tiles in this order with Decisions needed hidden (glance.py DEFAULT_HIDDEN, the reference).
export const TILE_KEYS = ["health", "overdue", "risks", "decisions"];
export const TILE_TITLES = { health: "Project health", overdue: "Overdue actions", risks: "High risks and issues", decisions: "Decisions needed" };
export const DEFAULT_HIDDEN = ["decisions"];
export const OUTLINE_CHOICES = [["", "Automatic"], ["G", "Green"], ["A", "Amber"], ["R", "Red"], ["N", "No colour"]];

/** {order: [keys], hidden: Set, outlines: {key: ""|R|A|G|N}} from glance_tiles rows (as glance.tile_settings does). */
export function layout(glanceRows) {
  const rows = (glanceRows || []).filter((r) => TILE_KEYS.includes(r.tile)).slice().sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || TILE_KEYS.indexOf(a.tile) - TILE_KEYS.indexOf(b.tile));
  const order = [...new Set(rows.map((r) => r.tile))];
  for (const k of TILE_KEYS) if (!order.includes(k)) order.push(k);
  const by = Object.fromEntries(rows.map((r) => [r.tile, r]));
  const hidden = new Set(TILE_KEYS.filter((k) => (by[k] ? !!by[k].hidden : DEFAULT_HIDDEN.includes(k))));
  const outlines = Object.fromEntries(rows.map((r) => [r.tile, r.outline || ""]));
  return { order, hidden, outlines };
}

/** The colour a tile shows: the hand-set outline if there is one ("N" is none), else the automatic colour. g a r n. */
export const shownRag = (outline, auto) => (outline ? (outline === "N" ? "n" : outline.toLowerCase()) : auto || "n");

/** Every tile in order, hidden ones kept (Edit draws them dimmed; View leaves them out). Project health is first in the default order. */
export function allTiles(rows, today, project, glanceRows) {
  const lay = layout(glanceRows), by = Object.fromEntries(tiles(rows, today).map((t) => [t.key, t]));
  const health = (project && project.health) || "";
  by.health = { key: "health", label: TILE_TITLES.health, value: health || "Not set", detail: "", rag: HEALTH_WORDS[health] || "n", filter: null, reason: (project && project.health_reason) || "" };
  return lay.order.map((key) => {
    const t = by[key], outline = lay.outlines[key] || "";
    return { ...t, hidden: key !== "health" && lay.hidden.has(key),            // Project health is always in the published file (#89), so it cannot be hidden
     outline, auto: t.rag, rag: shownRag(outline, t.rag), word: tileWord(key, shownRag(outline, t.rag), outline, HEALTH_WORDS[health] || "") };
  });
}

/** Where to send a move of `key` one step (dir -1 earlier, +1 later) in `order`: {before: key|null}, or null when it is already at that end. */
export function stepTile(order, key, dir) {
  const i = order.indexOf(key), j = i + dir;
  if (i < 0 || j < 0 || j >= order.length) return null;
  return { before: dir < 0 ? order[j] : order[j + 1] || null };
}

/** The file's own figures (data.glance.tiles, publish.add_glance) as tiles to draw: colour G A R N or "" is its letter lower-cased. */
export function fileTiles(glance, project) {
  const health = (project && project.health) || "";
  return ((glance && glance.tiles) || []).map((t) => {
    const rag = String(t.colour || "").toLowerCase() || "n";
    return t.tile === "health"
      ? { key: "health", label: TILE_TITLES.health, value: health || "Not set", detail: "", rag: HEALTH_WORDS[health] || rag, reason: (project && project.health_reason) || "", outline: t.outline || "", word: "" }
      : { key: t.tile, label: t.label, value: t.value, detail: t.detail, rag, outline: t.outline || "", word: tileWord(t.tile, rag, t.outline || "") };
  });
}
