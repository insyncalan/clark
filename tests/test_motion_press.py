"""Row 881 (motion): press feedback on buttons and cards. Run: python3 dev/run_tests.py test_motion_press

One shared rule per control class in the Motion block: the hover colours fade over --dur-instant, and a button or card lifts 1 px on hover (fine
pointers only) and settles on press. Transform and colour only, so nothing else moves. Under reduced motion (the computer's setting or
clark's own) the controls snap as before. Checked at 1400 and 900 px, light and dark.
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
EDIT = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
MAKE = """(() => { const o = {}; for (const [k, tag, cls] of [['btn', 'button', 'btn'], ['seg', 'button', ''], ['card', 'div', 'fig go']]) {
  const h = document.createElement('div'); if (k === 'seg') h.className = 'seg'; if (k === 'card') h.className = 'glance'; const e = document.createElement(tag); e.className = cls; e.textContent = 'x';
  h.appendChild(e); document.body.appendChild(h); const s = getComputedStyle(e); o[k] = [s.transitionProperty, s.transitionDuration]; } return JSON.stringify(o); })()"""


class MotionPress(unittest.TestCase):
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

    def test_row_881_controls_fade_and_cards_can_lift_and_snap_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        got = json.loads(cdp.js(MAKE, sid))
                        for k, (prop, dur) in got.items():
                            if motion == "no-preference":
                                self.assertIn("transform", prop, k)
                                self.assertEqual(set(dur.split(", ")), {"0.12s"} if k != "card" else {"0.12s", "0.22s"}, k)
                            elif k == "card":
                                # the card's own border and shadow fade is main's and stays; the new lift (transform) is absent
                                self.assertNotIn("transform", prop, k)
                            else:
                                self.assertEqual(set(dur.split(", ")), {"0s"}, k)

    def test_row_881_is_in_the_edit_stylesheet_only_gated_on_motion_and_uses_tokens(self):
        edit = EDIT[EDIT.index("Row 881 (motion)"):]
        self.assertTrue(edit.index("@media (prefers-reduced-motion: no-preference)") < edit.index("transition:"), "gated on no-preference")
        self.assertEqual(edit.count(':root:not([data-motion="reduce"])'), 3)
        for r in re.findall(r"[^{}]*\{[^}]*transition:[^}]*\}", edit):
            body = r[r.index("transition:"):]
            self.assertNotRegex(body, r"\b(height|width|margin|padding|top|left|max-height|max-width)\b")
            self.assertNotRegex(body, r"(?<![-\w(])\d+(\.\d+)?m?s\b")
            self.assertRegex(body, r"var\(--dur-[a-z]+\) var\(--ease-out\)")
        self.assertRegex(edit, r"\.btn:not\(\.primary\):not\(:disabled\)[^{]*\):hover \{ transform: translateY\(-1px\); \}")
        self.assertRegex(edit, r"\):active \{ transform: none; \}")
        lift = edit[edit.index("@media (hover: hover) and (pointer: fine)"):]
        self.assertIn(":hover { transform: translateY(-1px)", lift, "the lift is for fine pointers only")
        self.assertNotIn("row 881", CSS, "the shared stylesheet (the published page) holds none of it")
        self.assertNotRegex(CSS, r"\.hp-job:(hover|active) \{ transform")


if __name__ == "__main__":
    unittest.main()
