// Help's state and keys (#82; BRD 5.13, FR-122, FR-123). Edit-served pages only: the published file has no Help, so this is
// reached through edit/index.js and never from the shared components. Help is a layer over the open page: it keeps the address,
// the project and the open view, so Esc puts you back exactly where you were. Plain JS, no JSX.
import { signal, effect } from "@preact/signals";
import { view, project, show, mode, peek, closePeek } from "../stores/report.js";
import { singleKeys } from "../stores/keyPrefs.js";
import { screenOf, shapeContext } from "./peekLogic.js";
import { contextText, articlesFor, placeOf, TABS, firstPlace, placeTitle, trailVisit, trailBack } from "./helpLogic.js";

export const helpOpen = signal(false);
export const helpTab = signal(lastTab());
export const helpTarget = signal(null);          // the place to scroll to and flash, once it is drawn
export const helpQuery = signal("");
export const helpFocusSearch = signal(0);        // bumped to ask the panel to focus the search box
export const helpHere = signal(null);            // the place the reader is at: marked in the contents list, and the one the way back leaves
export const helpTrail = signal([]);             // the places left behind, the latest last (a small history, helpLogic.js trailVisit)
export const landing = { at: 0 };               // when a link last took the reader somewhere (set at once, before the page draws): a scroll that follows is not the reader reading on
export const helpLand = signal(0);               // bumped when a link took the reader to a place, so the panel puts focus on that entry

// The screens Help can take you to today. The others (the Publish box, Preview, ask clark) are named in the text but their
// parts are other items' work: a link to them is drawn as plain words until they exist.
export const LIVE_SCREENS = ["dashboard", "dashboard+edit", "work", "milestones", "settings"];
export const canGo = (to) => LIVE_SCREENS.includes(String(to).split("#")[0]);

function lastTab() {
  try { const t = localStorage.getItem("clark.helpTab"); return TABS.some((x) => x.key === t) ? t : "start"; } catch (e) { return "start"; }
}
function rememberTab(t) {
  try { localStorage.setItem("clark.helpTab", t); } catch (e) { /* the tab is only a convenience */ }
}

/** Open Help at `where` (nothing: the tab used last; a tab name; or a place such as "howto-add-an-item"). The one door the
 *  page's other parts use: window.clarkPage.help.open(where). An unknown place opens the tab used last. */
export function openHelp(where) {
  contextOpen.value = false;                     // the full Help and the peek are never both up (the peek's own link and the profile menu both come here)
  if (!helpOpen.value) opener = locate(document.activeElement);
  const p = placeOf(where, helpTab.value);
  helpTab.value = p.tab;
  rememberTab(p.tab);
  helpTarget.value = p.target;
  helpQuery.value = "";
  helpTrail.value = [];
  helpHere.value = p.target || firstPlace(p.tab);
  helpOpen.value = true;
  return p.known;
}

// Where focus was when Help opened, so closing Help puts it back there. The open page is replaced while Help is open, so a part
// of the page is found again by its place in the page (the child numbers down from <main>), not by the element itself; a part
// outside the page (the top bar) is the same element still.
let opener = null;
function locate(el) {
  // A menu item that opens Help is about to go (the menu closes as it is picked): the opener is the button that opened the menu.
  const dd = el && el.closest && el.closest("[role=menu]") ? el.closest(".dd") : null;
  if (dd) el = dd.querySelector("button[aria-haspopup=menu]") || el;
  if (!el || el === document.body || el === document.documentElement || !el.parentElement) return null;
  const main = document.getElementById("main");
  if (!main || !main.contains(el) || el === main) return { node: el };
  const path = [];
  for (let n = el; n && n !== main; n = n.parentElement) path.unshift(Array.prototype.indexOf.call(n.parentElement.children, n));
  return { path };
}
function giveFocusBack(o) {
  if (!o) return;
  const tryOnce = (left) => {
    let el = o.node || document.getElementById("main");
    if (o.path) for (const i of o.path) el = el && el.children[i];
    if (el && el.isConnected && typeof el.focus === "function") { el.focus(); if (document.activeElement === el) return; }
    if (left > 0) setTimeout(() => tryOnce(left - 1), 30);          // the page is drawn again a moment after Help closes
  };
  setTimeout(() => tryOnce(5), 0);
}

