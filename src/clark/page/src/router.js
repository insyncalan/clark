// The page's address book (#63): standard browser navigation, so Back and Forward (the trackpad swipe, the mouse buttons,
// the keyboard) step through clark's pages, projects and peeks. Plain JS: no JSX, no library, no store, so the store, the
// tests and the published page's script can all use it.
//
// An address is a hash, never a path or a query: "#work&p=PDF&item=A-12", "#milestones&p=PDF&ms=M-3", "#settings". The local
// server answers only GET / and /api/* (#33), so a path would 404 on reload; the published file has no server at all, and from
// file:// or a sandboxed frame only a hash can be set (a new path throws SecurityError). Every change of page, project or peek
// goes through navigate(), the one place that touches history, and filters, search, sort, scroll, Edit mode and the calendar
// scale never call it, so they add no entry.
//
// One more key, `f`, belongs to the Work items filters (#64a): "#work&p=PDF&f=<text>". The router NEVER parses it. `f` is an
// opaque string, kept exactly as it stands in the address: never decoded, re-encoded or double-encoded, so "%26" and "%3D" in it
// come back as "%26" and "%3D", and the caller (the filters) encodes and decodes its own text. It is trusted only if it is at
// most 600 characters, uses only characters an address carries as they are (letters, digits and - . _ ~ ! $ ' ( ) * + , ; : @ / ?)
// and well-formed percent-escapes (%XX), and decodes without a control character or an unpaired surrogate (so %zz, a lone %,
// %ED%A0%80 and %00 fail). Anything else, and a raw "=" in it, makes `f` '' (dropped, never repaired). A raw "&" ends the value
// as it ends any other: what follows is read as ordinary keys, so `f` can never change view, project, item or ms except as a
// key written in the address would. `f` is written with navigate({...state, f}, {replace: true}): a filter change never pushes an
// entry, so Back never stops on one. navigate() replaces by itself when only `f` differs, even if the caller forgets. A change
// of page or project that also changes `f` pushes one entry, like any other change, and Back and Forward bring `f` back.
export const VIEWS = ["dashboard", "work", "milestones", "usecases", "settings"];
const CODE = /^[A-Z][A-Z0-9]{2,6}$/;                       // a project's code (the store's rule)
const ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;            // a work item's or a milestone's id
const UC_KEY = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;        // a use case's address key: its reference as written ("1.2") or its id; only the Use cases page reads it
const MAX_F = 600;                                         // the longest `f` the router will carry
const F_TEXT = /^(?:[A-Za-z0-9\-._~!$'()*+,;:@/?]|%[0-9A-Fa-f]{2})*$/;   // what an address carries as it is, and %XX
const STUCK_MS = 400;                                      // how long back() waits for the address to move before it says it is stuck
const MARK = 1;                                            // history.state of an entry a click made by opening a peek

/** `f` as given if it is trustworthy, else ''. Never decodes for use: decoding is only a check that nobody could be thrown by it. */
function opaque(v) {
  if (typeof v !== "string" || !v || v.length > MAX_F || !F_TEXT.test(v)) return "";
  try { return /[\u0000-\u001f\u007f-\u009f]/.test(decodeURIComponent(v)) ? "" : v; } catch (e) { return ""; }
}

function clean(state) {
  const s = state && typeof state === "object" ? state : {};
  const text = (v) => (typeof v === "string" ? v : "");
  const view = VIEWS.includes(s.view) ? s.view : "dashboard";
  const project = CODE.test(text(s.project)) ? s.project : "";
  const peekable = view !== "settings";                    // Settings has no peek; one peek at a time, an item before a milestone
  const item = peekable && ID.test(text(s.item)) ? s.item : "";
  const ms = peekable && !item && ID.test(text(s.ms)) ? s.ms : "";
  const uc = view === "usecases" && UC_KEY.test(text(s.uc)) ? s.uc : "";     // "#usecases&p=PDF&uc=1.2": one use case's own page; no other page has it
  return { view, project, item, ms, f: opaque(s.f), uc };
}

/** True for a well-formed project code. */
export function isProject(code) {
  return typeof code === "string" && CODE.test(code);
}

function unescape(v) {
  try { return decodeURIComponent(v); } catch (e) { return ""; }
}

/** A hash (with or without the "#") as {view, project, item, ms, f, uc}. Never throws; whatever it can't trust is left empty. */
export function parse(hash) {
  const parts = (typeof hash === "string" ? hash : "").replace(/^#/, "").split("&");
  const found = {};
  for (const part of parts.slice(1)) {
    const at = part.indexOf("=");
    const key = at < 0 ? part : part.slice(0, at);
    if (key in found || !["p", "item", "ms", "f", "uc"].includes(key)) continue;     // the first of a repeated key wins; others are ignored
    const raw = at < 0 ? "" : part.slice(at + 1);
    found[key] = key === "f" ? raw : unescape(raw);                        // `f` is passed through as it stands, never decoded
  }
  return clean({ view: unescape(parts[0]), project: found.p, item: found.item, ms: found.ms, f: found.f, uc: found.uc });
}

/** {view, project, item, ms, f, uc} as a hash, the one form of each address ("#dashboard" for an empty state). Never throws. */
export function format(state) {
  const s = clean(state);
  return "#" + s.view + (s.project ? "&p=" + s.project : "") + (s.uc ? "&uc=" + encodeURIComponent(s.uc) : "") + (s.item ? "&item=" + encodeURIComponent(s.item) : "") +
    (s.ms ? "&ms=" + encodeURIComponent(s.ms) : "") + (s.f ? "&f=" + s.f : "");
}

try { history.scrollRestoration = "manual"; } catch (e) { /* the page works with the browser's default */ }

let seen = "";                                             // the hash the page last drew, so one move is never handled twice
let moves = 0;                                             // counts every move (navigate, Back, Forward): back()'s stuck check reads it

function here() {
  try { return location.hash; } catch (e) { return ""; }
}

/** The state of the address the page is on now. */
export function current() {
  return parse(here());
}

/** True when this entry was made by a click that opened a peek, so closing the peek can step Back and leave no entry behind. */
export function peekWasPushed() {
  try { return !!history.state && history.state.clarkPeek === MARK; } catch (e) { return false; }
}

/**
 * Move to `state`: a new entry, or with {replace: true} this entry rewritten. Returns true if the address changed. The same
 * address never pushes twice. A peek opened from none is marked on its entry, so closePeek() can call history.back(). A change of
 * only `f` (a filter) is always a replace, whatever the caller asked, so Back never stops on a filter.
 */
export function navigate(state, { replace = false } = {}) {
  const next = clean(state);
  const hash = format(next);
  const now = parse(here());
  if (hash === format(now)) return false;
  if (format({ ...next, f: "" }) === format({ ...now, f: "" })) replace = true;      // only `f` differs
  const opened = !!(next.item || next.ms) && !(current().item || current().ms);
  const mark = (opened && !replace) || (replace && (next.item || next.ms) && peekWasPushed()) ? { clarkPeek: MARK } : null;
  try { history.scrollRestoration = "manual"; } catch (e) { /* as above */ }
  seen = hash;                                             // set first: location.hash = ... can fire popstate inside the call
  moves++;
  try {
    if (replace) history.replaceState(mark, "", hash); else history.pushState(mark, "", hash);
  } catch (e) {
    try { if (replace) location.replace(hash); else location.hash = hash; } catch (e2) { seen = here(); /* no history: the page still works */ }
  }
  return true;
}

/** Step Back one entry (the browser's Back); the handler given to onPop then redraws. If `stuck` is given and nothing has moved a
 *  moment later (there was no earlier entry to go to: back() then does nothing and fires nothing), it is called once. "Nothing has
 *  moved" is no Back, Forward or navigate at all, not only the same address: closing a peek and opening the same item again within
 *  the wait is the same address, and the late fallback must not close the peek just opened (#42). */
export function back(stuck) {
  const from = here(), at = moves;
  try { history.back(); } catch (e) { return false; }
  if (stuck) setTimeout(() => { if (moves === at && here() === from) stuck(); }, STUCK_MS);
  return true;
}

/** Call `handler(state)` when the person moves through history (Back, Forward, a typed hash). Returns a function that stops it. */
export function onPop(handler) {
  const run = () => {
    const now = here();
    if (now === seen) return;                              // popstate and hashchange both fire for one move: draw once
    seen = now;
    moves++;
    try { handler(parse(now)); } catch (e) { /* a faulty handler must not break the next move */ }
  };
  seen = here();
  addEventListener("popstate", run);
  addEventListener("hashchange", run);
  return () => { removeEventListener("popstate", run); removeEventListener("hashchange", run); };
}

/** Opens a new tab now, while the click still counts (a browser blocks a tab opened after a wait), then points it at the address
 *  `getUrl()` gives, a promise of a string (#147). If that gives nothing, or anything but a string, the tab is closed. Resolves to
 *  true when the tab was pointed, false when it was blocked or there was no address. The one place a tab's address is set.
 *  The tab's link back to this page (`opener`) is cut at once, so the page shown there can never reach the editor or its token.
 *  "noopener" is not used for that, as window.open then gives no tab to point. The tab is still a blank page of this origin
 *  here, so the cut is allowed. */
export async function openInNewTab(getUrl) {
  const tab = window.open("", "_blank");
  if (tab) { try { tab.opener = null; } catch (e) { /* nothing to cut */ } }
  let url = null;
  try { url = await getUrl(); } catch (e) { url = null; }
  if (tab && typeof url === "string") { tab.location = url; return true; }
  if (tab) tab.close();
  return false;
}
