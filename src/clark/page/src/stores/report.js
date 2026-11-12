// The page's state: one signals store (as creaite's src/stores/). The view and the open project are the address, so a
// reload keeps them; the project's data comes from GET /api/data with this run's token (#33, #31's data_for).
// A published file (#39) has its data in an inline block, id="clark-data": then the page is a file (fromFile), reads that block
// and nothing else: no fetch, no token, no Settings tab, and "today" is the date it was published (as_at).
import { signal, computed, batch, effect } from "@preact/signals";
import * as route from "../router.js";
import { rowsOf, todayIso, pinToday } from "../workItems.js";
import { decode, encode, fits, hasReviewDates, setPublished, setReviewDays } from "../filters.js";
import { searchIndex } from "../clientView.js";
import { lineApi } from "./lineSlot.js";
import { ucKey } from "../logic/useCasesList.js";
import { useFileDensity } from "./density.js";
import { leaving, saved, beforeReload, trouble } from "./leave.js";
import { editorOn, tabName } from "../gantt/ganttTab.js";

export const VIEWS = route.VIEWS;
export const TITLES = { dashboard: "Dashboard", work: "Work items", milestones: "Milestones", usecases: "Use cases", get gantt() { return tabName(data.value && data.value.project); }, settings: "Settings" };   // "Use cases" in the editor and in a published file alike (#383)
export const SHORT_TITLES = {};   // a tab's name for a narrow window, where it has a shorter one; the page keeps the full name (none has one now)

// The address (router.js) holds the page, the project and the open peek, so a reload or a bookmark opens the same ones and
// Back and Forward step through them (#63). Each change of page, project or peek goes through navigate() there.
const start = route.current();

