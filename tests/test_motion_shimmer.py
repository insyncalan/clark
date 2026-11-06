"""Row 886 (motion): the loading placeholders shimmer. Run: python3 dev/run_tests.py test_motion_shimmer

A light band sweeps across each grey block, with a transform only (clipped to the block, so nothing shifts), over --dur-enter, for as long as
the placeholder shows. Under reduced motion (the computer's setting or clark's own) the still grey blocks are all there is.
Checked at 1400 and 900 px, light and dark.
"""
import json
import re
import unittest

from _paths import ROOT
import _testpage as testpage

from _real_server import real_server
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
# One grey block, the way Views.jsx draws it; the sweep is its ::after.
MAKE = """(() => { const t = document.createElement('span'); t.className = 'skel skel-line'; document.body.appendChild(t);
  const c = getComputedStyle(t, '::after'); const b = getComputedStyle(t); return JSON.stringify([c.animationName, c.animationDuration, c.animationIterationCount, b.overflow]); })()"""


class MotionShimmer(unittest.TestCase):
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
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#profile-btn')", sid)))
        return sid

    def test_row_886_the_blocks_shimmer_and_are_still_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        name, dur, count, overflow = json.loads(cdp.js(MAKE, sid))
                        if motion == "no-preference":
                            self.assertEqual((name, dur, count, overflow), ("m-shimmer", "0.7s", "infinite", "hidden"))
                        else:
                            self.assertEqual(name, "none")

    def test_row_886_is_inside_the_motion_block_uses_tokens_and_moves_only_a_transform(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        self.assertRegex(block, r"\.skel::after \{[^}]*animation: m-shimmer var\(--dur-enter\) var\(--ease-[a-z]+\) infinite;")
        self.assertNotRegex(CSS.replace(block, ""), r"animation:[^;]*m-shimmer")
        body = re.search(r"@keyframes m-shimmer \{(.*?)\}\s*\}", CSS, re.S).group(1)
        self.assertRegex(body, r"transform")
        self.assertNotRegex(body, r"height|margin|padding|top|left|width")


if __name__ == "__main__":
    unittest.main()
