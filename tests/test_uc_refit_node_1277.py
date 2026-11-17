"""Row 1277: the Use cases rows box refits when the page's own layout changes (a resize, a row growing, the fonts arriving), not only on the window's resize event. No browser.
Run: python3 dev/run_tests.py test_uc_refit_node_1277
"""
import json
import shutil
import subprocess
import unittest

from _paths import SRC

MOD = (SRC / "clark" / "page" / "src" / "logic" / "ucRefit.js").as_uri()

PROBE = """
const { watchRefit } = await import(%r);
const log = []; const out = {};
const win = { _l: {}, addEventListener(t, f) { this._l[t] = f; }, removeEventListener(t) { delete this._l[t]; } };
let obs = null;
win.ResizeObserver = class { constructor(f) { this.f = f; this.seen = []; this.off = false; obs = this; } observe(e) { this.seen.push(e); } disconnect() { this.off = true; } };
let fonts; const ready = new Promise((r) => { fonts = r; });
const doc = { fonts: { ready, status: "loading" } };
const ul = { children: ["r1", "r2"] };
const stop = watchRefit(win, doc, ul, () => log.push("again"), () => log.push("soft"));
const done = { fonts: { ready: Promise.resolve(), status: "loaded" } }; const lateLog = [];
const stop2 = watchRefit({ addEventListener() {}, removeEventListener() {} }, done, null, () => lateLog.push("again"), () => lateLog.push("soft"));
await Promise.resolve(); await Promise.resolve(); out.loadedFontsRefit = lateLog.length; stop2();
out.observed = obs.seen.length; out.hasResize = !!win._l.resize;
win._l.resize(); out.afterResize = log.length;
obs.f([]); out.afterObserver = log.length; out.observerKind = log[log.length - 1];
fonts(); await ready; await Promise.resolve(); out.afterFonts = log.length;
stop(); out.listenerGone = !win._l.resize; out.disconnected = obs.off;
obs.f([]); out.afterStop = log.length; out.kinds = log.join();
console.log(JSON.stringify(out));
""" % MOD

PROBE2 = """
const { watchRefit } = await import(%r);
const out = {};
const rej = []; process.on("unhandledRejection", (e) => rej.push(String(e)));
const mkwin = (withRO) => { const w = { _l: {}, obs: null, addEventListener(t, f) { this._l[t] = f; }, removeEventListener(t) { delete this._l[t]; } };
  if (withRO) w.ResizeObserver = class { constructor(f) { this.f = f; this.seen = []; w.obs = this; } observe(e) { this.seen.push(e); } disconnect() {} }; return w; };
const tick = () => new Promise((r) => setTimeout(r, 5));
// 1. nothing runs after stop, whichever of resize, observer or fonts arrives late
{ const win = mkwin(true); const log = []; let fonts; const ready = new Promise((r) => { fonts = r; });
  const stop = watchRefit(win, { fonts: { ready, status: "loading" } }, { children: ["r1"] }, () => log.push("again"), () => log.push("soft"));
  const resize = win._l.resize, obsf = win.obs.f; stop();
  resize(); obsf([]); fonts(); await tick(); out.afterStopLate = log.join(); }
// 2. no soft callback: the observer falls back to again
{ const win = mkwin(true); const log = [];
  watchRefit(win, null, { children: [] }, () => log.push("again")); win.obs.f([]); out.noSoft = log.join(); }
// 3. a ResizeObserver but no list: no observer made; a list but no ResizeObserver: no throw
{ const win = mkwin(true); let err = null;
  try { const st = watchRefit(win, null, null, () => {}); out.nullUlResize = !!win._l.resize; st(); } catch (e) { err = String(e); }
  out.nullUlErr = err; out.nullUlObs = win.obs === null;
  const w2 = mkwin(false); let err2 = null;
  try { watchRefit(w2, null, { children: ["r1"] }, () => {})(); } catch (e) { err2 = String(e); }
  out.noROErr = err2; }
// 4. a missing document, a document without fonts, fonts without ready
for (const [k, d] of [["docNull", null], ["docNoFonts", {}], ["fontsNoReady", { fonts: { status: "loading" } }]]) {
  let err = null; const win = mkwin(true); const log = [];
  try { watchRefit(win, d, { children: [] }, () => log.push("again"), () => log.push("soft"))(); } catch (e) { err = String(e); }
  out[k] = err; }
// 5. fonts.ready rejects: handled, no unhandled rejection
{ const win = mkwin(true); const log = [];
  const ready = Promise.reject(new Error("fonts failed"));
  watchRefit(win, { fonts: { ready, status: "loading" } }, { children: [] }, () => log.push("again"), () => log.push("soft"));
  await tick(); await tick(); out.rejLog = log.join(); out.unhandled = rej.length; }
console.log(JSON.stringify(out));
""" % MOD


class Refit(unittest.TestCase):
    def test_every_layout_change_refits_and_stop_ends_it(self):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("no node")
        r = subprocess.run([node, "--input-type=module", "-e", PROBE], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        o = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(o["observed"], 3, "the box and each row are watched")
        self.assertTrue(o["hasResize"])
        self.assertEqual(o["afterResize"], 1)
        self.assertEqual(o["afterObserver"], 2, "a row or the box changing size refits")
        self.assertEqual(o["observerKind"], "soft", "a row opening or closing must not clear the closed heights the box is fitted to, or the box moves (#1277)")
        self.assertEqual(o["kinds"], "again,soft,again", "resize and fonts clear and refit; the observer only refits")
        self.assertEqual(o["loadedFontsRefit"], 0, "fonts already loaded when the effect runs again (a row opened) change nothing, so they must not clear the closed heights")
        self.assertEqual(o["afterFonts"], 3, "the fonts arriving refits")
        self.assertTrue(o["listenerGone"] and o["disconnected"])
        self.assertEqual(o["afterStop"], 3, "after stop nothing refits")

    def test_edges_late_callbacks_missing_pieces_and_a_rejected_fonts_promise(self):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("no node")
        r = subprocess.run([node, "--input-type=module", "-e", PROBE2], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        o = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(o["afterStopLate"], "", "a resize, an observer call or the fonts arriving after stop() refits nothing")
        self.assertEqual(o["noSoft"], "again", "without a soft callback the observer falls back to again")
        self.assertIsNone(o["nullUlErr"], "a ResizeObserver with no list must not throw")
        self.assertTrue(o["nullUlObs"], "no list, nothing to observe, so no observer is made")
        self.assertTrue(o["nullUlResize"], "the resize listener is still added")
        self.assertIsNone(o["noROErr"], "a list with no ResizeObserver must not throw")
        for k in ("docNull", "docNoFonts", "fontsNoReady"):
            self.assertIsNone(o[k], k + " must not throw")
        self.assertEqual(o["rejLog"], "", "a rejected fonts.ready refits nothing")
        self.assertEqual(o["unhandled"], 0, "a rejected fonts.ready is handled, not an unhandled rejection")


if __name__ == "__main__":
    unittest.main()
