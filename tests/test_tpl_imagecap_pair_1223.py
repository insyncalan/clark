"""Row 1580 (the delta of row 1223): two half width Images paired in the published report's own grid. The view part of the Image (an imagecap
section with a body of version 2) is drawn twice into the page's real grid (shell.css `.secs`, with the slot classes of logic/placement.js), at
1400 and 900 px, light and dark: side by side at 1400, stacked at full width at 900, no sideways scroll.
The older tests draw one Image on a bare page at the half width (test_tpl_imagecap_half_1223.py) or text sections in the grid
(test_pair_widths_1214.py); this one draws two Images in the grid.

Run: python3 dev/run_tests.py test_tpl_imagecap_pair_1223
Needs Chrome (the #33 harness): fails, never skips, without it. Fictional data only.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from test_server import Running, chrome, wait
from test_tpl_imagecap_full_view import png, uri

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "imagecap_pair_demo.jsx"
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        import esbuild
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8") + (PAGE_SRC.parent / "shell.css").read_text(encoding="utf-8")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB" data-theme="light"><head><meta charset="utf-8"><title>t</title><style>{css}\nbody {{ margin: 0; }}</style></head>\n'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def section(id, alt, beside=0):
    content = {"image": uri(png(1600, 400)), "caption": "", "alt": alt, "full": 1, "fit": "stretch"}
    return {"id": id, "type": "imagecap", "title": "", "beside": beside, "hidden": 0, "content": content}


PAIR = [section("ABC-S-001", "Fictional left", beside=1), section("ABC-S-002", "Fictional right")]


class Pair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.F", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, code):
        return self.cdp.js(code, self.sid)

    def draw(self, width, theme):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
        self.js(f"F.mount({json.dumps(PAIR)})")
        self.assertTrue(wait(lambda: self.js("document.querySelectorAll('.tpl-fullimg-img').length === 2 && [...document.querySelectorAll('.tpl-fullimg-img')].every(i => i.complete && i.naturalWidth > 0)")), "both images loaded")
        return self.js("""(function(){
          var grid=document.querySelector('.secs'), g=grid.getBoundingClientRect(), gap=parseFloat(getComputedStyle(grid).columnGap);
          var secs=[...document.querySelectorAll('.secs > .sec')].map(function(s){var r=s.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width};});
          var figs=[...document.querySelectorAll('.tpl-fullimg')].map(function(f){var r=f.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width};});
          var imgs=[...document.querySelectorAll('.tpl-fullimg-img')].map(function(f){var r=f.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width};});
          return {grid:g.width, gap:gap, mlb:parseFloat(getComputedStyle(document.querySelectorAll('.secs > .sec')[1]).marginLeft) || 0, secs:secs, figs:figs, imgs:imgs, n:document.querySelectorAll('.tpl-fullimg').length,
                  scroll:[document.documentElement.scrollWidth, document.documentElement.clientWidth]};})()""")

    def test_two_half_width_images_sit_side_by_side_at_1400_and_stack_at_900(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                m = self.draw(width, theme)
                with self.subTest(width=width, theme=theme):
                    self.assertEqual(m["n"], 2)
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1], "no sideways scroll")
                    a, b = m["secs"]
                    fa, fb = m["figs"]
                    if width == 1400:
                        half = (m["grid"] - m["gap"]) / 2
                        self.assertGreater(m["gap"], 0, "the grid has a side gap")
                        self.assertLessEqual(abs(a["width"] - half), 1, "each section is the content width less the gap, over two")
                        # the page's default density pulls the right section 24 px left over the gap (shell.css `.sec.slot-right { margin-left: -24px; padding-left: 24px }`): its box is the half less that margin, its content the same width as the left one
                        self.assertLessEqual(abs(b["width"] - (half - m["mlb"])), 1, "the right section is the half, plus what its negative left margin gives back")
                        self.assertLessEqual(abs(a["top"] - b["top"]), 1, "side by side: the tops are equal")
                        self.assertLessEqual(a["right"], b["left"] + 1, "two across, the first on the left")
                        self.assertLessEqual(abs(fa["width"] - fb["width"]), 1, "the two Images are the same width")
                        self.assertLess(fa["width"], half + 1)
                        self.assertLessEqual(abs(m["imgs"][0]["width"] - fa["width"]), 1, "stretched: the image fills its half")
                    else:
                        self.assertLessEqual(abs(a["width"] - m["grid"]), 1, "stacked: the first is the full content width")
                        self.assertLessEqual(abs(b["width"] - m["grid"]), 1, "stacked: the second is the full content width")
                        self.assertGreaterEqual(b["top"], a["bottom"] - 1, "the second is below the first, one across")
                        self.assertLessEqual(abs(fa["width"] - fb["width"]), 1)
                        self.assertGreater(fa["width"], m["grid"] / 2 + 100, "each Image is wider than half the grid")


if __name__ == "__main__":
    unittest.main()
