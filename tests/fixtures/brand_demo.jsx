// Test-only (tests/test_brand_page.py): the Settings › Brands card on a bare page, never part of clark's bundle. window.T gives the
// tests the card's logic (src/logic/brand.js); T.mount draws the card over a fake `api` whose answers a test sets in T.replies,
// and T.calls records what the card asked for. #944 T2.
import { render } from "preact";
import * as logic from "@src/logic/brand.js";
import { Brands } from "@src/edit/Brands.jsx";

const T = { logic, replies: {}, calls: [] };
window.T = T;
const answer = (key, extra) => { T.calls.push([key, extra]); const r = T.replies[key]; return Promise.resolve(typeof r === "function" ? r(extra) : r); };
const api = {
  list: () => answer("list"),
  review: (from) => answer("review", { from }),
  install: (id) => answer("install", id),
  remove: (id) => answer("remove", id),
  undo: () => answer("undo"),
};
T.mount = () => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="host" style="padding:16px"></div>';
  const pick = { project: T.project, save: (id, name) => { T.calls.push(["pick", [id, name]]); return Promise.resolve(); } };      // #944: the open project and what saving its brand does
  render(<Brands api={api} pick={pick} />, document.getElementById("host"));
};
