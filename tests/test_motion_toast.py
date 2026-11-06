"""Row 882 (motion): the toast and its Undo bar rise 8 px as they appear. Run: python3 dev/run_tests.py test_motion_toast

Over --dur-state with --ease-enter, opacity and transform only; the .toasts box holds the place, so nothing else moves. Under reduced
motion (the computer's setting) the toast shows at once. Checked at 1400 and 900 px, light and dark.
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
# A toast with Undo and Close, the way ToastCard draws it, in the foot box the page keeps.
MAKE = """(() => { const r = document.createElement('div'); r.className = 'toasts'; r.id = 'row882-r'; const t = document.createElement('div'); t.className = 'toast'; t.id = 'row882-t';
  t.innerHTML = '<span class="toast-text">x</span><button class="toast-btn" data-undo>Undo</button>'; r.appendChild(t); document.body.appendChild(r);
  const c = getComputedStyle(t); return JSON.stringify({name: c.animationName, dur: c.animationDuration, box: getComputedStyle(r).animationName}); })()"""


class MotionToast(unittest.TestCase):
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

    def test_row_882_the_toast_rises_in_and_is_still_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion, want, dur in (("no-preference", "m-up", "0.22s"), ("reduce", "none", "0s")):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        got = json.loads(cdp.js(MAKE, sid))
                        self.assertEqual((got["name"], got["dur"]), (want, dur))
                        self.assertEqual(got["box"], "none", "the box that holds the place does not move")

    def test_row_882_is_inside_the_motion_block_uses_tokens_and_moves_only_opacity_and_transform(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        self.assertRegex(block, r"\.toast \{ animation: m-up var\(--dur-state\) var\(--ease-enter\) 1; \}")
        self.assertNotRegex(CSS.replace(block, ""), r"animation:\s*m-up")
        body = re.search(r"@keyframes m-up \{(.*?)\}\s*\}", CSS, re.S).group(1)
        self.assertNotRegex(body, r"height|margin|padding|top|left|width")
        self.assertRegex(body, r"opacity: 0; transform: translateY\(8px\)")


if __name__ == "__main__":
    unittest.main()
