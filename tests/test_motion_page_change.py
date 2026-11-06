"""Row 876 (motion): the page fades in and rises 8 px (--dur-view, --ease-enter) on a tab change only, never on a redraw in place.
Run: python3 dev/run_tests.py test_motion_page_change

App.jsx puts .view-in on <main> when the view name changes (not on the first draw, not when the same view is drawn again) and shell.css
animates it inside the one Motion block, so under reduced motion nothing animates. Opacity and transform only. 1400 and 900 px, light and dark.
"""
import re
import time
import unittest

from _paths import ROOT
import _testpage as testpage

from _real_server import real_server
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
TOKENS = (ROOT / "src/clark/brand/tokens.css").read_text(encoding="utf-8")
WATCH = """(() => { window.__names = []; const m = document.querySelector('main'); new MutationObserver(() => { if (m.classList.contains('view-in')) window.__names.push(getComputedStyle(m).animationName); })
  .observe(m, {attributes: true, attributeFilter: ['class']}); })()"""


class MotionPageChange(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, width, scheme, motion):
        projects = self.store.read("projects")
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda archived=False: projects,
                        page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                              {"name": "prefers-reduced-motion", "value": motion}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#dashboard&p={self.code}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('main') && !document.querySelector('main').getAttribute('aria-busy') && !!document.querySelector('main *')", sid)))
        return sid

    def test_row_876_a_tab_change_fades_and_rises_in_and_a_redraw_or_first_draw_does_not(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion, want in (("no-preference", "m-view"), ("reduce", "none")):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        self.assertEqual(cdp.js("document.querySelector('main').classList.contains('view-in')", sid), False, "the first draw is not a tab change")
                        cdp.js(WATCH, sid)
                        cdp.js(f"location.hash = '#work&p={self.code}'", sid)
                        self.assertTrue(wait(lambda: cdp.js("window.__names.length > 0", sid)), "a tab change starts it")
                        self.assertEqual(cdp.js("window.__names[0]", sid), want)
                        if motion == "no-preference":
                            self.assertTrue(wait(lambda: not cdp.js("document.querySelector('main').classList.contains('view-in')", sid)), "the class comes off when it ends")
                        cdp.js("window.__names = []", sid)
                        cdp.js(f"location.hash = '#work&p={self.code}&x=1'", sid)    # the same view drawn again
                        time.sleep(0.5)
                        self.assertEqual(cdp.js("window.__names", sid), [], "a redraw in place does not start it")

    def test_row_876_is_in_edit_css_only_inside_the_gate_uses_tokens_and_moves_only_opacity_and_transform(self):
        self.assertRegex(TOKENS, r"--dur-view:\s*180ms")
        edit = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
        gate = edit[edit.index("row 876"):]
        self.assertIn("@media (prefers-reduced-motion: no-preference)", gate)
        self.assertIn(':root:not([data-motion="reduce"])', gate)
        self.assertRegex(gate, r"main\.view-in \{ animation: m-view var\(--dur-view\) var\(--ease-enter\) 1; \}")
        body = re.search(r"@keyframes m-view \{(.*?)\}\s*\}", gate, re.S).group(1)
        self.assertNotRegex(body, r"height|margin|padding|top|left|width")
        self.assertRegex(body, r"opacity: 0; transform: translateY\(var\(--space-2\)\)")
        self.assertNotIn("view-in", CSS, "the shared stylesheet (the published page's) has no view-in")
        self.assertNotIn("m-view", CSS)
        view = ROOT / "src/clark/page/page-view.html"
        if view.exists():
            html = view.read_text(encoding="utf-8")
            self.assertNotIn("m-view", html)
            self.assertNotIn(".view-in", html)

    def test_row_876_only_a_change_of_view_in_the_editor_starts_it(self):
        app = (ROOT / "src/clark/page/src/components/App.jsx").read_text(encoding="utf-8")
        self.assertRegex(app, r"fromFile\.value \|\| was\.current === view\.value\) return", "a published file and a redraw in place do nothing")


if __name__ == "__main__":
    unittest.main()
