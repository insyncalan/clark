// Test-only (tests/test_past_reports_card.py): the Published reports page and its logic on a bare page, never part of
// clark's bundle. window.T gives the tests the logic; T.mount draws the card over a fake `api` whose answers a test sets in
// T.replies; T.calls records what the card asked for and T.toasts the toasts said (kind, words, and the Undo they offered, always none), T.tabs the addresses a new tab was pointed at (T.replies.tab = false is a
// blocked pop-up).
import { render } from "preact";
import * as logic from "@src/logic/pastReports.js";
import { PublishedPage } from "@src/edit/PublishedPage.jsx";
import { data } from "@src/stores/report.js";

const T = { logic, replies: {}, calls: [], tabs: [], toasts: [], went: [] };
T.setFolders = (local, client) => { data.value = { project: { name: "Example Programme", publish_local: local, publish_client: client } }; };
T.setFolders("/Users/example/clark reports/PDF", "Example Drive/Client reports");
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
  render(<PublishedPage api={api} openTab={openTab} toast={toast} code="PDF" name="Example Programme" goSettings={() => T.went.push("settings")} />, document.getElementById("host"));
};
