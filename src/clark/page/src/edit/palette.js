// The command palette's search and actions (#198), Edit parts only: a published file has no palette. Plain JS, no DOM: it takes
// what the page already holds (the open project's data, the project list, the tabs) and gives back the results in order:
// commands, pages, projects, work items (an ID first, then words in the title) and milestones. Nothing here asks a server, and a
// command that changes anything calls the very function the existing button or menu entry calls (profile menu, Publish).
import { signal } from "@preact/signals";
import { data, tabs, TITLES, project, projects, view, rows, show, setProject, openPeek, fromFile, status } from "../stores/report.js";
import { KIND_WORDS } from "../workItems.js";
import { openPublish } from "./Publish.jsx";
import { preview, exportExcel } from "./ProfileMenu.jsx";
import { openHelp, closeHelp, helpOpen } from "../help/helpStore.js";

export const paletteOpen = signal(false);
export const MOST_ITEMS = 8;          // work items shown at most, so a short word does not fill the box
export const DARK_WHY = "clark follows the light or dark setting of your computer. Change it there.";
const NEED_PROJECT = "Open a project first.";

const lower = (s) => String(s == null ? "" : s).toLowerCase();
const words = (q) => lower(q).split(/\s+/).filter(Boolean);
const hits = (text, ws) => { const t = lower(text); return ws.every((w) => t.includes(w)); };

function commands() {
  const ready = !!data.value && status.value === "ready" && !fromFile.value;
  const why = ready ? "" : NEED_PROJECT;
  return [
    { key: "publish", label: "Publish…", more: "report send client", why, run: () => openPublish() },
    { key: "preview", label: "Preview the page in a new tab", more: "published page", why, run: () => preview() },
    { key: "export", label: "Export to Excel", more: "workbook download xlsx", why, run: () => exportExcel() },
    { key: "settings", label: "Settings", more: "options folder client", why: tabs.value.includes("settings") ? "" : "Settings is not available on this page.", run: () => show("settings") },
    { key: "help", label: "Help", more: "keys shortcuts how", why: "", run: () => openHelp() },
    { key: "dark", label: "Dark mode", more: "light theme look", why: DARK_WHY, run: () => {} },
  ].map((c) => ({ id: "cmd-" + c.key, kind: "Command", label: c.label, more: c.more, disabled: c.why, run: c.run }));
}

function pages() {
  return tabs.value.filter((v) => v !== "settings" && TITLES[v]).map((v) => ({ id: "page-" + v, kind: "Page", label: TITLES[v], more: "", disabled: "", current: view.value === v, run: () => show(v) }));
}

/** The results for `query`, in the order they are shown. An empty query gives the commands, the pages and the projects. */
export function search(query) {
  const ws = words(query), all = (t, extra) => !ws.length || hits(t + " " + (extra || ""), ws);
  const out = [];
  for (const c of commands()) if (all(c.label + " command", c.more)) out.push(c);
  for (const p of pages()) if (all(p.label + " page")) out.push(p);
  for (const p of projects.value || []) {
    if (!all(p.name + " " + p.code + " project")) continue;
    const here = p.code === project.value;
    out.push({ id: "project-" + p.code, kind: "Project", label: p.name || p.code, more: p.code, disabled: "", current: here, run: () => { if (!here) setProject(p.code); } });
  }
  if (ws.length && data.value) {
    const q = lower(query).trim();
    const items = rows.value.filter((r) => hits(r.id + " " + r.title, ws));
    const byId = (r) => (lower(r.id) === q ? 0 : lower(r.id).startsWith(q) ? 1 : lower(r.id).includes(q) ? 2 : 3);
    items.sort((a, b) => byId(a) - byId(b));          // stable: an ID match first, the rest keep the page's order
    for (const r of items.slice(0, MOST_ITEMS)) {
      out.push({ id: "item-" + r.id, kind: KIND_WORDS[r.kind] || "Work item", label: r.title || r.id, more: r.id, disabled: "", run: () => { if (view.value === "settings") show("work"); openPeek(r.id, "item"); } });
    }
    for (const m of data.value.milestones || []) {
      if (hits(m.name + " " + m.id + " milestone", ws)) out.push({ id: "ms-" + m.id, kind: "Milestone", label: m.name || m.id, more: m.id, disabled: "", run: () => { if (view.value === "settings") show("milestones"); openPeek(m.id, "milestone"); } });
    }
  }
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
