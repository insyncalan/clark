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
const log = [];
const win = { _l: {}, addEventListener(t, f) { this._l[t] = f; }, removeEventListener(t) { delete this._l[t]; } };
let obs = null;
win.ResizeObserver = class { constructor(f) { this.f = f; this.seen = []; this.off = false; obs = this; } observe(e) { this.seen.push(e); } disconnect() { this.off = true; } };
let fonts; const ready = new Promise((r) => { fonts = r; });
const doc = { fonts: { ready } };
const ul = { children: ["r1", "r2"] };
const stop = watchRefit(win, doc, ul, () => log.push("again"));
const out = {};
out.observed = obs.seen.length; out.hasResize = !!win._l.resize;
win._l.resize(); out.afterResize = log.length;
obs.f([]); out.afterObserver = log.length;
fonts(); await ready; await Promise.resolve(); out.afterFonts = log.length;
stop(); out.listenerGone = !win._l.resize; out.disconnected = obs.off;
obs.f([]); out.afterStop = log.length;
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
        self.assertEqual(o["afterFonts"], 3, "the fonts arriving refits")
        self.assertTrue(o["listenerGone"] and o["disconnected"])
        self.assertEqual(o["afterStop"], 3, "after stop nothing refits")


if __name__ == "__main__":
    unittest.main()