// The brand block is the server's, for the project in the address (#944, GET /?project=<code>). An address for another project than the
// one this page was served for (typed, bookmarked, or a Back) is loaded again for its own; a published file and a non-served page never are.
// What is being typed is saved first, and the page waits for it (saved, leave.js), so a title not yet left is not lost; a message with Undo
// goes with the person to the new page (the hooks in beforeReload, given by the changes store: edit only).
// The page going away for good (Back or Forward to another page load, which is what leaving a project by Back is: each project is its own
// load, and the browser steps to that load without asking this page): a field still being typed in is left, so its save starts now, and api.js
// sends it so that it outlives the page. The reply is not read by a page that has gone, so no message follows it.
addEventListener("pagehide", () => { if (published()) return; leaving.on = true; leaveField(); });
addEventListener("pageshow", () => { leaving.on = false; });
function reloadFor(s, wait = true) {
  try {
    if (published() || !s.project || !/^https?:$/.test(location.protocol) || s.project === (new URLSearchParams(location.search).get("project") || "")) return false;
    const url = "/?project=" + s.project + route.format(s);
    if (!wait) { location.replace(url); return true; }
    const since = trouble.n;
    leaveField();
    // Only a save that worked lets the page go: a refused or slow one keeps the page, its field and the problem, and the address names the open project again.
    saved(undefined, since).then((ok) => {
      if (!ok) { route.navigate(where(), { replace: true }); return; }
      try { beforeReload.forEach((f) => f()); } catch (e) {}
      location.replace(url);
    }, () => location.replace(url));
    return true;
  } catch (e) { return false; }
}
// The address names its project in the hash, which the server never sees: a page served with a brand block of its own cannot stay for another
// project, so it is replaced at once. A page served on Generic reads the project first (load() below): only a project with a brand of its own
// goes to GET /?project=<code>, and a Generic one is one load, not two (row 107: the first load was the one a slow computer's tests polled).
if (typeof document !== "undefined" && document.getElementById && document.getElementById("brand-local")) reloadFor(start, false);
export const project = signal(start.project);
export const view = signal(start.view);
export const item = signal(start.item);              // the open peek: a work item's id, or "" (the peek itself is #42)
export const ms = signal(start.ms);                  // ... or a milestone's id
export const settingsPage = signal(start.view === "settings" ? start.s || "" : "");   // item 1024: the Settings page shown, an address key from router.SETTINGS_PAGES, or "" for Projects
export const wantName = signal(false);                  // "Add your name in Settings": the name box takes the focus when Settings has drawn (here, not in the profile store, so the published page does not pull in the api)
export const uc = signal(start.uc);                  // the open use case's address key on the Use cases page (its reference as written, else its id), or ""
const filterText = signal(start.f);                  // the Work items filters' text, opaque to the router (#64a): see setFilters()
export const f = computed(() => filterText.value);   // read-only: a component changes it only through setFilters()
export const peek = computed(() => (item.value ? { kind: "item", id: item.value } : ms.value ? { kind: "milestone", id: ms.value } : null));
// Work items' filters (filters.js) live in the address as `f` and nowhere else: the state is read from the text each time it changes,
// so a reload, Back and Forward bring the filters back with the page. The published file keeps this older bar (#69; the filter line is
// for the app only, #153): `openFilter` is which filter's box is open ("" for none).
export const filterState = computed(() => decode(f.value));
export const openFilter = signal("");
export const filterNote = signal("");                // a plain line when a filter could not be added; "" otherwise
export const refusals = signal(0);                   // counts the refusals, so a ticked box that was not kept is drawn unticked again
export const status = signal(project.value ? "loading" : "none");   // none | loading | ready | missing | failed
export const data = signal(null);
effect(() => setReviewDays(data.value && data.value.project ? data.value.project.review_after_days : undefined));   // #171: the words and rules for "not reviewed" follow the open project's own number (a file has none: 14)
export const message = signal("");
export const publication = signal(0);       // a published file: its publication number (#120), else 0; the footer reads it
export const fromFile = signal(false);       // true when the page is a published file (#39): it never edits and never asks a server
export const mode = signal("view");          // view | edit (#65): memory only, never in the database or the address, so a reload is View
export const dropAt = signal(undefined);     // Edit, while a section is dragged: what to draw (logic/placement.js indicator: { line: "before", ids } | { line: "end" } | { outline, side }), undefined for none
export const asAt = signal("");              // view mode: the publish date, YYYY-MM-DD; due dates and Overdue read as at this
export const rebuilt = signal("");           // item 349: the day the Dashboard is shown as at, rebuilt from the change history (YYYY-MM-DD), else "": memory only, never in the address; while set the page is read only
export const SERVED_TABS = VIEWS;   // the served page offers every view; a published file lists its own, from p.tabs
export const tabs = signal(SERVED_TABS);           // the views the tab bar offers; a published file has no Settings, and only the Use Cases it was given
// The tabs the bar offers right now. A published file lists its own (the server decides, #926); the served page adds the Gantt tab only
// when the open project's setting says so, and until a project is read it does not (a reload on #gantt opens it once the setting is known).
export const shownTabs = computed(() => (fromFile.value ? tabs.value : tabs.value.filter((v) => v !== "gantt" || editorOn(data.value && data.value.project))));
// The served page with the setting off (or turned off after) has no Gantt page: the address opens the first tab, as a reload of it does.
effect(() => { if (view.value === "gantt" && !fromFile.value && status.value === "ready" && !shownTabs.value.includes("gantt")) { view.value = SERVED_TABS[0]; route.navigate({ view: SERVED_TABS[0], project: project.value, item: "", ms: "", f: "" }, { replace: true }); } });
export const moves = signal(0);              // counts Back and Forward (and a typed address): a menu that is open closes on each
export const projects = signal([]);                 // [{code, name}] from GET /api/projects
export const projectsState = signal("loading");     // loading | ready | failed

export const rows = computed(() => (data.value ? rowsOf(data.value) : []));
// The published file's search words (#69): memory only, never kept anywhere. The index is read from the file's own rows, by id.
export const query = signal("");
export const found = computed(() => (data.value ? searchIndex(data.value) : {}));
export function setQuery(text) { query.value = String(text == null ? "" : text); }

// The signed-in person's name for the app's filter line: the page has no source for it yet. Read by filterCtx only.
export const me = signal("");
// The project's own lists, from the data the page already holds: workstream names in the project's order, milestones in their own order with the date each is working to.
export const filterCtx = () => {
  const d = data.value;
  return {
    today: fromFile.value && asAt.value ? asAt.value : todayIso(), me: me.value, quietReady: hasReviewDates(rows.value), archivedReady: !fromFile.value,
    workstreams: d ? (d.workstreams || []).map((w) => w.name).filter(Boolean) : [],
    milestones: d ? (d.milestones || []).map((m) => ({ name: m.name, date: m.forecast_date || m.baseline_date || "" })).filter((m) => m.name) : [],
  };
};

export const counts = computed(() => {
  const d = data.value;
  return d ? { work: d.actions.length + d.raid.length + d.decisions.length, milestones: d.milestones.length } : { work: 0, milestones: 0 };
});

let openedF = null;                                  // null: not known (a reload or a restored tab), so closing rewrites the entry

