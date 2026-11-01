// Test-only (tests/test_past_reports_card.py): the Settings › Published reports card and its logic on a bare page, never part of
// clark's bundle. window.T gives the tests the logic; T.mount draws the card over a fake `api` whose answers a test sets in
// T.replies; T.calls records what the card asked for and T.tabs the addresses a new tab was pointed at (T.replies.tab = false is a
// blocked pop-up).
import { render } from "preact";
import * as logic from "@src/logic/pastReports.js";
import { PublishedReports } from "@src/edit/PublishedReports.jsx";

const T = { logic, replies: {}, calls: [], tabs: [] };
window.T = T;
const answer = (key, extra) => { T.calls.push([key, extra]); const r = T.replies[key]; return Promise.resolve(typeof r === "function" ? r(extra) : r); };
const api = { list: (code) => answer("list", code), ready: (code, n) => answer("ready", { code, n }) };
const openTab = async (getUrl) => {
  if (T.replies.tab === false) return false;
  const url = await getUrl();
  if (typeof url !== "string") return false;
  T.tabs.push(url);
  return true;
};
T.mount = () => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="host" style="padding:16px"></div>';
  render(<PublishedReports api={api} openTab={openTab} code="PDF" name="Example Programme" />, document.getElementById("host"));
};
