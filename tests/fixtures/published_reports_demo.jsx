// Test-only (tests/test_past_reports_card.py): the Settings › Published reports card and its logic on a bare page, never part of
// clark's bundle. window.T gives the tests the logic; T.mount draws the card over a fake `api` whose answers a test sets in
// T.replies; T.calls records what the card asked for and T.toasts the toasts said (kind, words, and the Undo they offered, always none), T.tabs the addresses a new tab was pointed at (T.replies.tab = false is a
// blocked pop-up).
import { render } from "preact";
import * as logic from "@src/logic/pastReports.js";
import { PublishedReports } from "@src/edit/PublishedReports.jsx";
import { Cover } from "@src/components/Cover.jsx";
import { data } from "@src/stores/report.js";

const T = { logic, replies: {}, calls: [], tabs: [], toasts: [], zone: "UTC", folders: { local: null, client: null }, toSettings: 0 };
window.T = T;
const answer = (key, extra) => { T.calls.push([key, extra]); const r = T.replies[key]; return Promise.resolve(typeof r === "function" ? r(extra) : r); };
const api = { list: (code, archived) => answer("list", archived ? { code, archived: true } : code), ready: (code, n) => answer("ready", { code, n }),
  archive: (code, n) => answer("archive", { code, n }), restore: (code, n) => answer("restore", { code, n }) };
const toast = (kind, text, undo) => { T.toasts.push([kind, text, undo === undefined ? null : undo]); };
const openTab = async (getUrl) => {
  const blocked = T.replies.tab === false;
  const url = await getUrl();                              // as the real openInNewTab: the address is asked for even when the tab was blocked
  if (blocked || typeof url !== "string") return false;
  T.tabs.push(url);
  return true;
};
T.mount = () => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="host" style="padding:16px"></div>';
  render(<PublishedReports api={api} openTab={openTab} toast={toast} code="PDF" name="Example Programme" zone={T.zone} folders={T.folders} toSettings={() => { T.toSettings += 1; }} />, document.getElementById("host"));
};

// Mutation proof (row 1087): the client name the band says, and the shared band with no `kind` given.
T.setClient = (n) => { data.value = { project: { name: "Example Programme", client_name: n } }; };
T.mountCover = () => { document.getElementById("root").innerHTML = '<div id="host"></div>'; render(<Cover title="Example Programme" lines={["Week ending 30-10-2026"]} />, document.getElementById("host")); };
