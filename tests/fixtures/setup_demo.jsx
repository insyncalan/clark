// Test-only (tests/test_setup_page.py): the first-run setup page on a bare page, never part of clark's bundle. T.replies.checks and
// T.replies.folder are what the fake server answers (a value, or a function); T.calls records what the page asked for; T.ready counts onReady.
import { render } from "preact";
import * as logic from "@src/logic/setup.js";
import { SetupPage } from "@src/edit/SetupPage.jsx";

const T = { logic, replies: {}, calls: [], ready: 0 };
window.T = T;
const answer = (key) => { T.calls.push(key); const r = T.replies[key]; return typeof r === "function" ? r() : Promise.resolve(r); };
const api = { checks: () => answer("checks"), chooseFolder: () => answer("folder") };
T.mount = () => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="host" style="padding:16px"></div>';
  render(<SetupPage api={api} onReady={() => { T.ready += 1; }} />, document.getElementById("host"));
};
T.unmount = () => { render(null, document.getElementById("host")); };
