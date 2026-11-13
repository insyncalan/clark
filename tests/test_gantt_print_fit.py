"""The print scale of the Gantt (row 1038, src/clark/page/src/gantt/logic/printFit.js), the pure part, pinned by a mutation audit of PR 1333.

The browser tests in test_gantt_print.py only see a chart that is a little too wide, so the paper width, the half-size floor, the rounding
down and the narrow chart that must not be touched all survived a change. Here the ratio and the box setter are called directly.

Run: python3 dev/run_tests.py test_gantt_print_fit
The repo has no Node: the module is bundled with the pinned esbuild and run in headless Chrome, as test_filter_line does.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

FIT = SRC / "clark" / "page" / "src" / "gantt" / "logic" / "printFit.js"
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "entry.js"
            entry.write_text(f'import * as P from {json.dumps(str(FIT))};\nwindow.T = {{ P }};\n', encoding="utf-8")
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), str(entry), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class Fit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.T && window.T.P)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def test_the_paper_is_703_px_and_the_floor_is_half(self):
        self.assertEqual(self.val("[T.P.PAGE_PX, T.P.FLOOR]"), [703, 0.5])

    def test_a_chart_that_fits_or_is_not_a_size_is_left_at_one(self):
        for natural in ("703", "702", "1", "0", "-5", "NaN", "undefined", "null", "'wide'"):
            self.assertEqual(self.val(f"T.P.fitRatio({natural})"), 1, natural)
        self.assertEqual(self.val("T.P.fitRatio(900, 0)"), 1, "no page width, no scaling")
        self.assertEqual(self.val("T.P.fitRatio(900, -1)"), 1)

    def test_one_px_too_wide_is_scaled_and_the_ratio_is_cut_down_to_three_places(self):
        self.assertEqual(self.val("T.P.fitRatio(704)"), 0.998)       # 0.99858: rounded down, so the chart never overshoots the paper
        self.assertEqual(self.val("T.P.fitRatio(900)"), 0.781)       # 0.78111
        self.assertEqual(self.val("T.P.fitRatio(1000)"), 0.703)
        self.assertEqual(self.val("T.P.fitRatio(1200, 600)"), 0.5)

    def test_a_very_wide_plan_stops_at_the_floor(self):
        self.assertEqual(self.val("T.P.fitRatio(1406)"), 0.5)
        self.assertEqual(self.val("T.P.fitRatio(1407)"), 0.5)
        self.assertEqual(self.val("T.P.fitRatio(5000)"), 0.5)
        self.assertEqual(self.val("T.P.fitRatio(5000, 703, 0.25)"), 0.25, "the floor is a parameter")

    def test_boxes_are_set_cleared_and_left_alone(self):
        got = self.val("""(function () {
          document.body.insertAdjacentHTML('beforeend',
            '<div id="fit-root">'
            + '<div class="gt-gx" id="wide"><div class="gt-lhead" style="width:600px;height:5px"></div><div class="gt-rhead" style="width:600px;height:5px"></div></div>'
            + '<div class="gt-gx" id="narrow" style="--gt-fit:0.7"><div class="gt-lhead" style="width:300px;height:5px"></div><div class="gt-rhead" style="width:300px;height:5px"></div></div>'
            + '<div class="gt-gx" id="nohead"><div class="gt-lhead" style="width:900px;height:5px"></div></div>'
            + '</div>');
          const root = document.getElementById('fit-root'), at = (id) => document.getElementById(id).style.getPropertyValue('--gt-fit');
          T.P.fitCharts(root, true);
          const on = [at('wide'), at('narrow'), at('nohead')];
          T.P.fitCharts(root, false);
          const off = [at('wide'), at('narrow'), at('nohead')];
          T.P.fitCharts(null, true); T.P.fitCharts({}, true);
          return { on, off };
        })()""")
        self.assertEqual(got["on"], ["0.585", "", ""], "the wide chart is scaled, the narrow one loses a stale scale, one with no right head is skipped")
        self.assertEqual(got["off"], ["", "", ""], "afterprint clears every box")


if __name__ == "__main__":
    unittest.main()
