// The ask panel's state and keys (#47a). Edit pages only. "/" outside a field (or Ctrl or Cmd + J anywhere) opens it (not while a peek is open); Esc, Close or the ask button closes it (a click outside does not) and puts
// focus back; the width is remembered in this browser (a convenience only). Nothing is sent while asking is off: the status route
// is asked when the panel opens, and until it answers (or when it cannot) the panel reads as off.
import { signal } from "@preact/signals";
import { peek } from "../stores/report.js";
import { helpOpen } from "../help/helpStore.js";
import { singleKeys } from "../stores/keyPrefs.js";
import { askOn, askProvider } from "./askState.js";
import { keptCheck, runCheck } from "./askCheck.js";
import { chatId, histOpen, openChatOf, rememberOpen } from "./askHistory.js";
import { DISCONNECTED_LINE } from "./askWords.js";

const MIN = 320, DEFAULT = 420;
const KEY = "clark.askWidth";

export const panelOpen = signal(false);
export const panelDisconnected = signal(false);      // #54: Disconnect was pressed in Settings, so "not signed in" would be untrue
export const panelState = signal("checking");        // "checking" | "unknown" (the check failed: nothing is claimed) | "off" (the server said off) | "signed-out" | "ready"
export const panelModel = signal("");                 // the model's name when the status route gives one
export const panelWidth = signal(initialWidth());
export const panelFocus = signal(0);                  // bumped to ask the panel to focus its question box
export const turns = signal([]);                       // the chat: [{role: "user" | "assistant", text, kind?}]; kept while the panel is closed
export const pending = signal(false);                  // a question is out
export const queue = signal([]);                       // row 1220: messages typed while an answer is made, [{id, text}] in the order they are sent; kept only while the panel is open
export const queueHeld = signal("");                   // row 1220: "" (the queue goes on by itself), "stopped" or "failed" (it waits for Send the waiting messages or Clear)
export const queueDrop = signal(0);                    // row 1220: the number of waiting messages the person has been told would be dropped
export const QUEUE_MAX = 5;
export const answersReady = signal(0);                 // row 1292: answers that landed while the panel was closed; cleared when it opens
export const chatEpoch = signal(0);                    // row 1119: kept for a chat that is dropped while an answer is out; row 1292: leaving a page or project no longer bumps it

function room() { return Math.max(MIN, Math.floor(document.documentElement.clientWidth * 0.9)); }     // clientWidth: never the scrollbar's width

export function widthRange() { return { min: MIN, max: room() }; }      // the same limits clampWidth keeps to; the grip tells them to a screen reader
export function clampWidth(w) { return Math.min(room(), Math.max(MIN, Math.round(Number(w) || DEFAULT))); }
function initialWidth() {
  try { const w = parseInt(localStorage.getItem(KEY), 10); if (w >= MIN) return clampWidth(w); } catch (e) { /* only a convenience */ }
  return clampWidth(DEFAULT);
}
export function setWidth(w, keep) {
  panelWidth.value = clampWidth(w);
  if (keep) { try { localStorage.setItem(KEY, String(panelWidth.value)); } catch (e) { /* only a convenience */ } }
}

let opener = null;

async function readStatus() {
  const kept = keptCheck();
  if (kept) { apply(kept); return; }            // row 858: asked a moment ago and it was ready: no second wait
  panelState.value = "checking";
  const b = await runCheck();
  if (!panelOpen.value) return;
  apply(b);
}

function apply(b) {
  // Only a good answer that says "off" reads as off. A check that failed (the request threw, the status was not 200, the body was not a
  // good answer) says nothing about the switch, so the panel claims nothing and sends nothing.
  if (!b || b.ok !== true || typeof b.ask_enabled !== "boolean") { panelState.value = "unknown"; panelModel.value = ""; return; }
  if (b.ask_enabled === false) { panelState.value = "off"; panelModel.value = ""; askOn.value = false; return; }
  askOn.value = true;
  panelModel.value = typeof b.model === "string" ? b.model.slice(0, 60) : "";
  panelDisconnected.value = b.why === DISCONNECTED_LINE;
  if (typeof b.provider === "string") askProvider.value = b.provider;
  panelState.value = b.connected === true ? "ready" : "signed-out";
}