// Each Settings page keeps its own place (item 1024): the scroll is noted as it moves, set aside under the page's key when the page
// is left, and given back when it is shown again by Back, Forward or its menu entry. A page not seen yet starts at the top.
const scrolls = new Map();
let seenY = 0;
export const restoreY = signal(0);                   // where the page now shown should be scrolled to; Settings reads it once it has drawn
const scrollKey = () => project.value + "|" + settingsPage.value;
if (typeof addEventListener === "function") addEventListener("scroll", () => { if (view.value === "settings") seenY = window.scrollY; }, { passive: true });

const where = () => ({ view: view.value, project: project.value, item: item.value, ms: ms.value, f: filterText.value, uc: uc.value, s: settingsPage.value });

// Draw the page from an address: the signals follow it, and a project that changed is read again. A published file has one
// project and only its own tabs: an address that names another project or a tab the file does not have (typed, or a Back to it)
// stays on the file's project and opens its first tab, as a reload of that address does.
let moved = false;                                   // a move inside the page (a click, Back, Forward) has happened since a Settings page last took it
/** True once, after an in-app move: Settings uses it to tell a first draw that is an arrival from a first draw that is a reload. */
export function takeArrival() { const m = moved; moved = false; return m; }
function apply(s, history = false) {
  moved = true;
  if (rebuilt.value && (s.project !== project.value || s.view !== "dashboard")) leaveAsAt(s.project === project.value);   // item 349: another page or project is now, not then
  if (fromFile.value) s = { ...s, project: project.value, view: tabs.value.includes(s.view) ? s.view : (tabs.value[0] || s.view), uc: "" };
  if (s.view !== view.value || s.project !== project.value) { openFilter.value = ""; filterNote.value = ""; }   // a filter change keeps its box open
  const wasSettings = view.value === "settings";
  if (wasSettings) scrolls.set(scrollKey(), seenY);          // item 1024: the page being left keeps its place, taken before anything changes
  batch(() => {                                          // one move: an effect (the client's kept choices) sees the page and its filters together, never a new page with the old page's filters
    view.value = s.view;
    item.value = s.item;
    ms.value = s.ms;
    uc.value = s.uc || "";
    settingsPage.value = s.view === "settings" ? s.s || "" : "";
    filterText.value = s.f;
  });
  restoreY.value = s.view === "settings" && (wasSettings || history) ? scrolls.get(scrollKey()) || 0 : 0;
  seenY = restoreY.value;                            // the place noted is the one the page is about to be at, so an arrival with no scroll event keeps no old page's place
  if (s.project !== project.value) {
    project.value = s.project;
    data.value = null;
    status.value = s.project ? "loading" : "none";
    load();
  } else {
    settle();
  }
}

// Whether the loaded data has a work item (`milestone` false) or a milestone with this id.
function known(d, id, milestone) {
  return !!d && (milestone ? d.milestones.some((m) => m.id === id) : [...d.actions, ...d.raid, ...d.decisions].some((r) => r.id === id));
}

// Move to `s` through the router and draw it. Drawn from `s` itself (made well-formed as the router makes it), not from the
// address: if the router could not set the address at all it has not moved, and the page must still change.
function go(s, options) {
  if (route.navigate(s, options)) apply(route.parse(route.format(s)));
}

// A peek whose item or milestone isn't in the project's data (deleted, mistyped, from an old link) opens the page with no
// peek: the entry is rewritten, not added.
function settle() {
  const d = data.value;
  if (!d || status.value !== "ready" || (!item.value && !ms.value)) return;
  if (item.value ? known(d, item.value, false) : known(d, ms.value, true)) return;
  item.value = "";
  ms.value = "";
  route.navigate(where(), { replace: true });
}

// Back and Forward (the trackpad swipe, the mouse buttons, the keyboard) with something still open on the page. What is being typed
// (a section's title) is kept: the field is left first, so it is saved as a click on a tab saves it, to the project it belongs to,
// before the page moves, and the message says so, with Undo. A menu or a drag closes, and nothing is chosen. The
// peek has an entry of its own (closing it is a Back), so the page redraws after this as it would anyway.
function leaveField() {
  const el = document.activeElement;
  const typing = !!el && el !== document.body && (el.isContentEditable || el.tagName === "TEXTAREA" ||
    (el.tagName === "INPUT" && /^(text|search)$/.test(el.type)));
  if (typing && typeof el.blur === "function") el.blur();
}
function leave() {
  leaveField();
  openFilter.value = "";
  dropAt.value = undefined;
  moves.value++;
}

let backingAt = -Infinity;                               // when a Back from closePeek was started: a second close before it lands must not step Back again; after 1.5 s it counts as lost (row 894; no timer on the open path, see test_peek OpenTime)
const backing = () => performance.now() - backingAt < 1500;
route.onPop((s) => { if (reloadFor(s)) return; backingAt = -Infinity; leave(); apply(s, true); });

