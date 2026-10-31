// Help's state and keys (#82; BRD 5.13, FR-122, FR-123). Edit-served pages only: the published file has no Help, so this is
// reached through edit/index.js and never from the shared components. Help is a layer over the open page: it keeps the address,
// the project and the open view, so Esc puts you back exactly where you were. Plain JS, no JSX.
import { signal, effect } from "@preact/signals";
import { view, project, show, mode } from "../stores/report.js";
import { singleKeys } from "../stores/keyPrefs.js";
import { placeOf, TABS } from "./helpLogic.js";

export const helpOpen = signal(false);
export const helpTab = signal(lastTab());
export const helpTarget = signal(null);          // the place to scroll to and flash, once it is drawn
export const helpQuery = signal("");
export const helpFocusSearch = signal(0);        // bumped to ask the panel to focus the search box

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
  if (!helpOpen.value) opener = locate(document.activeElement);
  const p = placeOf(where, helpTab.value);
  helpTab.value = p.tab;
  rememberTab(p.tab);
  helpTarget.value = p.target;
  helpQuery.value = "";
  helpOpen.value = true;
  return p.known;
}

// Where focus was when Help opened, so closing Help puts it back there. The open page is replaced while Help is open, so a part
// of the page is found again by its place in the page (the child numbers down from <main>), not by the element itself; a part
// outside the page (the top bar) is the same element still.
let opener = null;
function locate(el) {
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

export function setTab(t) {
  if (!TABS.some((x) => x.key === t)) return;
  helpTab.value = t;
  rememberTab(t);
  helpTarget.value = null;
  helpQuery.value = "";
}

/** A link inside Help: its place, and its tab follows from it. */
export function follow(place) {
  const p = placeOf(place, helpTab.value);
  if (!p.known) return;
  helpTab.value = p.tab;
  rememberTab(p.tab);
  helpQuery.value = "";
  helpTarget.value = null;
  setTimeout(() => { helpTarget.value = p.target; }, 0);     // set again so a second click on the same link flashes again
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
    if (e.key === "Escape" && helpOpen.value) {
      e.preventDefault();
      if (helpQuery.value) { helpQuery.value = ""; helpTarget.value = null; helpFocusSearch.value++; return; }    // from the box, a result or a tab: clear the search first
      closeHelp(); return;
    }
    if (typing(e.target) || otherLayerOpen()) return;
    if (e.key === "?") { e.preventDefault(); if (helpOpen.value) helpFocusSearch.value++; else openHelp(); }
    else if (e.key === "/" && helpOpen.value && singleKeys.value) { e.preventDefault(); e.stopImmediatePropagation(); helpFocusSearch.value++; }
  }, true);
  // Moving to another page or project closes Help.
  let seen = view.value + "|" + project.value;
  effect(() => {
    const now = view.value + "|" + project.value;
    if (now !== seen) { seen = now; opener = null; helpOpen.value = false; }
  });
}
