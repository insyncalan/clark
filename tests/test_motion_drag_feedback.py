"""Row 887 (motion): drag feedback on the Board. Run: python3 dev/run_tests.py test_motion_drag_feedback

A card that is dragged lifts (its ghost grows into place; the card has no transform), the column it would land in eases its highlight in, and a column dragged by its heading lifts the
same way. Under reduced motion (the computer's setting or clark's own) the highlight and the dimming stay and nothing lifts or eases.
Checked at 1400 and 900 px, light and dark. The classes are the Board's own (bcard drag, col over, col moving); no drag logic changes.
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
# A card being dragged and two columns, with the classes Board.jsx gives them.
MAKE = """(() => { const d = document.createElement('div');
  d.innerHTML = '<div class="bghost"></div><section class="col over"></section><section class="col moving"></section><section class="col drop-before"></section>';
  document.body.appendChild(d); const q = (x) => getComputedStyle(d.querySelector(x));
  window.__d = d; return JSON.stringify([q('.bghost').animationName, q('.col.moving').animationName, q('.col.over').animationName, q('.col.drop-before').animationName]); })()"""
# Read after the lift has finished: a computed scale mid-animation is still the start of the run.
SETTLED = "window.__d.getAnimations({subtree: true}).length === 0"
FINAL = """(() => { const q = (x) => getComputedStyle(window.__d.querySelector(x)); return JSON.stringify([q('.bghost').scale, q('.col.moving').scale]); })()"""


class MotionDragFeedback(unittest.TestCase):
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

    def test_row_887_cards_lift_and_columns_highlight_and_all_is_still_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        ghost, moving, over, line = json.loads(cdp.js(MAKE, sid))
                        if motion == "no-preference":
                            self.assertEqual((ghost, moving, over, line), ("m-lift", "m-lift", "m-over", "m-col-line"))
                            self.assertTrue(wait(lambda: cdp.js(SETTLED, sid)), "the animations end")
                            self.assertEqual(json.loads(cdp.js(FINAL, sid)), ["1.05", "1.01"])
                        else:
                            self.assertEqual((ghost, moving, over, line), ("none", "none", "none", "none"))
                            self.assertEqual(json.loads(cdp.js(FINAL, sid)), ["none", "none"])

    def test_row_887_is_inside_the_motion_block_uses_tokens_and_lifts_with_a_transform_only(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        self.assertRegex(block, r"\.bghost \{ scale: 1\.05; animation: m-lift var\(--dur-instant\) var\(--ease-out\) 1; \}")
        self.assertRegex(block, r"\.col\.over \{ animation: m-over var\(--dur-state\) var\(--ease-enter\) 1; \}")
        self.assertNotRegex(CSS, r"\.bcard[^{]*\{[^}]*(transform|transition|scale)")      # the card holds its date picker: it gets no transform
        rest = CSS.replace(block, "")
        self.assertNotRegex(rest, r"animation:[^;]*m-(over|col-line)")
        for name in ("m-lift", "m-over", "m-col-line"):
            body = re.search(r"@keyframes " + name + r" \{(.*?)\}\s*\}", CSS, re.S).group(1)
            self.assertNotRegex(body, r"height|margin|padding|top|left|width")
        # the drag logic is not touched by this row: the Board only supplies the classes
        jsx = (ROOT / "src/clark/page/src/edit/Board.jsx").read_text(encoding="utf-8")
        self.assertRegex(jsx, r"dragging \? \" drag\"")


if __name__ == "__main__":
    unittest.main()
