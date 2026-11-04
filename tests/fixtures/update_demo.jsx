// Test-only (tests/test_update_page.py): the Settings › Version and updates card and its logic on a bare page, never part of clark's
// bundle. window.T gives the tests the logic; T.mount draws the card over a fake `api` whose answers a test sets in T.replies, and
// counts the reloads in T.reloads. T.calls records what the card asked for; T.copied what Copy put on the clipboard.
import { render } from "preact";
import * as logic from "@src/logic/update.js";
import { Update } from "@src/edit/Update.jsx";

const T = { logic, replies: {}, calls: [], reloads: 0, copied: [] };
window.T = T;
const answer = (key, extra) => { T.calls.push([key, extra]); const r = T.replies[key]; return Promise.resolve(typeof r === "function" ? r(extra) : r); };
const api = {
  status: () => answer("status"),
  review: (from, reinstall) => answer("review", { from, reinstall }),
  install: (id) => answer("install", id),
  arm: () => answer("arm"),
  undo: (id, appOnly) => answer("undo", { id, appOnly }),
  who: () => answer("who"),
};
T.mount = () => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="host" style="padding:16px"></div>';
  render(<Update api={api} reload={() => { T.reloads += 1; }} sleep={() => Promise.resolve()}
    copy={(t) => { if (T.copyFails) return Promise.reject(new Error("no")); T.copied.push(t); return Promise.resolve(); }} />,
  document.getElementById("host"));
};
