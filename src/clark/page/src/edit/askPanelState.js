// The ask panel's state and keys (#47a). Edit pages only. "/" outside a field (or Ctrl or Cmd + J anywhere) opens it (not while a peek is open); Esc, Close or the ask button closes it (a click outside does not) and puts
// focus back; the width is remembered in this browser (a convenience only). Nothing is sent while asking is off: the status route
// is asked when the panel opens, and until it answers (or when it cannot) the panel reads as off.
import { signal, effect } from "@preact/signals";
import { peek, project } from "../stores/report.js";
import { helpOpen } from "../help/helpStore.js";
import { singleKeys } from "../stores/keyPrefs.js";
import { askOn, askProvider } from "./askState.js";
import { keptCheck, runCheck } from "./askCheck.js";
import { chatId, histOpen } from "./askHistory.js";
import { QUIPS, DISCONNECTED_LINE } from "./askWords.js";
import { askNewRead } from "./publishApi.js";

const MIN = 320, DEFAULT = 420;
const KEY = "clark.askWidth";

export const panelOpen = signal(false);
export const panelDocker = signal("");                  // Row 1293: the server's "not available in the Docker version" sentence when clark runs in Docker, else ""
export const panelDisconnected = signal(false);      // #54: Disconnect was pressed in Settings, so "not signed in" would be untrue
export const panelState = signal("checking");        // "checking" | "unknown" (the check failed: nothing is claimed) | "off" (the server said off) | "signed-out" | "ready"
export const panelModel = signal("");                 // the model's name when the status route gives one
export const panelStanding = signal(false);            // #1292 S13: the status route says standing instructions are set (the card that sets them is #1294)
export const panelWidth = signal(initialWidth());
export const panelFocus = signal(0);                  // bumped to ask the panel to focus its question box
export const turns = signal([]);                       // the chat: [{role: "user" | "assistant", text, kind?}]; kept while the panel is closed
export const pending = signal(false);                  // a question is out
export const queue = signal([]);                       // row 1220: messages typed while an answer is made, [{id, text}] in the order they are sent; kept only while the panel is open
export const queueHeld = signal("");                   // row 1220: "" (the queue goes on by itself), "stopped" or "failed" (it waits for Send them or Clear)
export const queueDrop = signal(0);                    // row 1220: the number of waiting messages the person has been told would be dropped
export const QUEUE_MAX = 5;
export const draft = signal(null);                     // row 1292 (S12): the Draft open beside the panel, {html, title, sec} (askDraft.js readDraft), or null; closing the panel or leaving the chat closes it, the report is unchanged
export const subject = signal(null);                   // row 1292: what "Ask about this" was pressed on, {kind: "item" | "section" | "use case", id, name}, or null; shown as a chip the person can remove
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