/** Go to a page: one new entry; an open peek closes, and so do the filters (they belong to one page). */
export function show(next) {
  go({ view: next, project: project.value, item: "", ms: "", f: "" });
}

/** Open a Settings page (item 1024): one new entry; the same page again adds none. "" is Projects, the page plain Settings opens. */
export function openSettings(page = "") {
  go({ view: "settings", project: project.value, item: "", ms: "", f: "", s: page });
}

/** A Settings page the window cannot show (its project is not open, its tool is not here) is rewritten as Projects, never added. */
export function settingsFallback() {
  if (!settingsPage.value) return;
  settingsPage.value = "";
  route.navigate(where(), { replace: true });
}

/** Open Work items with a filter state already set (an At a glance tile, #79): one new entry, as any change of page is. */
export function openWork(want) {
  // The app's filter line (installed at start-up, never in a published file) leaves out a word it cannot answer yet and keeps the line.
  const L = fromFile.value ? null : lineApi.current;
  const state = L ? L.usable(want) : want;
  if (L && project.value && fits(state)) L.remember(project.value, state);
  go({ view: "work", project: project.value, item: "", ms: "", f: fits(state) ? encode(state) : "" });
}

/** Open one use case's own page (the Use cases page, Edit's): one new entry. `id` is the use case's database id; the address carries its reference ("1.2") when that is a clean, single key, else its id. */
export function openUseCase(id) {
  const d = data.value, u = d && (d.use_cases || []).find((x) => x.id === id);
  if (!u) return;
  go({ view: "usecases", project: project.value, item: "", ms: "", f: "", uc: ucKey(d, u) });
}

/** The use case page's way back: the list, one new entry (so Back returns to the use case). */
// A use case address that names nothing (another project, a mistyped link; an archived use case is read first, by the Use cases page)
// opens the list: the entry is rewritten, not added.
export function leaveUseCase() {
  if (!uc.value) return;
  uc.value = "";
  route.navigate(where(), { replace: true });
}

export function openUseCases() {
  go({ view: "usecases", project: project.value, item: "", ms: "", f: "", uc: "" });
}

/** Open a work item's or a milestone's peek (`kind` "milestone" or "item"; left out, the project's data says which): one new entry; with a peek already open, this entry is rewritten (Previous, Next, another row). An id the loaded data doesn't have does nothing. */
export function openPeek(id, kind) {
  const d = data.value;
  if (!peek.value) openedF = filterText.value;           // the filters as they were when the peek opened: closing steps Back only if they still are
  const milestone = kind ? kind === "milestone" : known(d, id, true);
  if (d && !known(d, id, milestone)) return;               // with no data loaded there is nothing to check it against: open it
  go({ ...where(), item: milestone ? "" : id, ms: milestone ? id : "" }, { replace: !!peek.value });
}

/** True while a Back started by closePeek has not landed: the peek is as good as closed (row 891). */
export const peekClosing = () => backing();

/** Close the peek: Back if a click opened it (so no entry stays behind), else this entry is rewritten without it. A Back that
 *  goes nowhere (a restored tab whose stack is gone) falls back to the rewrite. */
export function closePeek() {
  if (!peek.value || backing()) return;
  const rewrite = () => { backingAt = -Infinity; go({ ...where(), item: "", ms: "" }, { replace: true }); };
  // Back would also take away a filter changed while the peek was open (that change rewrote this entry), so then the entry is rewritten.
  if (route.peekWasPushed() && openedF === filterText.value && route.back(rewrite)) { backingAt = performance.now(); return; }       // onPop redraws
  rewrite();
}

/** Switch project: one new entry (and any peek and the filters close), so Back returns to the earlier one. */
export function setProject(code) {
  if (!route.isProject(code)) return;
  loadProject({ view: view.value, project: code, item: "", ms: "", f: "", s: settingsPage.value });      // the Settings page goes with the person; a page the other project cannot show falls back to Projects (settingsFallback)
}

// A different project is a fresh page load, GET /?project=<code> (#944): the server sends that project's one brand block with the policy's
// hashes of exactly those bytes. The page is asked for first: if it cannot be had, this page stays and moves in place as before (as it does
// for the same project, or an address that cannot be set).
function loadProject(s) {
  if (s.project === project.value || typeof fetch !== "function") { go(s); return; }
  const url = "/?project=" + s.project + route.format(s);
  const since = trouble.n;
  leaveField();                                            // what is being typed is saved first, in its own project, and waited for
  saved(undefined, since).then((ok) => (ok ? fetch(url, { cache: "no-store" }) : null)).then((r) => {
    if (!r) return;                                        // the save failed or ran past the wait: this page stays, as it is
    if (!r.ok) { go(s); return; }
    try { beforeReload.forEach((f) => f()); } catch (e) {}
    location.assign(url);
  }, () => go(s));
}

