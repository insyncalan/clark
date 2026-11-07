"""Row 934 (replaces 886): the loading placeholders are static. Run: python3 dev/run_tests.py test_skeleton_static

The grey blocks never animate, with motion allowed or reduced: no ::after band, no animation on the block. Checked at 1400 and 900 px,
light and dark.
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
# One grey block, the way Views.jsx draws it.
MAKE = """(() => { const t = document.createElement('span'); t.className = 'skel skel-line'; document.body.appendChild(t);
  const c = getComputedStyle(t, '::after'); const b = getComputedStyle(t); return JSON.stringify([c.animationName, c.content, b.animationName, b.overflow]); })()"""


class SkeletonStatic(unittest.TestCase):
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

    def test_row_934_the_blocks_are_still_with_motion_allowed_or_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        after_name, after_content, name, overflow = json.loads(cdp.js(MAKE, sid))
                        self.assertEqual((after_name, name), ("none", "none"))
                        self.assertIn(after_content, ("none", "normal"), "no ::after band")

    def test_row_934_no_shimmer_or_loop_is_left_in_the_stylesheet(self):
        self.assertNotIn("m-shimmer", CSS)
        self.assertNotRegex(CSS, r"\.skel[^{]*::after")
        skel = re.findall(r"\.skel[\w-]*[^{]*\{([^{}]*)\}", CSS)
        self.assertTrue(skel)
        self.assertEqual([x for x in skel if "infinite" in x], [])   # .skel-leave fades the frame out once; that is not a loop


if __name__ == "__main__":
    unittest.main()
