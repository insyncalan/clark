"""Row 888 (motion): the small delights. Run: python3 dev/run_tests.py test_motion_micro_delight

A column's count badge ticks when its number changes (the class `settle`, from useSettle, never on the first draw), the toast's Undo pulses once
as it appears, and an eye blinks once when it is pressed (the button holds data-blink for that run). All transform only. Under reduced motion
(the computer's setting or clark's own) none of it runs. Checked at 1400 and 900 px, light and dark.
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
EDIT = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
# The three elements, with the classes the page gives them.
MAKE = """(() => { const d = document.createElement('div');
  d.innerHTML = '<div class="col"><div class="col-b"><span class="cn num settle">3</span></div></div><div class="toast"><button class="toast-btn" data-undo>Undo</button></div><button class="ib ms-eye" data-blink><svg class="i"></svg></button>';
  document.body.appendChild(d); const q = (x) => getComputedStyle(d.querySelector(x));
  return JSON.stringify([q('.cn').animationName, q('[data-undo]').animationName, q('.ms-eye svg').animationName, q('.cn').animationDuration]); })()"""


class MotionMicroDelight(unittest.TestCase):
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

    def test_row_888_the_badge_ticks_undo_pulses_and_the_eye_blinks_and_none_runs_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        names = json.loads(cdp.js(MAKE, sid))
                        if motion == "no-preference":
                            self.assertEqual(names[:3], ["m-count", "m-undo", "m-blink"])
                            self.assertEqual(names[3], "0.22s")
                        else:
                            self.assertEqual(names[:3], ["none", "none", "none"])

    def test_row_888_is_inside_the_motion_block_uses_tokens_and_moves_only_a_transform(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        self.assertRegex(block, r"\.col-b \.cn\.settle \{ animation: m-count var\(--dur-state\) var\(--ease-out\) 1; \}")
        self.assertRegex(block, r"\.toast-btn\[data-undo\] \{ animation: m-undo var\(--dur-enter\) var\(--ease-out\) 1; \}")
        # the eye rule is Edit's: in edit.css under both guards, and nowhere in shell.css (which the published file carries)
        self.assertRegex(EDIT, r"no-preference\) \{\s*:root:not\(\[data-motion=\"reduce\"\]\) :is\([^)]*\)\[data-blink\] svg \{ animation: m-blink var\(--dur-state\) var\(--ease-toggle\) 1; \}")
        self.assertNotRegex(CSS, r"data-blink|m-blink|ms-eye|ucl-eye|ucd-eye")
        self.assertNotRegex(CSS.replace(block, ""), r"animation:[^;]*m-(count|undo)")
        for name in ("m-count", "m-undo", "m-blink"):
            body = re.search(r"@keyframes " + name + r" \{(.*?)\}\s*\}", CSS + EDIT, re.S).group(1)
            self.assertRegex(body, r"transform")
            self.assertNotRegex(body, r"height|margin|padding|top|left|width|opacity")

    def test_row_888_the_page_gives_the_classes_only_when_something_changed(self):
        src = ROOT / "src/clark/page/src"
        board = (src / "edit/Board.jsx").read_text(encoding="utf-8")
        self.assertRegex(board, r"useSettle\(ref, n\)")
        self.assertRegex(board, r"<ColCount n=\{c\.count\} />")
        motion = (src / "stores/motion.js").read_text(encoding="utf-8")
        self.assertRegex(motion, r"export function blink\(e\)[\s\S]*?reduced\(\)[\s\S]*?animationend")
        for f in ("edit/MsEye.jsx", "edit/UseCasesPage.jsx", "components/UseCaseDetail.jsx", "edit/cells/Eye.jsx"):
            self.assertRegex((src / f).read_text(encoding="utf-8"), r"blink\(e\)", f)


if __name__ == "__main__":
    unittest.main()
