// The ask panel's state and keys (#47a). Edit pages only. "/" outside a field opens it (not while a peek is open); Esc or a click outside closes it and puts
// focus back; the width is remembered in this browser (a convenience only). Nothing is sent while asking is off: the status route
// is asked when the panel opens, and until it answers (or when it cannot) the panel reads as off.
import { signal, effect } from "@preact/signals";
import { view, project, peek } from "../stores/report.js";
import { token } from "../stores/report.js";
import { helpOpen } from "../help/helpStore.js";
import { askOn } from "./askState.js";
import { QUIPS } from "./askWords.js";

const MIN = 320, DEFAULT = 420;
const KEY = "clark.askWidth";

export const panelOpen = signal(false);
export const panelState = signal("checking");        // "checking" | "off" | "signed-out" | "ready"
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

/** The next quip: random, never the one just shown. `rand` is Math.random's shape. */
export function nextQuip(prev, rand = Math.random) {
  const rest = QUIPS.filter((q) => q !== prev);
  return rest[Math.min(rest.length - 1, Math.floor(rand() * rest.length))];
}
/** 5 to 10 seconds, in milliseconds. */
export const quipDelay = (rand = Math.random) => 5000 + Math.floor(rand() * 5001);

let opener = null;

async function readStatus() {
  panelState.value = "checking";
  let r = null;
  try {
    const x = await fetch("/api/ask/status", { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    r = { status: x.status, body: await x.json().catch(() => null) };
  } catch (e) { r = null; }
  const b = r && r.status === 200 ? r.body : null;
  if (!panelOpen.value) return;
  if (!b || b.ok !== true || b.ask_enabled !== true) { panelState.value = "off"; panelModel.value = ""; if (b && b.ask_enabled === false) askOn.value = false; return; }
  askOn.value = true;
  panelModel.value = typeof b.model === "string" ? b.model.slice(0, 60) : "";
  panelState.value = b.connected === true ? "ready" : "signed-out";
}

export function openPanel() {
  if (panelOpen.value) { panelFocus.value++; return; }
  const a = document.activeElement;
  opener = a && a !== document.body && a !== document.documentElement ? a : null;
  panelOpen.value = true;
  panelState.value = "checking";           // reads as off-or-checking until the server has answered; nothing is sent meanwhile
  readStatus();
}

export function closePanel() {
  if (!panelOpen.value) return;
  panelOpen.value = false;
  const back = opener;
  opener = null;
  setTimeout(() => {
    if (back && back.isConnected && typeof back.focus === "function") back.focus();
    else { const m = document.getElementById("main"); if (m) { m.setAttribute("tabindex", "-1"); m.focus({ preventScroll: true }); } }
  }, 0);
}

const typing = (el) => !!el && !!el.tagName && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
const otherLayer = () => !!document.querySelector("dialog[open], [role=dialog], [role=menu]");

export function installAskKeys() {
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panelOpen.value) { e.preventDefault(); closePanel(); return; }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    // An open peek keeps "/" for its own two slashes (the words box); the ask button still opens the panel there.
    if (e.key === "/" && !e.defaultPrevented && !typing(e.target) && !otherLayer() && !helpOpen.value && !peek.value) { e.preventDefault(); openPanel(); }
  }, true);
  document.addEventListener("mousedown", (e) => {
    if (!panelOpen.value) return;
    const p = document.getElementById("ask-panel");
    if (p && !p.contains(e.target)) closePanel();
  }, true);
  let seen = view.value + "|" + project.value;
  effect(() => {
    const now = view.value + "|" + project.value;
    if (now !== seen) { seen = now; turns.value = []; if (panelOpen.value) { panelOpen.value = false; opener = null; } }
  });
}
