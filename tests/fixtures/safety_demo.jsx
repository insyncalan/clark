// Test-only (tests/test_safety_logic.py): the Settings › Safety card and its logic on a bare page, never part of clark's bundle.
// window.T gives the tests the logic; T.mount draws the card over a fake `api` whose answers a test sets in T.replies, and counts
// the reloads in T.reloads. T.calls records what the card asked for.
import { render } from "preact";
import * as logic from "@src/logic/safety.js";
import { Safety } from "@src/edit/Safety.jsx";

const T = { logic, replies: {}, calls: [], reloads: 0, memory: {} };
window.T = T;
const fake = {
  getItem: (k) => (k in T.memory ? T.memory[k] : null),
  setItem: (k, v) => { T.memory[k] = v; },
  removeItem: (k) => { delete T.memory[k]; },
};
T.store = fake;
const answer = (key, extra) => { T.calls.push([key, extra]); const r = T.replies[key]; return Promise.resolve(typeof r === "function" ? r(extra) : r); };
const api = {
  list: () => answer("list"),
  preview: (name) => answer("preview", name),
  restore: (name, step) => answer("restore", { name, step }),
};
T.mount = () => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="host" style="padding:16px"></div>';
  render(<Safety api={api} reload={() => { T.reloads += 1; }} store={fake} />, document.getElementById("host"));
};
