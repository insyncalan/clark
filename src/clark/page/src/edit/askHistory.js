// Row 1095: the earlier chats in the ask clark panel of one project, kept in this browser on this computer (a per-project store, like the page's other
// remembered things). Newest first, at most KEEP of them; the title is the first question. Every read and write can fail: then nothing is kept.
import { signal } from "@preact/signals";
import { project } from "../stores/report.js";
import { recall, remember } from "../logic/remember.js";
import { HISTORY_UNTITLED } from "./askWords.js";
import { nowMs } from "../workItems.js";

export const KEEP = 30;
export const MAX_TEXT = 20000;   // one turn kept at most this long, so 30 chats stay well inside the browser's store (about 5 MB)
export const chatId = signal(null);      // the stored chat the panel is showing, or null for one not yet kept
export const histOpen = signal(false);   // the list of earlier chats is showing in place of the chat
export const histTick = signal(0);       // bumped when the store changes, so the list is read again

const key = (p = project.value) => "askChats." + (p || "");
const openKey = (p) => "askOpen." + (p || "");

export function chats(p = project.value) {
  const l = recall(key(p), []);
  return Array.isArray(l) ? l.filter((c) => c && typeof c.id === "string" && Array.isArray(c.turns)) : [];
}

const plain = (t) => ({ role: t.role, text: String(t.text).slice(0, MAX_TEXT), ...(t.kind ? { kind: t.kind } : {}), ...(t.sources && t.sources.length ? { sources: t.sources } : {}) });

/** Keeps the chat as it stands: a new entry the first time, the same entry after. Only a chat that has an answer is kept. */
export function keepChat(turns, now = nowMs(), into = null) {
  const kept = turns.filter((t) => t && (t.role === "user" || t.role === "assistant") && (!t.kind || t.kind === "note") && typeof t.text === "string");
  const first = kept.find((t) => t.role === "user");
  if (!first || !kept.some((t) => t.role === "assistant" && !t.kind)) return;
  // `into` ({ project, id }): an answer that came back after the project was changed is kept in the chat of the project it was asked in, not in the one on screen.
  const pr = into ? into.project : project.value, all = chats(pr), id = (into ? into.id : chatId.value) || String(now);
  const entry = { id, at: now, title: first.text.trim().slice(0, 120) || HISTORY_UNTITLED(when(now)), turns: kept.map(plain) };
  if (!into) chatId.value = id;
  // The store can be full: drop the oldest other chat and try again, until the newest chat itself is kept (or nothing more can go).
  const others = all.filter((c) => c.id !== id).slice(0, KEEP - 1);
  for (;;) {
    if (remember(key(pr), [entry, ...others]) || !others.length) break;
    others.pop();
  }
  histTick.value++;
  return id;
}

export function deleteChat(id) {
  remember(key(), chats().filter((c) => c.id !== id));
  if (chatId.value === id) chatId.value = null;
  histTick.value++;
}

/** #1292 slice 8: the chat each project was left on (its id, kept like the chats are), so a change of project, or the page loading again for one, comes back to it. */
export function rememberOpen(p, id) { remember(openKey(p), id || null); }
export function openChatOf(p) {
  const id = recall(openKey(p), null);
  return typeof id === "string" ? chats(p).find((c) => c.id === id) || null : null;
}

export function when(at) { return new Date(at).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
