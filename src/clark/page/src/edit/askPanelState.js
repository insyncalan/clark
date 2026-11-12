// The ask panel's state and keys (#47a). Edit pages only. "/" outside a field (or Ctrl or Cmd + J anywhere) opens it (not while a peek is open); Esc or a click outside closes it and puts
// focus back; the width is remembered in this browser (a convenience only). Nothing is sent while asking is off: the status route
// is asked when the panel opens, and until it answers (or when it cannot) the panel reads as off.
import { signal, effect } from "@preact/signals";
import { view, project, peek } from "../stores/report.js";
import { helpOpen } from "../help/helpStore.js";
import { askOn, askProvider } from "./askState.js";
import { keptCheck, runCheck } from "./askCheck.js";
import { chatId, histOpen } from "./askHistory.js";
import { QUIPS, DISCONNECTED_LINE } from "./askWords.js";

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

function room() { return Math.max(MIN, Math.floor(document.documentElement.clientWidth * 0.9)); }     // clientWidth: never the scrollbar's width

export function clampWidth(w) { return Math.min(room(), Math.max(MIN, Math.round(Number(w) || DEFAULT))); }
function initialWidth() {
  try { const w = parseInt(localStorage.getItem(KEY), 10); if (w >= MIN) return clampWidth(w); } catch (e) { /* only a convenience */ }
  return clampWidth(DEFAULT);
}
export function setWidth(w, keep) {
  panelWidth.value = clampWidth(w);
  if (keep) { try { localStorage.setItem(KEY, String(panelWidth.value)); } catch (e) { /* only a convenience */ } }
}

/** A deck of every quip index in a random order (Fisher-Yates). `rand` is Math.random's shape. */
export function quipDeal(rand = Math.random) {
  const d = QUIPS.map((_, i) => i);
  for (let i = d.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [d[i], d[j]] = [d[j], d[i]]; }
  return d;
}
/** The next quip from a deck (an array of indexes, dealt from the end): a fresh shuffled deck when it runs out, never the one just
 * shown first. Returns the quip text; the deck is changed in place. */
export function nextQuip(deck, prev, rand = Math.random) {
  if (!deck.length) {
    deck.push(...quipDeal(rand));
    const top = deck.length - 1;
    if (deck.length > 1 && QUIPS[deck[top]] === prev) [deck[0], deck[top]] = [deck[top], deck[0]];
  }
  return QUIPS[deck.pop()];
}
/** 5 to 10 seconds, in milliseconds. */
export const quipDelay = (rand = Math.random) => 5000 + Math.floor(rand() * 5001);

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
  panelState.value = "checking";           // reads as checking until the server has answered; no off or signed-out line and nothing is sent meanwhile
  readStatus();
}

/** A new chat: the earlier turns are dropped, so nothing from them is sent again. Not while a question is out. */
export function newChat() {
  if (pending.value) return;
  turns.value = [];
  chatId.value = null; histOpen.value = false;
}

export function closePanel() {
  if (!panelOpen.value) return;
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
    if (e.key === "Escape" && panelOpen.value) { e.preventDefault(); closePanel(); return; }
    // Ctrl or Cmd + J (row 855, the prototype's): opens the panel from anywhere, a field included (it types nothing), as Ctrl or Cmd + K does for the palette.
    if ((e.key || "").toLowerCase() === "j" && (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && !e.isComposing && !e.defaultPrevented) {
      if (otherLayer() || helpOpen.value) return;
      e.preventDefault();
      if (!e.repeat) openPanel();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    // An open peek, or a use case open in Edit (it has the words box), keeps "/" for its own two slashes (the words box); the ask button still opens the panel there.
    if (e.key === "/" && !e.defaultPrevented && !typing(e.target) && !otherLayer() && !helpOpen.value && !peek.value && !document.querySelector("[data-ucd] .ucd-acts")) { e.preventDefault(); openPanel(); }
  }, true);
  document.addEventListener("mousedown", (e) => {
    if (!panelOpen.value) return;
    const p = document.getElementById("ask-panel");
    if (p && !p.contains(e.target)) closePanel();
  }, true);
  let seen = view.value + "|" + project.value;
  effect(() => {
    const now = view.value + "|" + project.value;
    if (now !== seen) { seen = now; turns.value = []; chatId.value = null; histOpen.value = false; if (panelOpen.value) { panelOpen.value = false; opener = null; } }
  });
}
