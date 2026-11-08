"""Row 883 (motion): the check mark draws itself when a publish completes. Run: python3 dev/run_tests.py test_motion_tick

The path of the tick is drawn with a dash offset over --dur-layout, once, after the green disc appears. Under reduced motion (the computer's
setting or clark's own) the whole tick is there at once, with no dash. The tick is drawn only in the done state, so it never runs on a redraw.
Checked at 1400 and 900 px, light and dark.
"""
import json
import re
import unittest
from _editor_checks import for_url

from _paths import ROOT
import _testpage as testpage

from _real_server import real_server
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
# The done tick, the way Publish.jsx draws it.
MAKE = """(() => { const t = document.createElement('span'); t.className = 'pub-tick'; t.innerHTML = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 6 9 17l-5-5"/></svg>';
  document.body.appendChild(t); const c = getComputedStyle(t.querySelector('path')); return JSON.stringify([c.animationName, c.animationDuration, c.strokeDasharray]); })()"""


class MotionTick(unittest.TestCase):
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
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#dashboard&p={self.code}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#profile-btn')", sid)))
        return sid

    def test_row_883_the_check_mark_draws_and_is_whole_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        name, dur, dash = json.loads(cdp.js(MAKE, sid))
                        if motion == "no-preference":
                            self.assertEqual((name, dur), ("m-draw", "0.38s"))
                            self.assertNotEqual(dash, "none")
                        else:
                            self.assertEqual((name, dash), ("none", "none"))

    def test_row_883_is_inside_the_motion_block_uses_tokens_and_draws_only_the_stroke(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        self.assertRegex(block, r"\.pub-tick \.i path \{ stroke-dasharray: 24; animation: m-draw var\(--dur-layout\) var\(--ease-out\) 1; \}")
        self.assertNotRegex(CSS.replace(block, ""), r"stroke-dasharray|animation:\s*m-draw")
        body = re.search(r"@keyframes m-draw \{(.*?)\}\s*\}?", CSS, re.S).group(1)
        self.assertRegex(body, r"stroke-dashoffset")
        self.assertNotRegex(body, r"height|margin|padding|top|left|width")


if __name__ == "__main__":
    unittest.main()
