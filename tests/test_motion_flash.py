"""Row 879 (motion): a changed field in the peek and the "please look here" line flash, then settle. Run: python3 dev/run_tests.py test_motion_flash

The section, Work items and milestone rows already glow (m-glow, motion item 3); this row moves the peek's two flashes into the Motion block on
tokens (about 1.6 s and 1 s), so under reduced motion (the computer's setting or clark's own) they show the still tint and the word, no motion.
The flash starts when the page marks a field changed (flash() after a change or an Undo), so a redraw without a change does not run it.
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
MAKE = """(() => { const o = []; for (const c of ['pk-row', 'sn-confirm']) { const e = document.createElement('div'); e.className = c + ' flash'; document.body.appendChild(e);
  const s = getComputedStyle(e); o.push([s.animationName, s.animationDuration, s.backgroundColor]); } return JSON.stringify(o); })()"""


class MotionFlash(unittest.TestCase):
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

    def test_row_879_the_peek_flashes_and_is_a_still_tint_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        row, line = json.loads(cdp.js(MAKE, sid))
                        if motion == "no-preference":
                            self.assertEqual((row[0], row[1]), ("sn-flash", "1.62s"))
                            self.assertEqual((line[0], line[1]), ("sn-flash", "1.04s"))
                        else:
                            self.assertEqual((row[0], line[0]), ("none", "none"))
                            self.assertNotIn(row[2], ("rgba(0, 0, 0, 0)", "transparent"), "the still tint stays")
                            self.assertNotIn(line[2], ("rgba(0, 0, 0, 0)", "transparent"))

    def test_row_879_is_inside_the_motion_block_uses_tokens_and_the_old_bare_times_are_gone(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        for sel in (".pk-row.flash", ".sn-confirm.flash"):
            self.assertRegex(block, re.escape(sel) + r" \{ animation: sn-flash calc\([^;]*var\(--dur-[a-z]+\)[^;]*\) var\(--ease-out\) 1; \}")
        self.assertNotRegex(CSS.replace(block, ""), r"animation:\s*sn-flash")
        self.assertRegex(CSS, r'data-motion="reduce"\] :is\(\.pk-row\.flash, \.sn-confirm\.flash\) \{ background: var\(--status-amber-tint\)')


if __name__ == "__main__":
    unittest.main()
