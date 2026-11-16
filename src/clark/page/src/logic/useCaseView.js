// The Use case summary view's settings as plain functions with no DOM (row 1234). The editor and a published file both call these,
// so the same settings draw the same list. A setting is { n: a count or "all", scroll: true/false, tracker: "top" | "bottom" | "off" }.
export const ALL = "all";
export const TRACKER_POSITIONS = ["top", "bottom", "off"];
export const DEFAULT_VIEW = { n: 5, scroll: false, tracker: "top" };

// Any stored value (an object or its JSON string) in, a complete setting out. A bad count, flag or position falls back to the default for that one field.
export function normalizeView(raw) {
  let r = raw;
  if (typeof r === "string") { try { r = JSON.parse(r); } catch (e) { r = null; } }
  if (!r || typeof r !== "object") r = {};
  const num = Number(r.n);
  const n = r.n === ALL ? ALL : Number.isInteger(num) && num >= 1 ? num : DEFAULT_VIEW.n;
  const scroll = typeof r.scroll === "boolean" ? r.scroll : DEFAULT_VIEW.scroll;
  const tracker = TRACKER_POSITIONS.includes(r.tracker) ? r.tracker : DEFAULT_VIEW.tracker;
  return { n, scroll, tracker };
}

// How many of `total` rows are drawn straight away, and how many are left to reveal.
export function shownRows(total, view, showAll = false) {
  const v = normalizeView(view), t = Math.max(0, total | 0);
  const shown = showAll || v.n === ALL ? t : Math.min(t, v.n);
  return { shown, hidden: t - shown };
}

// The rows to draw. With "Show all" pressed (or n = all) every row; otherwise the first `n`.
export function visibleItems(items, view, showAll = false) {
  return items.slice(0, shownRows(items.length, view, showAll).shown);
}

// Whether a "Show all" control is wanted: only when some rows are hidden, and the list is not already scrolling.
export function needsShowAll(total, view, showAll = false) {
  const v = normalizeView(view);
  return !v.scroll && shownRows(total, v, showAll).hidden > 0;
}

// Scrolling keeps the list a fixed height of `n` rows and lets the rest scroll; "all" has no height to fix.
export function scrollRows(view) {
  const v = normalizeView(view);
  return v.scroll && v.n !== ALL ? v.n : 0;
}

// Where the tracker is drawn: above the list, below it, or not at all.
export function trackerPlace(view) {
  const t = normalizeView(view).tracker;
  return { above: t === "top", below: t === "bottom", on: t !== "off" };
}

// The view a section holds, { set, n, scroll, tracker }. `fromFile`: the published section's own entry (its n, scroll and tracker sit beside its id and title).
// Otherwise the stored body, which is JSON text; text that can't be read gives the default. `set` is true only when a count was written. Never throws.
export function viewOf(section, fromFile) {
  let v = null;
  if (fromFile) v = section && typeof section === "object" ? section : null;
  else if (section && typeof section.body === "string" && section.body) { try { v = JSON.parse(section.body); } catch (e) { v = null; } }
  if (!v || typeof v !== "object" || Array.isArray(v)) v = null;
  return { set: !!v && v.n !== undefined && v.n !== null, ...normalizeView(v) };
}

// The section's body for a view: the JSON text of { n, scroll, tracker } and nothing else (what viewOf reads back).
export const bodyOf = (view) => JSON.stringify(normalizeView(view));
