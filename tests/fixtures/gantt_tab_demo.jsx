// Test-only (tests/test_gantt_tab.py): the top bar, the open page and the Gantt card of Settings, drawn on a page with the shell styles, never part
// of clark's bundle. The server is a stand-in: window.fetch answers /api/data and /api/change from one project held here, so a tick or a rename
// is saved, read again and drawn exactly as the page does it. Every change request is kept in G.sent. Fictional data.
import { render } from "preact";
import { data, status, view, mode, project, tabs, SERVED_TABS } from "@src/stores/report.js";
import { TopBar } from "@src/components/TopBar.jsx";
import { Settings } from "@src/components/Views.jsx";
import { GanttView } from "@src/gantt/components/GanttView.jsx";
import { GanttSetting } from "@src/edit/GanttSetting.jsx";
import { GanttTabName } from "@src/edit/GanttTabName.jsx";
import { ReviewDays } from "@src/edit/ReviewDays.jsx";
import { Toast } from "@src/edit/Toast.jsx";

const G = { sent: [], undone: [], back: {}, project: null };
window.G = G;
const BASE = { code: "DEMO", name: "Harbour Bridge", health: "Green", health_reason: "", review_after_days: 14, show_gantt_editor: 0, show_gantt_client: 0, gantt_tab_name: "Gantt" };
const EMPTY = { project: null, actions: [], raid: [], decisions: [], milestones: [], report_sections: [], glance_tiles: [], use_cases: [] };

window.fetch = async (url, init) => {
  const u = String(url);
  const json = (body) => ({ ok: true, status: 200, json: async () => body });
  if (u.startsWith("/api/change")) {
    const req = JSON.parse(init.body);
    G.sent.push(req);
    G.back[G.sent.length] = Object.fromEntries(Object.keys(req.changes).map((k) => [k, G.project[k]]));      // what an Undo puts back
    Object.assign(G.project, req.changes);
    return json({ ok: true, apply_id: G.sent.length, project: { ...G.project }, sections: [] });
  }
  if (u.startsWith("/api/undo")) {
    const req = JSON.parse(init.body);
    G.undone.push(req.apply_id);
    Object.assign(G.project, G.back[req.apply_id]);
    return json({ ok: true, project: { ...G.project }, sections: [] });
  }
  if (u.startsWith("/api/data")) return json({ ok: true, data: { ...EMPTY, project: { ...G.project } } });
  return { ok: false, status: 404, json: async () => ({}) };
};

function Shell() {
  const Page = view.value === "gantt" ? GanttView : view.value === "settings" ? Settings : () => <section class="frame"><h1>Dashboard</h1></section>;
  const tools = mode.value === "edit" ? { GanttTabName, GanttSetting, ReviewDays } : {};
  return <><TopBar tools={tools} /><main id="main"><Page tools={tools} /></main><Toast /></>;
}

G.mount = (over, edit) => {
  G.sent = [];
  G.undone = [];
  G.back = {};
  G.project = { ...BASE, ...(over || {}) };
  project.value = "DEMO";
  data.value = { ...EMPTY, project: { ...G.project } };
  status.value = "ready";
  tabs.value = SERVED_TABS;
  mode.value = edit ? "edit" : "view";
  document.getElementById("root").innerHTML = '<div id="gt"></div>';
  render(<Shell />, document.getElementById("gt"));
};
G.set = (over) => { Object.assign(G.project, over); data.value = { ...EMPTY, project: { ...G.project } }; };
G.state = () => ({ tabs: [...document.querySelectorAll(".top .tab")].map((t) => t.textContent), view: view.value, hash: location.hash, project: { ...G.project } });