/** Row 1292: a double-click on the grip puts the panel back to its usual width and forgets the kept one, so the next visit opens at the usual width too. */
export function resetWidth() {
  panelWidth.value = clampWidth(DEFAULT);
  try { localStorage.removeItem(KEY); } catch (e) { /* only a convenience */ }
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
// One deck for the whole session of the panel (not one per question), so no quip comes round again until all have been shown,
// and the one that ended a question never opens the next.
let deck = [], lastQuip = "";
/** The next quip to show, drawn from the one deck. */
export function drawQuip(rand = Math.random) {
  lastQuip = nextQuip(deck, lastQuip, rand);
  return lastQuip;
}
/** 5 to 10 seconds, in milliseconds. */
export const quipDelay = (rand = Math.random) => 5000 + Math.floor(rand() * 5001);

let opener = null;

async function readStatus() {
  const kept = keptCheck();
  if (kept) { apply(kept); await hereCheck(); return; }            // row 858: asked a moment ago and it was ready: no second connection check
  panelState.value = "checking";
  const b = await runCheck();
  if (!panelOpen.value) return;
  apply(b);
  await hereCheck();
}

// Row 1294: the connection check above is for the computer, not for a project. A project whose own asking is off reads as off here BEFORE anything is sent (the server
// refuses it too). Fail closed: while this is out the panel reads as checking, and a read that fails reads as unknown, which sends nothing.
async function hereCheck() {
  const was = panelState.value, code = project.value;
  if ((was !== "ready" && was !== "signed-out") || !code) return;
  panelState.value = "checking";
  const r = await askNewRead(code);
  if (!panelOpen.value || panelState.value !== "checking" || project.value !== code) return;
  if (r.status === 404 && r.body && r.body.code === "not_found") { panelState.value = was; return; }      // a server with no settings store has no per-project value to read (the server always has one when run for real)
  const b = r.body;
  if (!(r.status === 200 && b && b.ok === true && typeof b.off_here === "boolean")) { panelState.value = "unknown"; return; }
  if (b.off_here) { panelState.value = "off"; panelModel.value = ""; panelStanding.value = false; return; }
  panelState.value = was;
}

function apply(b) {
  // Only a good answer that says "off" reads as off. A check that failed (the request threw, the status was not 200, the body was not a
  // good answer) says nothing about the switch, so the panel claims nothing and sends nothing.
  if (!b || b.ok !== true || typeof b.ask_enabled !== "boolean") { panelState.value = "unknown"; panelModel.value = ""; panelStanding.value = false; return; }
  if (b.ask_enabled === false) { panelState.value = "off"; panelModel.value = ""; panelStanding.value = false; askOn.value = false; return; }
  askOn.value = true;
  panelModel.value = typeof b.model === "string" ? b.model.slice(0, 60) : "";
  panelStanding.value = b.standing_instructions === true;
  panelDisconnected.value = b.why === DISCONNECTED_LINE;
  panelDocker.value = b.docker === true && typeof b.why === "string" && b.why.length <= 300 ? b.why : "";
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

export const handed = signal(null);                    // S11: a question the quick bar handed over, {text, send}, until the panel has taken it

/** S11: the quick bar's ask row. Opens the panel; the panel takes the words (into its box, or asked at once when `send`). */
export function handOver(text, send) {
  handed.value = { text: String(text), send: send === true };
  openPanel();
}

/** Row 1292: the sparkle: the panel opens (or takes focus) with a chip naming what it was pressed on. */
export function askAbout(what) {
  subject.value = what && what.id ? { kind: String(what.kind || "item"), id: String(what.id), name: String(what.name || what.id), project: project.value } : null;
  if (panelOpen.value) panelFocus.value++; else openPanel();
}

// Row 1292: the chip names a row of one project, so it goes when the project changes (the panel and the chat stay).
effect(() => { const s = subject.value; if (s && s.project !== project.value) subject.value = null; });

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
  draft.value = null;
  subject.value = null;
  turns.value = [];
  chatId.value = null; histOpen.value = false;
}

export function closePanel(force) {
  if (!panelOpen.value) return;
  if (force !== true && !mayDrop()) return;
  setQueue([]);
  draft.value = null;
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
  // Row 1292: the panel's width is on the page as --ask-w (0 while it is shut), so a peek opened from an answer sits left of the panel, not behind it.
  effect(() => { document.documentElement.style.setProperty("--ask-w", panelOpen.value ? clampWidth(panelWidth.value) + "px" : "0px"); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !e.isComposing && panelOpen.value && !document.getElementById("ask-slash")) {   // the slash menu is open: the first Esc is the menu's (it closes, the panel stays)
      if (draft.value && e.target && e.target.closest && e.target.closest("#ask-draft")) return;      // row 1292: Esc in the Draft is the Draft's (it closes its menu, then itself), the panel stays
      e.preventDefault(); closePanel(); return;
    }
    // Ctrl or Cmd + J (row 855, the prototype's): opens the panel from anywhere, a field included (it types nothing), as Ctrl or Cmd + K does for the palette. Row 1292: pressed again it closes it (closing never stops an answer).
    if ((e.key || "").toLowerCase() === "j" && (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && !e.isComposing && !e.defaultPrevented) {
      if (otherLayer() || helpOpen.value) return;
      e.preventDefault();
      if (!e.repeat) { if (panelOpen.value) closePanel(); else openPanel(); }
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    // An open peek, or a use case open in Edit (it has the words box), keeps "/" for its own two slashes (the words box); the ask button still opens the panel there.
    if (e.key === "/" && singleKeys.value && !e.defaultPrevented && !typing(e.target) && !otherLayer() && !helpOpen.value && !peek.value && !document.querySelector("[data-ucd] .ucd-acts")) { e.preventDefault(); openPanel(); }
  }, true);
  // row 1292 slice 1: a click outside, a change of page or of project no longer closes the panel or drops the chat; only Close, Esc or the ask button close it, and none of them stops an answer.
}
