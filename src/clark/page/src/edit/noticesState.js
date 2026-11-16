// Row 1046, piece 2: what the bell holds. The notices are pushed to the running clark (pushNotices; the file at a path set in Settings is a later piece);
// which are shown and how many are unread come from logic/notices.js. Read ids are kept per person in this browser (try/catch: a private window keeps them for this visit only).
import { signal, computed } from "@preact/signals";
import { visible, unreadIds, markRead, markAllRead, pruneRead, arrivals } from "../logic/notices.js";

const KEY = "clark.notices-read";
const saved = () => { try { const v = JSON.parse(localStorage.getItem(KEY) || "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; } catch (e) { return []; } };
const keep = (list) => { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* kept for this visit only */ } };

const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

export const pushed = signal([]);                 // everything pushed, as given
export const installed = signal(undefined);       // the installed version, when known (a notice's version test)
export const readIds = signal(saved());
export const announced = signal("");              // the line the polite live region says: new arrivals only
export const noticesOpen = signal(false);

export const shown = computed(() => visible(pushed.value, { today: today(), installed: installed.value }));
export const unread = computed(() => unreadIds(shown.value, readIds.value));

let seen = null;                                  // the ids shown before the last push; null until the first look, which announces nothing
export function pushNotices(list) {
  pushed.value = Array.isArray(list) ? list : [];
  const ids = shown.value.map((n) => n.id);
  const fresh = arrivals(seen, shown.value).filter((id) => !readIds.value.includes(id));
  seen = ids;
  announced.value = fresh.length ? (fresh.length === 1 ? shown.value.find((n) => n.id === fresh[0]).title : `${fresh.length} new notifications`) : "";
  const pruned = pruneRead(readIds.value, pushed.value.map((n) => n && n.id));
  if (pruned.length !== readIds.value.length) { readIds.value = pruned; keep(pruned); }
}
export function readOne(id) { readIds.value = markRead(readIds.value, id); keep(readIds.value); }
export function readAll() { readIds.value = markAllRead(readIds.value, shown.value); keep(readIds.value); }