/** A filter change (#64a): `text` goes in the address as `f`, exactly as given (the router does not read, decode or encode it; the
 *  caller encodes it, and an untrustworthy text becomes ''). It rewrites the entry, so Back never stops on a filter. */
export function setFilters(text) {
  go({ ...where(), f: text }, { replace: true });
}

/** A filter change from the published file's bar (#69): the state is encoded (filters.js) into `f`. If it would not fit in the
 *  address, nothing changes and a plain line says why. */
export function setFilterState(next) {
  if (!fits(next)) {
    refusals.value++;
    filterNote.value = "That filter would not fit in the page's address, so it was not added. Remove another filter first.";
    return;
  }
  filterNote.value = "";
  setFilters(encode(next));
}

// Leave the open project (its data was removed, as the demo's is): the Dashboard with no project, one new entry; the Gate then says No project open.
export function leaveProject() {
  go({ view: "dashboard", project: "", item: "", ms: "", f: "" });
}

// Open a project chosen from the list: one new entry, so the address takes its code (a reload keeps it) and its data is read.
export function openProject(code) {
  setProject(code);
}

// Open a project on a given page (Settings › Projects: Open): one new entry.
export function openProjectAt(code, next) {
  if (!route.isProject(code)) return;
  loadProject({ view: next, project: code, item: "", ms: "", f: "" });
}

// The published file's data block: null when the page is the editor's, "bad" when the block is there but is not ours.
function published() {
  const el = document.getElementById("clark-data");
  if (!el) return document.documentElement.dataset.mode === "view" ? "bad" : null;
  try {
    const p = JSON.parse(el.textContent);
    return p && p.v === 1 && p.data && p.data.project && Array.isArray(p.tabs) ? p : "bad";
  } catch (e) { return "bad"; }
}

/** True when the page is a published file: it has its data in it and never waits for a server, so it never shows a loading placeholder. */
export function isFile() {
  return published() !== null;
}

function openPublished(p) {
  fromFile.value = true;
  setPublished(true);                                     // the client's seven filters, no Client filter, Earlier for a finished item
  mode.value = "view";
  if (p === "bad") { tabs.value = []; status.value = "failed"; message.value = "This report's data could not be read."; return; }
  tabs.value = VIEWS.filter((v) => p.tabs.includes(v));
  if (!tabs.value.includes(view.value)) view.value = tabs.value[0];
  project.value = p.data.project.code;
  asAt.value = p.as_at || "";
  publication.value = p.publication && Number.isInteger(p.publication.n) && p.publication.n >= 1 ? p.publication.n : 0;
  useFileDensity(p.style);                                // the look it was published with (item 45); a file written before that has the default
  data.value = { ...p.data, report_sections: Array.isArray(p.sections) ? p.sections : [] };     // the file holds only the sections that show
  status.value = "ready";
  settle();
}

export function token() {
  try { return JSON.parse(document.getElementById("clark-boot").textContent).token; } catch (e) { return ""; }
}

let reading = 0;                                       // the newest read wins when the project changed meanwhile

// What the page says when clark could not give the data. The page never shows the server's own text, because it might be a
// program's error name or a technical phrase: it looks the server's message up here by the HTTP status, and a message it does not
// know (or none at all) gets the plain fallback for that status. Every line says what to do next. A status of 0 is "no answer".
const READ_FAILED = "This project could not be read. Reload the page. If it happens again, restart clark.";
const STALE = "This page is out of date because clark was restarted after you opened it. Reload the page and try again.";
const BAD_CODE = "Use a project code of 3 to 7 capital letters or digits.";
const NO_PROJECT = "There is no project with that code. Check the code in the address, or choose a project from the list.";
const NOT_ACCEPTED = "That request was not accepted. Reload the page.";
const ALLOWED = {
  400: { fallback: "That request could not be read. Reload the page.",
         known: { [BAD_CODE]: BAD_CODE } },
  403: { fallback: NOT_ACCEPTED,
         known: { "Not allowed": NOT_ACCEPTED, [NOT_ACCEPTED]: NOT_ACCEPTED, [STALE]: STALE,
                  "That was not accepted. Reload the page and try again.": NOT_ACCEPTED,       // server.MESSAGES not_allowed
                  "This page is out of date because clark was restarted. Reload the page and try again.": STALE,       // server.STALE_PAGE
                  "The server was restarted since this page was opened. Reload the page (Cmd+R) and try again.": STALE } },
  404: { fallback: "Check the project's code.",
         known: { [NO_PROJECT]: NO_PROJECT,
                  "There is no project with that code.": NO_PROJECT } },
  500: { fallback: "A problem came up reading this project. Reload the page. If it happens again, restart clark.", known: {} },
  0: { fallback: "Nothing is running behind this page. After a while with nothing open, clark stops by itself. Start it again from clark.command.", known: {} },
};
export function plain(code, body) {
  const row = ALLOWED[code];
  if (!row) return READ_FAILED;
  const said = body && typeof body.message === "string" ? body.message : "";
  if (code === 403 && body && body.stale === true) return STALE;
  return Object.prototype.hasOwnProperty.call(row.known, said) ? row.known[said] : row.fallback;
}