function leave() {
  helpOpen.value = false;
  helpQuery.value = "";
  helpTarget.value = null;
}

/** Close Help and put focus back on what had it when Help opened (if that is still on the page). */
export function closeHelp() {
  const was = helpOpen.value, back = opener;
  opener = null;
  leave();
  if (was) giveFocusBack(back);
}

/** Note that the reader moved on from the place they were at to `to` (the history for the way back). */
function visit(to) {
  helpTrail.value = trailVisit(helpTrail.value, helpHere.value, to);
  helpHere.value = to;
}

export function setTab(t) {
  if (!TABS.some((x) => x.key === t)) return;
  if (t !== helpTab.value) visit(firstPlace(t));
  helpTab.value = t;
  rememberTab(t);
  helpTarget.value = null;
  helpQuery.value = "";
}

/** A link inside Help: its place, and its tab follows from it. */
export function follow(place) {
  const p = placeOf(place, helpTab.value);
  if (!p.known) return;
  visit(p.target);
  arrive(p);
}

function arrive(p) {
  landing.at = performance.now();
  helpTab.value = p.tab;
  rememberTab(p.tab);
  helpQuery.value = "";
  helpTarget.value = null;
  setTimeout(() => { helpTarget.value = p.target; helpLand.value++; }, 0);     // set again so a second click on the same link flashes again
}

/** The place the way back leads to (its title), or null when there is nowhere to go back to. */
export function backPlace() {
  const t = helpTrail.value;
  const p = t.length ? t[t.length - 1] : null;
  return p && placeTitle(p) ? { place: p, title: placeTitle(p) } : null;
}

/** One place back: the place before this one, with no new entry in the history. */
export function goBackPlace() {
  const b = trailBack(helpTrail.value);
  if (!b.place) return;
  const p = placeOf(b.place, helpTab.value);
  helpTrail.value = b.trail;
  if (!p.known) return;
  helpHere.value = p.target;
  arrive(p);
}

/** A link to a screen: Help closes, the screen opens. A settings anchor opens Settings. */
export function goTo(to) {
  const v = String(to).split("#")[0];
  if (!canGo(to)) return false;
  opener = null;                                     // going to another screen: focus does not return to the page left
  leave();
  if (v === "dashboard+edit") { show("dashboard"); mode.value = "edit"; } else show(v);
  return true;
}

// A key that is typed into something is not a shortcut.
function typing(el) {
  if (!el || !el.tagName) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}
function otherLayerOpen() {
  return !!document.querySelector("dialog[open], [role=dialog], [role=menu]");
}

/** "?" opens Help outside a field, a dialog or a menu; in Help it goes to the search box. "/" in Help does the same. Esc closes
 *  Help (the search box clears first). Called once by the page's start-up. */
export function installKeys() {
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "Escape" && contextOpen.value && !document.querySelector("[role=menu]")) { e.preventDefault(); closeContext(); return; }
    if (e.key === "Escape" && helpOpen.value) {
      e.preventDefault();
      if (helpQuery.value) { helpQuery.value = ""; helpTarget.value = null; helpFocusSearch.value++; return; }    // from the box, a result or a tab: clear the search first
      closeHelp(); return;
    }
    if (typing(e.target) || otherLayerOpen()) return;
    if (e.key === "?") { e.preventDefault(); if (helpOpen.value) helpFocusSearch.value++; else if (!toggleContext()) openHelp(); }
    else if (e.key === "/" && helpOpen.value && singleKeys.value) { e.preventDefault(); e.stopImmediatePropagation(); helpFocusSearch.value++; }
  }, true);
  // A click outside the peek closes it (the "?" button is outside, but its own click toggles, so it is let through).
  document.addEventListener("mousedown", (e) => {
    if (!contextOpen.value) return;
    const t = e.target;
    if (t && t.closest && (t.closest("#help-peek") || t.closest("#help-btn"))) return;
    closeContext();
  }, true);
  // Moving to another page or project closes Help, and the peek (it was written for the page it was opened on).
  let seen = view.value + "|" + project.value;
  effect(() => {
    const now = view.value + "|" + project.value;
    if (now !== seen) { seen = now; opener = null; helpOpen.value = false; closeContext({ focus: false }); }
  });
  let was = screenNow();
  effect(() => {
    const now = screenNow();
    if (now !== was) { was = now; closeContext({ focus: false }); }       // the Dashboard to its Edit view is another screen too
  });
  // One right-hand panel at a time: an item peek that opens takes the place of the Help peek.
  effect(() => { if (peek.value) closeContext({ focus: false }); });
}

