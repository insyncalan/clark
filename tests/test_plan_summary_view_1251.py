"""Row 1251: the Plan summary skeleton counts as empty however its tags are spaced, and View draws 'Nothing recorded.' for it.

Run: python3 dev/run_tests.py test_plan_summary_view_1251
Headless Chrome. logic/emptyBody.js is run on markup with a multi-space and a newline-plus-indent gap between tags (the same
skeleton, so empty), and the text Section is drawn in View (components/Section.jsx) from fixtures/plan_summary_view_demo.jsx at
1400 and 900 px: the unedited skeleton gives the one quiet line, a typed word gives the body.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from test_server import Running, chrome, wait

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "plan_summary_view_demo.jsx"
_PAGE = {}
SKELETON = "<h2>Where we are</h2><p></p><h2>What is next</h2><ul><li></li></ul>"
INDENTED = "<h2>Where we are</h2>\n  <p></p>\n  <h2>What is next</h2>\n  <ul>\n    <li></li>\n  </ul>"
SPACES = SKELETON.replace("><", ">   <")
TYPED = "<h2>Where we are</h2><p>On track.</p><h2>What is next</h2><ul><li></li></ul>"


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
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB" data-theme="light"><head><meta charset="utf-8"><title>t</title><style>{css}</style></head>\n'
                         f'<body><main><div id="root"></div></main>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class PlanSummaryView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.P", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, code):
        return self.cdp.js(code, self.sid)

    def width(self, w):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)

    def test_gaps_between_tags_of_any_length_still_count_as_empty(self):
        for body in (SKELETON, INDENTED, SPACES):
            with self.subTest(body=body):
                self.assertTrue(self.js(f"P.emptyBody({json.dumps(body)})"))

    def test_a_typed_word_is_not_empty_whatever_the_gaps(self):
        for body in (TYPED, TYPED.replace("><", ">\n  <")):
            with self.subTest(body=body):
                self.assertFalse(self.js(f"P.emptyBody({json.dumps(body)})"))

    def test_view_says_nothing_recorded_for_the_unedited_skeleton(self):
        for w in (1400, 900):
            self.width(w)
            for body in (SKELETON, INDENTED, SPACES):
                with self.subTest(width=w, body=body):
                    self.js(f"P.mount({json.dumps(body)})")
                    self.assertTrue(wait(lambda: self.js("!!document.querySelector('section .quiet, .quiet')")))
                    self.assertEqual(self.js("document.querySelector('.quiet').textContent"), "Nothing recorded.")
                    self.assertFalse(self.js("!!document.querySelector('[data-view-text]')"))

    def test_view_shows_the_body_when_a_word_is_typed(self):
        for w in (1400, 900):
            self.width(w)
            with self.subTest(width=w):
                self.js(f"P.mount({json.dumps(TYPED)})")
                self.assertTrue(wait(lambda: self.js("!!document.querySelector('[data-view-text]')")))
                self.assertIn("On track.", self.js("document.querySelector('[data-view-text]').textContent"))
                self.assertFalse(self.js("[...document.querySelectorAll('.quiet')].some(e => e.textContent === 'Nothing recorded.')"))


if __name__ == "__main__":
    unittest.main()