// What the page says when a change or an undo (api.js) failed, by the same rule as plain(): the status picks the words, and a
// message from the server is used only to pick one of these, never shown. Each says that nothing was changed (or what is
// still true) and what to do next.
const CHANGE_FAILED = "That change could not be made, and nothing was changed. Reload the page and try again.";
const CHANGE_KNOWN = {
  "Your page is out of date. Reload it, then try again.": "The report has changed since you opened it, and nothing was changed. Reload the page and try again.",
  "That section isn't in this project.": "That section is no longer in this report, and nothing was changed. Reload the page.",
  "That step can't be undone from here.": "That change can't be undone any more. Reload the page to see how the report is now.",
  "That step has been undone already.": "That change has been undone already. Reload the page to see how the report is now.",
  // The eye of the Work items table (#456) cannot show a Sensitive item: clark's refusal of it, in the page's words.
  "A Sensitive item is never published, so it can't be added to the report.": "A Sensitive item is never shown to the client, and nothing was changed. Take the Sensitive label off first.",
  // #80: a work item change clark would not make (clark/changes.py's words; the page says its own)
  "That item isn't in this project.": "That item is no longer in this project, and nothing was changed. Reload the page.",
  "The week ending date must be a real date. The old date was kept. Pick a date and try again.": "That isn't a real day, so the old week ending date was kept. Type another date as DD-MM-YYYY.",
  // changes.NOT_A_DATE, and DOC_NOT_A_DATE for a document's typed date
  "That isn't a date. Pick a day from the calendar.": "That date isn't a real day, and nothing was changed. Pick another date.",
  "That isn't a date. Write it as DD-MM-YYYY (day, month, year), or leave it empty.": "That date isn't right. Nothing was changed. Type it as DD-MM-YYYY, or leave it empty.",
  "That status isn't available for this item.": "That status isn't one this item can have, and nothing was changed.",
  "A decision that is made needs the date it was made.": "A made decision needs the date it was made, and nothing was changed. Pick a date.",
  "A decision that isn't made yet has no date.": "A decision that isn't made yet has no decision date, and nothing was changed.",
  // = changes.MADE_STAYS exactly (capital P; a test keeps them equal)
  "A decision that has been made can't go back to Pending. Record a new decision that replaces it.":
    "A decision that has been made can't go back to Pending, and nothing was changed. Record a new decision that replaces it.",
  "A decision that has been made can't be put back. Record a new decision that replaces it.":
    "That decision has been made, so it was left as it is. Record a new decision that replaces it.",
  "Use plain text, with no line breaks or hidden characters.": "A name can only be plain text, with no line breaks or hidden characters. Nothing was changed.",
  "That value isn't one clark can use.": "That value can't be used, and nothing was changed. Try another.",
  "A latest update can be at most 1000 characters. Shorten it and try again.": "A latest update can be 1000 characters at most. Nothing was changed. Shorten it and try again.",
  "That has a hidden character in it. Take it out and try again.": "That update has a hidden character in it, often from copying and pasting. Nothing was changed. Type it again, then press Enter.",
  // #121: a 'Needs from you' list clark would not save (clark/section_bodies.py's words; the page checks first and says the same)
  "Needs from you can have at most 100 rows.": "A list can have 100 rows at most, and nothing was changed. Remove one to add another.",
  "Say what is needed.": "Say what is needed. Nothing was changed.",
  "What is needed can be 300 characters at most.": "What is needed can be 300 characters at most. Nothing was changed.",
  "From can be 100 characters at most.": "From can be 100 characters at most. Nothing was changed.",
  "By must be a real day between 2000 and 2100, or empty.": "By must be a real day between 2000 and 2100, or empty. Nothing was changed.",
  // the change route's own limit (server.py MESSAGES change_too_large) is the key at the end of this table
  // row 1005: the Text and picture section's text over its limit (section_kinds/textimage.py's words, said as the server says them)
  "The text can be 40,000 characters at most. Shorten it and try again.": "The text can be 40,000 characters at most. Shorten it and try again.",
  // #189: a 'Progress tracker' clark would not save (clark/section_bodies.py's words; the page checks first and says the same)
  "The progress tracker holds an overall figure, the columns shown, and groups of lines.": "That tracker can't be saved, and nothing was changed. Reload the page and try again.",
  "The overall figures are two numbers from 0 to 100, a health word, and a short note, or empty.": "The overall figures could not be saved. Nothing was changed. Use numbers from 0 to 100, then try again.",
  "A line about it can be 100 characters at most. Shorten it and try again.": "That line is too long (100 characters at most). Nothing was changed. Shorten it and try again.",
  "The progress tracker's size is Large, Medium, Small or Compact.": "That size could not be saved. Nothing was changed. Choose Large, Medium, Small or Compact, then try again.",
  "Each extra column is either shown or not.": "That column setting could not be saved. Nothing was changed. Reload the page and try again.",
  "A group holds a name and its lines.": "That group can't be saved, and nothing was changed. Reload the page and try again.",
  "A tracker can have at most 10 groups.": "A tracker can have 10 groups at most, and nothing was changed. Remove one to add another.",
  "Give each group a name.": "Give each group a name. Nothing was changed.",
  "A group name can be 80 characters at most. Shorten it and try again.": "That group name is too long (80 characters at most). Nothing was changed. Shorten it and try again.",
  "A group can have at most 47 lines and a tracker 47 in all.": "A tracker can have 47 lines in all, and nothing was changed. Remove one to add another.",
  "A line holds a number, a description, dates, a status, a weight, what was planned and what was achieved.": "That line can't be saved, and nothing was changed. Reload the page and try again.",
  "Describe each line.": "Describe each line. Nothing was changed.",
  "A line description can be 100 characters at most. Shorten it and try again.": "That description is too long (100 characters at most). Nothing was changed. Shorten it and try again.",
  "A line number can be 10 characters at most. Shorten it and try again.": "That number is too long (10 characters at most). Nothing was changed. Shorten it and try again.",
  "A date must be a real day between 2000 and 2100, or empty.": "That date isn't right. Nothing was changed. Type it as DD-MM-YYYY, or leave it empty.",
  "A line can't end before it starts.": "The end date is before the start date, and nothing was changed. Change one of the dates.",
  "Choose Planned, In progress, Completed or Late.": "Choose Planned, In progress, Completed or Late. Nothing was changed.",
  "Type a percentage from 0 to 100, with one decimal at most.": "Type a percentage from 0 to 100, with one decimal at most. Nothing was changed.",
  "Weight, Planned or Achieved adds up to more than 100% across all the lines. Lower one of the figures and try again.": "Weight, Planned or Achieved adds up to more than 100% across all the lines. Nothing was changed. Lower one of the figures and try again.",
  "A count must be a whole number from 0 to 99999, or empty.": "A count must be a whole number from 0 to 99999, or empty. Nothing was changed.",
  "That content can't hold control or invisible characters.": "Hidden text can't be saved. Use plain letters and numbers. Nothing was changed.",
  "That content is too long to save.": "That is too long to save, and nothing was changed. Make the text shorter, or take some of the list out.",
  // #220: a text section's body clark would not save (clark/changes.py's words)
  "That text is too long to save. Shorten it and try again.": "That text is too long to save, and nothing was changed. Shorten it and try again.",
  // the whole change was over the size clark takes (server.py's words; any kind of section can be that big)
  "That is too big to save. Make the text shorter, or take some of the list out, then try again.": "That is too big to save, and nothing was changed. Make the text shorter, or take some of the list out.",
};
export const sayings = [];      // Edit adds the words of a refusal that is already plain (edit/ganttWords.js): each is (text) => the text, or ""
export function plainChange(code, body) {
  const said = body && typeof body.message === "string" ? body.message : "";
  const known = Object.prototype.hasOwnProperty.call(CHANGE_KNOWN, said) ? CHANGE_KNOWN[said] : "";
  if (code === 400 || code === 409) return known || sayings.map((f) => f(said)).find(Boolean) || CHANGE_FAILED;     // row 926: a Gantt refusal is already plain words
  if (code === 403 || code === 0) return plain(code, body);
  if (code === 404) return "This project could not be found, and nothing was changed. Check the code in the address, then reload the page.";
  if (code === 500) return "A problem came up saving that, and nothing was changed. Try again. If it happens again, restart clark.";
  if (code === 503) return "That could not be saved just now, and nothing was changed. Wait a moment and try again. If it keeps happening, restart clark.";
  return CHANGE_FAILED;
}

