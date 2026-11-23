// Test-only (tests/test_ask_np_kill_1503_hook.py): the project's own asking line (AskHere, edit/NewProjects.jsx) on a bare page, never part of clark's bundle.
// The page itself never moves from one project to another under a mounted line (it leaves the page for "loading" first), so the hook's own rules for a changed
// project are shown here: T.show(code) draws the same line again for another project, in the same place. fetch is a stand-in: each read waits in T.out until
// T.answer(code, off_here) answers it, and T.reads lists the projects asked for, in order.
import { render } from "preact";
import { AskHere } from "@src/edit/NewProjects.jsx";

const T = { reads: [], out: {} };
window.T = T;

window.fetch = (url) => {
  const m = /project=([^&]*)/.exec(String(url));
  const code = m ? decodeURIComponent(m[1]) : "";
  T.reads.push(code);
  return new Promise((done) => { (T.out[code] = T.out[code] || []).push(done); });
};

/** Answer the oldest read still waiting for `code`: asking off for it when `off`. */
T.answer = (code, off) => {
  const done = (T.out[code] || []).shift();
  done(new Response(JSON.stringify({ ok: true, on: true, off_here: off }), { status: 200, headers: { "Content-Type": "application/json" } }));
};

T.show = (code) => {
  render(<AskHere code={code} />, document.getElementById("root"));
};
T.hide = () => render(null, document.getElementById("root"));
