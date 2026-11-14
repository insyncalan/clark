// Test-only (tests/test_brand_page.py): the Settings › Brands card on a bare page, never part of clark's bundle. window.T gives the
// tests the card's logic (src/logic/brand.js); T.mount draws the card over a fake `api` whose answers a test sets in T.replies,
// and T.calls records what the card asked for. item 944 T2.
import { render, options } from "preact";
import * as logic from "@src/logic/brand.js";
import { data } from "@src/stores/report.js";
import { Brands } from "@src/edit/Brands.jsx";

const T = { logic, replies: {}, calls: [], releases: [] };
window.T = T;
// With T.slowRender set the page draws a moment after a change, as a busy page does: code that runs right after a save sees what was drawn before it.
options.debounceRendering = (cb) => { if (T.slowRender) setTimeout(cb, 100); else Promise.resolve().then(cb); };
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
  // item 944: the open project is the page's own data signal (BrandPick reads it when no project is passed), so a change or an Undo
  // reaches the picker the way it does in clark. With T.keep set, a save is kept on the project, as clark keeps it.
  data.value = T.project ? { project: { ...T.project } } : null;
  // With T.hold set, a save waits until the test calls T.release(): the choice is on its way, as in clark. T.keep keeps it when it finishes.
  const pick = { save: (id, name) => {
    T.calls.push(["pick", [id, name]]);
    const done = () => { if (T.keep) T.setBrand(id); };
    if (!T.hold) { done(); return Promise.resolve(); }
    return new Promise((res) => T.releases.push(() => { done(); res(); }));
  } };
  render(<Brands api={api} pick={pick} />, document.getElementById("host"));
};
T.saved = () => data.value.project.brand;
T.release = () => { const r = T.releases.shift(); if (r) r(); };
T.setBrand = (id) => { data.value = { ...data.value, project: { ...data.value.project, brand: id } }; };
T.undoPick = (id) => { T.calls.push(["undo-pick", id]); T.setBrand(id); };      // Undo of a brand change: the earlier brand comes back
