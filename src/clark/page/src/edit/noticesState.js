// Row 1046, piece 2: what the bell holds. The notices are pushed to the running clark (pushNotices; the file at a path set in Settings feeds it, see loadNotices below);
// which are shown and how many are unread come from logic/notices.js. Read ids are kept per person in this browser (try/catch: a private window keeps them for this visit only).
import { signal, computed } from "@preact/signals";
import { noticesRead } from "./publishApi.js";
import { zoneFetch } from "../api.js";
import { todayIso } from "../workItems.js";
import { visible, unreadIds, markRead, markAllRead, pruneRead, arrivals } from "../logic/notices.js";

const KEY = "clark.notices-read";
const saved = () => { try { const v = JSON.parse(localStorage.getItem(KEY) || "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; } catch (e) { return []; } };
const keep = (list) => { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* kept for this visit only */ } };

const today = todayIso; // the clock is read in workItems.js only

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

// Row 1046, piece 3: the notices come from the file or folder set in Settings, read by the server (GET /api/notices): once when the editor
// starts, then every few minutes. An answer that is not a good one (offline, no such route, a bad body) changes nothing, so a share that
// is away never empties the bell or shows an error; a good empty answer does (the file was cleared).
export const REFRESH_MS = 5 * 60 * 1000;
export async function loadNotices() {
  const r = await noticesRead();
  const b = r && r.body;
  if (r && r.status === 200 && b && b.ok === true && Array.isArray(b.notices) && b.why !== "away") pushNotices(b.notices);
  return r && r.status;
}
// The installed version, for a notice's version test (installedBelow): read once from this server's own /health answer (server.health_answer; no outbound call).
// An answer that is not a plain x.y.z leaves it unknown, and an unknown version keeps the notice.
export async function loadInstalled() {
  try {
    const r = await zoneFetch("/health", { cache: "no-store" });
    const b = r && r.status === 200 ? await r.json() : null;
    if (b && typeof b.version === "string" && /^\d+\.\d+\.\d+$/.test(b.version)) installed.value = b.version;
  } catch (e) { /* stays unknown */ }
  return installed.value;
}
let timer = null;
export function startNotices() {
  if (timer) return;
  loadNotices();
  timer = setInterval(loadNotices, REFRESH_MS);
}
export function stopNotices() { if (timer) { clearInterval(timer); timer = null; } }
