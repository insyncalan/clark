// The command palette's search and actions (#198), Edit parts only: a published file has no palette. Plain JS that draws nothing and touches no DOM itself: it takes
// what the page already holds (the open project's data, the project list, the tabs) and gives back the results in order:
// pages, then (when words are typed) work items (an ID first), use cases and milestones, then actions, projects, commands; with no words: pages, actions, projects, commands (row 900). Words match the text, the ID and the owner's name. Nothing here asks a server, and a
// command that changes anything calls the very function the existing button or menu entry calls (profile menu, Publish).
import { signal } from "@preact/signals";
import { data, tabs, TITLES, project, projects, view, rows, show, setProject, openPeek, openUseCase, fromFile, status } from "../stores/report.js";
import { appearance, setAppearance, MODES } from "../stores/appearance.js";
import { KIND_WORDS } from "../workItems.js";
import { liveOf, nameOf, refOf } from "../logic/useCasesList.js";
import { addItem, ADDABLE } from "./addItem.js";
import { addMilestone } from "./MsAdd.jsx";
import { ADD_MILESTONE } from "./movementWords.js";
import { openPublish } from "./Publish.jsx";
import { preview, exportExcel } from "./ProfileMenu.jsx";
import { openHelp, closeHelp, helpOpen } from "../help/helpStore.js";
import { openPanel } from "./askPanelState.js";
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
    { key: "settings", label: "Settings", more: "options folder client", why: tabs.value.includes("settings") ? "" : "Settings is not available on this page.", run: () => show("settings") },
    { key: "ask", label: PANEL_TITLE, more: "question chat", why: "", run: () => openPanel() },          // the same panel "/" and the ask button open (#47a)
    { key: "help", label: "Help", more: "keys shortcuts how", why: "", run: () => openHelp() },
    ...MODES.map((m) => ({ key: "look-" + m, label: "Appearance: " + LOOK_WORDS[m], more: "theme look colour", why: "", now: appearance.value === m, run: () => setAppearance(m) })),
  ].map((c) => ({ id: "cmd-" + c.key, kind: "Command", label: c.label, more: c.more, disabled: c.why, now: !!c.now, run: c.run }));
}

function pages() {
  return tabs.value.filter((v) => v !== "settings" && TITLES[v]).map((v) => ({ id: "page-" + v, kind: "Page", label: TITLES[v], more: "", disabled: "", current: view.value === v, run: () => show(v) }));
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
    const items = rows.value.filter((r) => hits(r.id + " " + r.title + " " + r.owner, ws));
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

/** The results for `query`, in the order they are shown: pages, actions, projects, commands, then (when words are typed) the data right after the pages. */
export function search(query) {
  const ws = words(query), all = (t, extra) => !ws.length || hits(t + " " + (extra || ""), ws);
  const out = [];
  for (const p of pages()) if (all(p.label + " page")) out.push(p);
  out.push(...dataResults(query, ws));          // row 901: with words typed, the data comes right after the pages
  for (const a of actions()) if (all(a.label + " action", a.more)) out.push(a);
  for (const p of projects.value || []) {
    if (!all(p.name + " " + p.code + " project")) continue;
    const here = p.code === project.value;
    out.push({ id: "project-" + p.code, kind: "Project", label: p.name || p.code, more: p.code, disabled: "", current: here, run: () => { if (!here) setProject(p.code); } });
  }
  for (const c of commands()) if (all(c.label + " command", c.more)) out.push(c);
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
