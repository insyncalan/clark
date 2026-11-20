// The command palette's search and actions (#198), Edit parts only: a published file has no palette. Plain JS that draws nothing and touches no DOM itself: it takes
// what the page already holds (the open project's data, the project list, the tabs) and gives back the results in order:
// with words typed: commands, pages, work items (an ID first), use cases and milestones, then actions, projects (Classic: projects come right after the pages, before the work items); with no words: pages, actions, projects, commands (row 900). Words match the text, the ID and the owner's name. Nothing here asks a server, and a
// command that changes anything calls the very function the existing button or menu entry calls (profile menu, Publish).
import { signal } from "@preact/signals";
import { data, shownTabs, TITLES, project, projects, view, rows, show, setProject, openPeek, openUseCase, fromFile, status } from "../stores/report.js";
import { appearance, setAppearance, MODES } from "../stores/appearance.js";
import { KIND_WORDS } from "../workItems.js";
import { liveOf, nameOf, refOf } from "../logic/useCasesList.js";
import { addItem, ADDABLE } from "./addItem.js";
import { addMilestone } from "./MsAdd.jsx";
import { ADD_MILESTONE } from "./movementWords.js";
import { openPublish } from "./Publish.jsx";
import { preview, exportExcel } from "./ProfileMenu.jsx";
import { openHelp, closeHelp, helpOpen } from "../help/helpStore.js";
import { classicTheme } from "../components/Contents.jsx";
import { openPanel, handOver } from "./askPanelState.js";
import { PANEL_TITLE } from "./askWords.js";

export const paletteOpen = signal(false);
export const MOST_ITEMS = 8;          // work items shown at most, all kinds together (cut after the ID ranking), so a short word does not fill the box
const LOOK_WORDS = { light: "Light", dark: "Dark", system: "System" };       // the same words as Settings › Personal and the profile menu
const NEED_PROJECT = "Open a project first.";

const lower = (s) => String(s == null ? "" : s).toLowerCase();
const words = (q) => lower(q).split(/\s+/).filter(Boolean);
const plainText = (h) => String(h || "").replace(/<[^>]*>/g, " ");
const hits = (text, ws) => { const t = lower(text); return ws.every((w) => t.includes(w)); };

function commands() {
  const ready = !!data.value && status.value === "ready" && !fromFile.value;
  const why = ready ? "" : NEED_PROJECT;
  return [
    { key: "publish", label: "Publish…", more: "report send client", why, run: () => openPublish() },
    { key: "preview", label: "Preview the page in a new tab", more: "published page", why, run: () => preview() },
    { key: "export", label: "Export to Excel", more: "workbook download xlsx", why, run: () => exportExcel() },
    { key: "settings", label: "Settings", more: "options folder client", why: shownTabs.value.includes("settings") ? "" : "Settings is not available on this page.", run: () => show("settings") },
    { key: "ask", label: PANEL_TITLE, more: "question chat", why: "", run: () => openPanel() },          // the same panel "/" and the ask button open (#47a)
    { key: "help", label: "Help", more: "keys shortcuts how", why: "", run: () => openHelp() },
    ...MODES.map((m) => ({ key: "look-" + m, label: "Appearance: " + LOOK_WORDS[m], more: "theme look colour", why: "", now: appearance.value === m, run: () => setAppearance(m) })),
  ].map((c) => ({ id: "cmd-" + c.key, kind: "Command", label: c.label, more: c.more, disabled: c.why, now: !!c.now, run: c.run }));
}

function pages() {
  return shownTabs.value.filter((v) => v !== "settings" && v !== "published" && TITLES[v]).map((v) => ({ id: "page-" + v, kind: "Page", label: TITLES[v], more: "", disabled: "", current: view.value === v, run: () => show(v) }));
}

// The create entries, each calling the very function the existing Add button calls: the Add menu on Work items (addItem) and the Milestones page's add. The words are the Add buttons' own (filters.js KIND_ADD, ADD_MILESTONE).
function actions() {
  const ready = !!data.value && status.value === "ready" && !fromFile.value;
  const why = ready ? "" : NEED_PROJECT;
  return [
    ...ADDABLE.map((k) => ({ key: k, label: "Add " + k, more: KIND_WORDS[k], run: () => { if (view.value === "settings") show("work"); addItem(k); } })),
    { key: "milestone", label: ADD_MILESTONE, more: "", run: () => { if (view.value === "settings") show("milestones"); addMilestone(); } },
  ].map((a) => ({ id: "act-" + a.key, kind: "Action", label: a.label, more: a.more, disabled: why, run: a.run }));
}