export function openPanel() {
  if (panelOpen.value) { panelFocus.value++; return; }
  const a = document.activeElement;
  opener = a && a !== document.body && a !== document.documentElement ? a : null;
  panelOpen.value = true;
  answersReady.value = 0;
  panelState.value = "checking";           // reads as checking until the server has answered; no off or signed-out line and nothing is sent meanwhile
  readStatus();
}

/** Row 1220: the one place the queue is changed, so a changed list is never held, nor a drop warning kept, for a list it was not about. */
export function setQueue(list) {
  queue.value = list;
  queueDrop.value = 0;
  if (!list.length) queueHeld.value = "";
}
/** Row 1220: leaving with messages waiting says so first; the same press again goes on. True when it may go on. */
export function mayDrop() {
  const n = queue.value.length;
  if (!n || queueDrop.value === n) return true;
  queueDrop.value = n;
  return false;
}

/** A new chat: the earlier turns are dropped, so nothing from them is sent again. Not while a question is out. */
export function newChat() {
  if (pending.value || !mayDrop()) return;
  setQueue([]);
  turns.value = [];
  chatId.value = null; histOpen.value = false;
}

export function closePanel(force) {
  if (!panelOpen.value) return;
  if (force !== true && !mayDrop()) return;
  setQueue([]);
  panelOpen.value = false;
  const back = opener;
  opener = null;
  setTimeout(() => {
    // Only when focus is still lost (on the page itself, or in the panel on its way out): if something took it in the meantime
    // (a peek that opened, a button the click outside landed on), it stays there.
    const at = document.activeElement, p = document.getElementById("ask-panel");
    if (at && at !== document.body && at !== document.documentElement && !(p && p.contains(at))) return;
    if (back && back.isConnected && typeof back.focus === "function") back.focus();
    else { const m = document.getElementById("main"); if (m) { m.setAttribute("tabindex", "-1"); m.focus({ preventScroll: true }); } }
  }, 0);
}

const typing = (el) => !!el && !!el.tagName && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
const otherLayer = () => !!document.querySelector("dialog[open], [role=dialog], [role=menu]");

export function installAskKeys() {
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !e.isComposing && panelOpen.value) { e.preventDefault(); closePanel(); return; }
    // Ctrl or Cmd + J (row 855, the prototype's): opens the panel from anywhere, a field included (it types nothing), as Ctrl or Cmd + K does for the palette.
    if ((e.key || "").toLowerCase() === "j" && (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && !e.isComposing && !e.defaultPrevented) {
      if (otherLayer() || helpOpen.value) return;
      e.preventDefault();
      if (!e.repeat) openPanel();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    // An open peek, or a use case open in Edit (it has the words box), keeps "/" for its own two slashes (the words box); the ask button still opens the panel there.
    if (e.key === "/" && singleKeys.value && !e.defaultPrevented && !typing(e.target) && !otherLayer() && !helpOpen.value && !peek.value && !document.querySelector("[data-ucd] .ucd-acts")) { e.preventDefault(); openPanel(); }
  }, true);
  // row 1292 slice 1: a click outside, a change of page or of project no longer closes the panel or drops the chat; only Close, Esc or the ask button close it, and none of them stops an answer.
  // row 1292 slice 8: a chat belongs to its project. A change of page keeps the chat; a change of project shows that project's own chat (the one it was left
  // on, else an empty one) and the first is back on return. The answered chats are kept in Earlier chats, and the one each project is on is kept beside them,
  // so a page that loads again for another project (a brand of its own) still finds it. An answer still out for the old project is not added to the new chat.
  let seen = view.value + "|" + project.value, seenProject = project.value;
  const resume = (p) => { const c = openChatOf(p); turns.value = c ? c.turns.map((t) => ({ ...t })) : []; chatId.value = c ? c.id : null; };
  resume(seenProject);
  effect(() => { rememberOpen(seenProject, chatId.value); });
  effect(() => {
    const now = view.value + "|" + project.value, p = project.value;
    if (now === seen) return;
    seen = now;
    if (p !== seenProject) { seenProject = p; chatEpoch.value++; setQueue([]); histOpen.value = false; resume(p); }
  });
}
