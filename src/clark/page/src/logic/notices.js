// Row 1046 (v1.2), piece 1: the notices behind the bell in the top bar, as plain logic with no drawing and no reading of a file.
// A notice is pushed to the running clark (later: from a notices file at a path set in Settings). Here is what is kept of it, which ones
// are shown, and how the unread number and the bell's name are made. Everything is plain text: nothing here is ever read as HTML, and an
// action can only name a place inside clark.

export const SEVERITIES = ["info", "warning", "critical"];
export const LABELS = { info: "Info", warning: "Warning", critical: "Critical" };      // shown as the icon's word, so a colour is never the only sign
export const WORDS = {
  caughtUp: "You are all caught up",
  markRead: "Mark as read",
  markAll: "Mark all as read",
  close: "Close",
};
export const MAX_ITEMS = 30;
export const MAX_DAYS = 90;
export const BADGE_CAP = 9;

const ISO = /^\d{4}-\d\d-\d\d$/;
const text = (v, max) => (typeof v === "string" ? v.replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, max) : "");

/** Whole days since 1970 for a YYYY-MM-DD, never shifted by a time zone; NaN when it is not a real day. */
export function dayNumber(iso) {
  if (typeof iso !== "string" || !ISO.test(iso)) return NaN;
  const [y, m, d] = iso.split("-").map(Number), t = Date.UTC(y, m - 1, d);
  const back = new Date(t);
  return back.getUTCFullYear() === y && back.getUTCMonth() === m - 1 && back.getUTCDate() === d ? t / 86400000 : NaN;
}

/** Compare dotted numbers ("1.0.7" against "1.0.10"): -1, 0, 1; NaN when either is not dotted numbers. */
export function compareVersions(a, b) {
  const part = (v) => (typeof v === "string" && /^\d+(\.\d+){0,3}$/.test(v.trim()) ? v.trim().split(".").map(Number) : null);
  const x = part(a), y = part(b);
  if (!x || !y) return NaN;
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const p = x[i] || 0, q = y[i] || 0;
    if (p !== q) return p < q ? -1 : 1;
  }
  return 0;
}

/** An action may only name a place inside clark: a path from the root ("/settings"), never an address with a scheme or a second slash. */
export function insidePlace(to) {
  return typeof to === "string" && /^\/(?!\/)[A-Za-z0-9/_\-.#?=&]*$/.test(to) && !to.includes("..");
}

/** One notice as kept, or null when it cannot be one (no id, no title, no valid date). The action is dropped, not the notice, when it
 *  is longer than two words or leaves clark. */
export function clean(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = text(raw.id, 80), title = text(raw.title, 80), date = typeof raw.date === "string" ? raw.date : "";
  if (!id || !title || Number.isNaN(dayNumber(date))) return null;
  const severity = SEVERITIES.includes(raw.severity) ? raw.severity : "info";
  const out = { id, severity, title, body: text(raw.body, 240), date };
  if (typeof raw.expires === "string" && !Number.isNaN(dayNumber(raw.expires))) out.expires = raw.expires;
  const below = raw.test && typeof raw.test === "object" ? text(raw.test.installedBelow, 20) : "";
  if (below && !Number.isNaN(compareVersions(below, below))) out.installedBelow = below;
  const a = raw.action && typeof raw.action === "object" ? raw.action : null;
  const label = a ? text(a.label, 30) : "";
  if (a && label && label.split(" ").length <= 2 && insidePlace(a.to)) out.action = { label, to: a.to };
  return out;
}

/** The notices to show today: cleaned, one per id (the newest date wins, then the later one in the list), not expired, not older than 90
 *  days, a test that no longer holds removed (installedBelow: shown only while the installed version is below it; an unknown installed
 *  version keeps it), newest first, at most 30. `today` is YYYY-MM-DD. */
export function visible(list, { today, installed } = {}) {
  const now = dayNumber(today);
  if (Number.isNaN(now) || !Array.isArray(list)) return [];
  const byId = new Map();
  for (const raw of list) {
    const n = clean(raw);
    if (!n) continue;
    const had = byId.get(n.id);
    if (!had || dayNumber(n.date) >= dayNumber(had.date)) byId.set(n.id, n);
  }
  return [...byId.values()]
    .filter((n) => now - dayNumber(n.date) <= MAX_DAYS)
    .filter((n) => !n.expires || dayNumber(n.expires) >= now)
    .filter((n) => !n.installedBelow || !(compareVersions(installed, n.installedBelow) >= 0))
    .sort((a, b) => dayNumber(b.date) - dayNumber(a.date) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
    .slice(0, MAX_ITEMS);
}

/** The ids of the shown notices not yet read. `read` is a list of ids kept in this browser. */
export function unreadIds(shown, read) {
  const done = new Set(Array.isArray(read) ? read : []);
  return shown.filter((n) => !done.has(n.id)).map((n) => n.id);
}

/** The number on the bell: nothing at 0 (the bell is then not drawn at all), the number up to 9, then "9+". */
export function badgeText(count) {
  return !(count > 0) ? "" : count > BADGE_CAP ? `${BADGE_CAP}+` : String(count);
}

/** The bell's accessible name: the true count, not the capped one. */
export function bellName(count) {
  return `Notifications, ${count} unread`;
}

/** True only when there is something unread: the bell is not drawn otherwise. */
export function bellShown(unread) {
  return unread > 0;
}

export function markRead(read, id) {
  const list = Array.isArray(read) ? read : [];
  return list.includes(id) ? list : [...list, id];
}

export function markAllRead(read, shown) {
  return shown.reduce((acc, n) => markRead(acc, n.id), Array.isArray(read) ? read : []);
}

/** Keep the read list from growing for ever: only ids still pushed (before the cut to 30 and 90 days) are kept, so an id that comes
 *  back later is unread again only if it was never seen in what is pushed now. `pushedIds` is every id in the source. */
export function pruneRead(read, pushedIds) {
  const live = new Set(pushedIds);
  return (Array.isArray(read) ? read : []).filter((id) => live.has(id));
}

/** The ids shown now that were not shown before: what the polite live region announces. The first look announces nothing. */
export function arrivals(before, shown) {
  if (!Array.isArray(before)) return [];
  const had = new Set(before);
  return shown.filter((n) => !had.has(n.id)).map((n) => n.id);
}