const LIST_FAILED = "The list of projects could not be read. Reload the page. If it happens again, restart clark.";
// The list's own words, picked by status like plain(): a refusal or no answer says what plain() says; anything else is LIST_FAILED.
function plainList(code, body) {
  return code === 0 || code === 400 || code === 403 ? plain(code, body) : LIST_FAILED;
}

// The projects to choose from (GET /api/projects) when the address names none. "There are no projects yet" is said only when the
// list was read and is empty: a list that could not be read says so, with Try again.
export async function loadProjects() {
  projectsState.value = "loading";
  try {
    const r = await fetch("/api/projects", { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    const body = await r.json().catch(() => ({}));
    if (!r.ok || !body.ok || !Array.isArray(body.projects)) {
      projects.value = []; projectsState.value = "failed"; message.value = plainList(r.status, body);
      return;
    }
    projects.value = body.projects;
    projectsState.value = "ready";
  } catch (e) {
    projects.value = []; projectsState.value = "failed"; message.value = plain(0);
  }
}

// The address of a Generic project's page, as the reload would have left it (/?project=<code> and the same hash), set in place: no navigation.
function nameProject(s) {
  try {
    if (published() || !s.project || !/^https?:$/.test(location.protocol) || s.project === (new URLSearchParams(location.search).get("project") || "")) return;
    route.replaceAddress("/?project=" + s.project + route.format(s));
  } catch (e) {}
}
let firstLoad = true;          // only the page's first read may go to another page for its brand: a switch that could not get the page stays put (loadProject)
export async function load() {
  const first = firstLoad; firstLoad = false;
  const p = published();
  if (p) return openPublished(p);          // a published file never asks a server for anything
  const code = project.value;
  const mine = ++reading;
  if (!code) { status.value = "none"; return loadProjects(); }
  status.value = "loading";
  try {
    const r = await fetch(`/api/data?project=${encodeURIComponent(code)}`, { headers: { "X-Clark-Token": token() } });
    const body = await r.json().catch(() => ({}));
    if (mine !== reading) return;
    if (r.status === 404) { status.value = "missing"; message.value = plain(404, body); return; }
    if (!r.ok || !body.ok) { status.value = "failed"; message.value = plain(r.status, body); return; }
    if (first) {
      if (!(body.data && body.data.project && body.data.project.brand === "generic") && reloadFor(where(), false)) return;   // a brand of its own (or none known): the page for it, before anything is drawn
      nameProject(where());          // a Generic project keeps this page; its address names it as the reload would have (no second load)
    }
    data.value = body.data;
    status.value = "ready";
    settle();
  } catch (e) {
    if (mine !== reading) return;
    status.value = "failed";
    message.value = plain(0);
  }
}

/** Read the open project's data again without redrawing the page as loading (#80: after an undo of a work item change, whose
 *  reply carries no items). Resolves to true when the data was read and drawn; false leaves the page as it is. */
export async function reread(code) {
  if (fromFile.value || rebuilt.value || !code || code !== project.value) return false;
  try {
    const r = await fetch(`/api/data?project=${encodeURIComponent(code)}`, { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    const body = await r.json().catch(() => ({}));
    if (!r.ok || !body.ok || !body.data || code !== project.value) return false;
    data.value = body.data;
    settle();
    return true;
  } catch (e) {
    return false;
  }
}

// item 349: the Dashboard as at `day`, from GET /api/as-at's data (edit/asAtApi.js). The page is View, read only, behind the banner
// (components/AsAtBanner.jsx), and "today" is that day. Nothing here is saved; Back to now (or any other page or project) reads now again.
export function showAsAt(day, d) {
  if (fromFile.value || !d || !d.project || d.project.code !== project.value) return false;
  ++reading;                                          // a read of now still on its way is not drawn over this one
  batch(() => {
    pinToday(day);
    mode.value = "view";
    data.value = d;
    rebuilt.value = day;
    status.value = "ready";
  });
  if (view.value !== "dashboard" || item.value || ms.value) show("dashboard");
  return true;
}

function leaveAsAt(reload) {
  pinToday("");
  rebuilt.value = "";
  if (reload) load();
}

/** Back to now: this week's Dashboard, read from clark again. */
export function backToNow() {
  if (rebuilt.value) leaveAsAt(true);
}

// "Try again": a page that clark would not accept has a token from an earlier run, so only a reload of the page helps.
export function tryAgain() {
  if (message.value === STALE || message.value === NOT_ACCEPTED) location.reload(); else load();
}
