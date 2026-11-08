"""Row 881 (motion): press feedback on buttons and cards. Run: python3 dev/run_tests.py test_motion_press

One shared rule per control class in the Motion block: the hover colours fade over --dur-instant, and a button or card lifts 1 px on hover (fine
pointers only) and settles on press. Transform and colour only, so nothing else moves. Under reduced motion (the computer's setting or
clark's own) the controls snap as before. Checked at 1400 and 900 px, light and dark.
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
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#dashboard&p={self.code}")}, sid)
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
        start = EDIT.index("Row 881 (motion)")
        end = EDIT.find("\n/* row ", start + 1)      # the next row's block (another row's rules may follow this one in edit.css)
        edit = EDIT[start:] if end == -1 else EDIT[start:end]
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

    def test_row_938_1_main_buttons_and_mode_pills_sink_1px_on_press_edit_only_gated_on_motion(self):
        start = EDIT.index("row 938-1 (motion)")
        end = EDIT.find("\n/* row ", start + 1)
        edit = EDIT[start:end]
        rule = re.search(r":is\(([^)]*)\)[^{]*:active \{([^}]*)\}", edit)
        self.assertIsNotNone(rule)
        self.assertEqual(set(x.strip() for x in rule.group(1).split(",")), {".again", ".btn.primary", ".btn.pri", ".modes.seg .mode"})
        self.assertIn("transform: translateY(1px)", rule.group(2), "sinks 1 px")
        self.assertIn("transform var(--dur-instant) var(--ease-out)", rule.group(2), "over --dur-instant")
        self.assertTrue(edit.index("@media (prefers-reduced-motion: no-preference)") < edit.index(":active"), "gated on no-preference")
        self.assertIn(':root:not([data-motion="reduce"])', edit.split(":active")[0], "and on clark's own reduced motion")
        self.assertNotRegex(rule.group(2), r"(?<![-\w(])\d+(\.\d+)?m?s\b", "tokens only")
        self.assertNotRegex(CSS, r"\.(again|btn\.primary|btn\.pri|modes\.seg \.mode)[^{]*:active", "the published page's stylesheet holds no press sink")
        self.assertNotIn("938-1", CSS)

    def test_row_938_1_press_sinks_in_the_browser_and_snaps_when_reduced(self):
        for scheme in ("light", "dark"):
            for motion in ("no-preference", "reduce"):
                with self.subTest(scheme=scheme, motion=motion), chrome() as cdp:
                    sid = self.load(cdp, 1400, scheme, motion)
                    for cls, host in (("again", ""), ("btn primary", ""), ("btn pri", ""), ("mode", "modes seg")):
                        cdp.js("""(() => { document.querySelectorAll('.t938').forEach(x => x.remove()); const h = document.createElement('div'); h.className = 't938 %s';
                          h.style.cssText = 'position:fixed;left:20px;top:20px;z-index:99999'; const e = document.createElement('button'); e.id = 't938b'; e.className = '%s'; e.textContent = 'x';
                          h.appendChild(e); document.body.appendChild(h); })()""" % (host, cls), sid)
                        box = json.loads(cdp.js("(() => { const r = document.getElementById('t938b').getBoundingClientRect(); return JSON.stringify([r.x + r.width / 2, r.y + r.height / 2]); })()", sid))
                        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, sid)
                        M42 = "new DOMMatrix(getComputedStyle(document.getElementById('t938b')).transform).m42"
                        hovered = cdp.js(M42, sid)       # the shared stylesheet's own hover lift (if any) is the baseline
                        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": box[0], "y": box[1], "button": "left", "buttons": 1, "clickCount": 1}, sid)
                        self.assertTrue(wait(lambda: cdp.js("document.getElementById('t938b').matches(':active')", sid)), cls)
                        if motion == "no-preference":
                            self.assertTrue(wait(lambda: cdp.js(M42, sid) == 1), f"{cls} sinks 1 px")
                            self.assertIn("0.12s", cdp.js("getComputedStyle(document.getElementById('t938b')).transitionDuration", sid), f"{cls} presses over --dur-instant")
                        else:
                            self.assertEqual(cdp.js(M42, sid), hovered, f"{cls} does not move under reduced motion")
                        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": box[0], "y": box[1], "button": "left", "buttons": 0, "clickCount": 1}, sid)


if __name__ == "__main__":
    unittest.main()