/** Work items, milestones and use cases that match the typed words: an ID first, then words in the text or the owner's name. */
function dataResults(query, ws) {
  const out = [];
  if (ws.length && data.value) {
    const q = lower(query).trim();
    const items = rows.value.filter((r) => hits(r.id + " " + (r.title || "") + " " + (r.owner || ""), ws));
    const byId = (r) => (lower(r.id) === q ? 0 : lower(r.id).startsWith(q) ? 1 : lower(r.id).includes(q) ? 2 : 3);
    items.sort((a, b) => byId(a) - byId(b));          // stable: an ID match first, the rest keep the page's order
    for (const r of items.slice(0, MOST_ITEMS)) {
      out.push({ id: "item-" + r.id, kind: KIND_WORDS[r.kind] || "Work item", label: r.title || r.id, more: r.id, disabled: "", run: () => { if (view.value === "settings") show("work"); openPeek(r.id, "item"); } });
    }
    let shown = 0;          // milestones are capped like the work items
    let ucs = 0;
    for (const u of liveOf(data.value)) {
      if (ucs < MOST_ITEMS && hits([u.id, u.ref, nameOf(u), u.headline, plainText(u.standing)].join(" "), ws) && ++ucs) out.push({ id: "uc-" + u.id, kind: "Use case", label: nameOf(u) || refOf(u) || u.id, more: refOf(u), disabled: "", run: () => { openUseCase(u.id); } });
    }
    for (const m of data.value.milestones || []) {
      if (shown < MOST_ITEMS && hits(m.name + " " + m.id + " " + (m.owner || "") + " milestone", ws) && ++shown) out.push({ id: "ms-" + m.id, kind: "Milestone", label: m.name || m.id, more: m.id, disabled: "", run: () => { if (view.value === "settings") show("milestones"); openPeek(m.id, "milestone"); } });
    }
  }
  return out;
}

const QUESTION_WORDS = /^(what|who|whom|whose|when|where|why|how|which|is|are|was|were|can|could|do|does|did|should|will|would|has|have)\s/i;
const CLASSIC_WORDS = /^(summar\w*|check|draft)\s/i;          // row 1350, Classic only: the prototype also lists summar (a stem), check and draft; Cards keeps its list
const ASK_SHOWN = 60;          // the typed words are cut here in the row's label; the whole text is handed over
/** The word for the send key in the row's hint: "Cmd+Enter" on a Mac, "Ctrl+Enter" elsewhere. `nav` is the browser's navigator (a plain object in tests). */
export function sendKey(nav) {
  const n = nav === undefined ? (typeof navigator === "undefined" ? null : navigator) : nav;
  const where = String((n && ((n.userAgentData && n.userAgentData.platform) || n.platform)) || "");
  return /^(mac|iphone|ipad|ipod)/i.test(where) ? "Cmd+Enter" : "Ctrl+Enter";
}

/** S11: the "Ask ... in ask clark" row for the typed words (none when nothing is typed). Classic only: the row carries the send-key hint (Cards: none, as before row 1350). Enter or a click opens the panel with the words in its box; Ctrl or Cmd + Enter sends them (handOver). */
export function askRow(query) {
  const q = String(query == null ? "" : query).trim();
  if (!q) return null;
  const shown = q.length > ASK_SHOWN ? q.slice(0, ASK_SHOWN - 1).trimEnd() + "…" : q;
  return { id: "ask-row", kind: PANEL_TITLE, label: `Ask “${shown}” in ${PANEL_TITLE}`, more: classicTheme() ? sendKey() : "", disabled: "", question: q, first: /\?$/.test(q) || QUESTION_WORDS.test(q) || (classicTheme() && CLASSIC_WORDS.test(q)), run: () => handOver(q, false) };
}

/** The results for `query`, in the order they are shown: pages, actions, projects, commands, then (when words are typed) the data right after the pages. */
export function search(query) {
  const ws = words(query), all = (t, extra) => !ws.length || hits(t + " " + (extra || ""), ws);
  const out = [], classic = classicTheme();
  if (ws.length && classic) for (const c of commands()) if (all(c.label + " command", c.more)) out.push(c);          // row 1350 (Classic only): with words typed, commands come before the pages
  for (const p of pages()) if (all(p.label + " page")) out.push(p);
  const projectRows = () => {
    for (const p of projects.value || []) {
      if (!all(p.name + " " + p.code + " project")) continue;
      const here = p.code === project.value;
      out.push({ id: "project-" + p.code, kind: "Project", label: p.name || p.code, more: p.code, disabled: "", current: here, run: () => { if (!here) setProject(p.code); } });
    }
  };
  if (ws.length && classicTheme()) projectRows();          // row 1350 (Classic only): with words typed, projects come right after the pages, before the data
  out.push(...dataResults(query, ws));          // row 901: with words typed, the data comes right after the pages (after the projects in Classic)
  for (const a of actions()) if (all(a.label + " action", a.more)) out.push(a);
  if (!ws.length || !classicTheme()) projectRows();          // nothing typed, or Cards: projects after the actions, as before
  if (!ws.length || !classic) for (const c of commands()) if (all(c.label + " command", c.more)) out.push(c);          // nothing typed, or Cards: commands last, as before row 1350
  const ask = askRow(query);
  if (ask) { if (ask.first) out.unshift(ask); else out.push(ask); }          // a question first, anything else after the search
  return out;
}

/** The next result Up or Down reaches from `at` (an index, or -1 for none), wrapping and skipping any that cannot run now. -1 if none can. */
export function step(results, at, dir) {
  const n = results.length;
  for (let k = 1; k <= n; k++) {
    const i = ((at < 0 ? (dir > 0 ? -1 : 0) : at) + dir * k + n * (k + 1)) % n;
    if (!results[i].disabled) return i;
  }
  return -1;
}

/** Run a result: Help closes first if it is open (the palette sits over it), then the result's own action. Disabled ones do nothing. */
export function runResult(r) {
  if (!r || r.disabled) return false;
  if (helpOpen.value && r.id !== "cmd-help") closeHelp();
  r.run();
  return true;
}
