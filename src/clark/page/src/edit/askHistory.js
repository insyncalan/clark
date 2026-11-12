// Row 1095: the earlier chats in the ask clark panel of one project, kept in this browser on this computer (a per-project store, like the page's other
// remembered things). Newest first, at most KEEP of them; the title is the first question. Every read and write can fail: then nothing is kept.
import { signal } from "@preact/signals";
import { project } from "../stores/report.js";
import { recall, remember } from "../logic/remember.js";
import { nowMs } from "../workItems.js";

export const KEEP = 30;
export const chatId = signal(null);      // the stored chat the panel is showing, or null for one not yet kept
export const histOpen = signal(false);   // the list of earlier chats is showing in place of the chat
export const histTick = signal(0);       // bumped when the store changes, so the list is read again

const key = () => "askChats." + (project.value || "");

export function chats() {
  const l = recall(key(), []);
  return Array.isArray(l) ? l.filter((c) => c && typeof c.id === "string" && Array.isArray(c.turns)) : [];
}

const plain = (t) => ({ role: t.role, text: String(t.text), ...(t.kind ? { kind: t.kind } : {}), ...(t.sources && t.sources.length ? { sources: t.sources } : {}) });

/** Keeps the chat as it stands: a new entry the first time, the same entry after. Only a chat that has an answer is kept. */
export function keepChat(turns, now = nowMs()) {
  const kept = turns.filter((t) => t && (t.role === "user" || t.role === "assistant") && (!t.kind || t.kind === "note") && typeof t.text === "string");
  const first = kept.find((t) => t.role === "user");
  if (!first || !kept.some((t) => t.role === "assistant" && !t.kind)) return;
  const all = chats(), id = chatId.value || String(now);
  const entry = { id, at: now, title: first.text.trim().slice(0, 120), turns: kept.map(plain) };
  chatId.value = id;
  remember(key(), [entry, ...all.filter((c) => c.id !== id)].slice(0, KEEP));
  histTick.value++;
}

export function deleteChat(id) {
  remember(key(), chats().filter((c) => c.id !== id));
  if (chatId.value === id) chatId.value = null;
  histTick.value++;
}

export const when = (at) => new Date(at).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