// ---------- the context peek (#645 steps 3 to 5) ----------
// A right-hand panel with the text for the screen you are on and a link to the full Help. Edit-served pages only (edit/index.js hands
// it over; a published file has no Help and no peek). It opens only for a screen that has context text: contextText(page) in
// helpLogic.js, which is written apart from this. With no such text nothing opens and "?" and the button open the full Help, as before.
export const contextOpen = signal(false);
export const contextScreen = signal("");         // the screen the peek was opened on

let source = null;                                 // a test-only override of contextText (testhook.js sets it; nothing in the served page does)
/** Test seam: use `fn(page)` in place of contextText(page); null puts it back. */
export function useContextText(fn) { source = typeof fn === "function" ? fn : null; }
let closeOthers = () => {};
/** Who else is a right-hand panel, closed when the peek opens (the ask panel; edit/index.js passes it, so this file does not import it). */
export function setCloseOthers(fn) { closeOthers = typeof fn === "function" ? fn : () => {}; }

/** The screen "?" means now: a LIVE_SCREENS name (the Dashboard is its Edit view while you edit). */
export function screenNow() { return screenOf(view.value, mode.value); }

/** The peek's content for a screen, in one shape (peekLogic.js), or null when there is none. */
export function contextOf(screen) {
  const f = source || contextText;
  try {
    const c = shapeContext(f(screen));
    return c ? { ...c, articles: articlesFor(screen), articlesTitle: (TABS.find((t) => t.key === "howto") || {}).name || "" } : null;   // row 896: the how-to articles for this page, under the how-to tab's own word
  } catch (e) { return null; }
}

let peekBack = null;                                // what had focus when the peek opened
const inPanels = (el) => !!(el && el.closest && el.closest("#help-peek, #ask-panel, #peek"));

/** Open the peek for `screen` (nothing: the one now). Closes the item peek and the ask panel first. False when the screen has no text (nothing opens). */
export function openContext(screen) {
  const s = screen || screenNow();
  if (!contextOf(s)) return false;
  if (contextOpen.value) { contextScreen.value = s; return true; }
  const a = document.activeElement;
  peekBack = a && a !== document.body && a !== document.documentElement && !inPanels(a) ? a : null;
  closeOthers();
  if (peek.value) closePeek();
  contextScreen.value = s;
  contextOpen.value = true;
  return true;
}

/** Close the peek. Focus goes back to where it was unless `focus` is false (leaving the page: there is nothing to go back to). */
export function closeContext(o) {
  if (!contextOpen.peek()) return;                   // peek(): called from effects, which must not come to depend on it
  contextOpen.value = false;
  const back = peekBack;
  peekBack = null;
  if (o && o.focus === false) return;
  setTimeout(() => {
    // only when focus is still lost (on the page itself, or in the peek on its way out): a click that landed on a control keeps it
    const at = document.activeElement, p = document.getElementById("help-peek");
    if (at && at !== document.body && at !== document.documentElement && !(p && p.contains(at))) return;
    if (back && back.isConnected && typeof back.focus === "function") back.focus();
    else { const m = document.getElementById("main"); if (m) { m.setAttribute("tabindex", "-1"); m.focus({ preventScroll: true }); } }
  }, 0);
}

/** "?" and the top-bar button: open the peek, or close it when it is open. False when the screen has no text (the caller opens the full Help). */
export function toggleContext() {
  if (contextOpen.value) { closeContext(); return true; }
  return openContext();
}

/** The peek's foot link: close the peek and open the full Help on the entry the text names. Back from Help returns to where the peek was opened. */
export function openFull(place) {
  const c = contextOf(contextScreen.value), back = peekBack;
  peekBack = null;
  contextOpen.value = false;
  if (back && back.isConnected && typeof back.focus === "function") back.focus();   // so Help's Back returns there, not to the link that has just gone
  openHelp(typeof place === "string" ? place : c ? c.full || undefined : undefined);   // an article of the peek (row 896) opens on itself
}
