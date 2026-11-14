"""Row 884 (motion): the View/Edit pill's thumb slides, the Edit chrome fades in. Run: python3 dev/run_tests.py test_motion_modes

The Dashboard pill's thumb (a ::before the page measures into --vw, --tx and --sx) slides over --dur-state with --ease-toggle, transform only; the Edit-only
gutter and drag hint fade in over --dur-state. Under reduced motion the pill swaps at once, with the button's own still fill. Checked at 1400 and 900 px, light and dark.
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
# The Dashboard pill as Toggle draws it, an Edit gutter and the drag hint.
MAKE = """(() => { const r = document.createElement('div'); r.className = 'rbar'; r.innerHTML = '<span class="modes seg glide"><button class="mode" data-mode="view" aria-pressed="false">View</button><button class="mode" data-mode="edit" aria-pressed="true">Edit</button></span><span class="rbar-hint">h</span>';
  document.body.appendChild(r); const g = document.createElement('div'); g.className = 'sec-ctl'; document.body.appendChild(g);
  const t = getComputedStyle(r.querySelector('.modes'), '::before'), c = n => getComputedStyle(document.querySelector(n));
  return JSON.stringify({prop: t.transitionProperty, dur: t.transitionDuration, ctl: c('.sec-ctl').animationName, hint: c('.rbar-hint').animationName, hintDur: c('.rbar-hint').animationDuration}); })()"""


class MotionModes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, width, scheme, motion, view="dashboard"):
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
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#{view}&p={self.code}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#profile-btn')", sid)))
        return sid

    def test_row_884_the_thumb_slides_and_the_edit_chrome_fades_and_both_are_still_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion, prop, name, dur in (("no-preference", "transform", "m-in", "0.22s"), ("reduce", "all", "none", "0s")):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        got = json.loads(cdp.js(MAKE, sid))
                        self.assertEqual((got["prop"], got["dur"]), (prop, dur))
                        self.assertEqual((got["ctl"], got["hint"]), (name, name))

    def test_row_884_the_thumb_is_measured_again_when_the_window_width_changes(self):
        from test_server import chrome
        want = """(() => { const g = document.querySelector('#gantt-bar .modes.glide'), v = g.querySelector('[data-mode=view]'), on = g.querySelector('[aria-pressed=true]');
          return g.style.getPropertyValue('--vw') === v.offsetWidth + 'px' && g.style.getPropertyValue('--tx') === (on.offsetLeft - v.offsetLeft) + 'px'
            && Math.abs(parseFloat(g.style.getPropertyValue('--sx')) - on.offsetWidth / v.offsetWidth) < 0.001; })()"""
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                sid = self.load(cdp, 1400, scheme, "no-preference", "gantt")      # item 1177: the Dashboard's pill floats and has no thumb; Toggle's sliding pill is the Gantt page's
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#gantt-bar .modes.glide')", sid)), "the Gantt page's pill drew")
                self.assertTrue(wait(lambda: cdp.js(want, sid)), "measured at 1400")
                for width in (900, 1400):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    self.assertTrue(wait(lambda: cdp.js(want, sid)), f"measured again at {width}")
                cdp.js("document.querySelector('#gantt-bar .modes.glide [data-mode=edit]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(want, sid)), "and after a switch")

    def test_row_884_is_inside_the_motion_block_uses_tokens_and_the_still_pill_is_untouched(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        self.assertRegex(block, r"\.modes\.seg\.glide::before \{[^}]*transition: transform var\(--dur-state\) var\(--ease-toggle\);")
        self.assertNotRegex(block[block.index(".modes.seg.glide::before"):].split("}", 1)[0], r"\b(width|left|margin|padding) *:[^;]*\d+m?s|transition:[^;]*\b(width|left|top|height)\b")
        self.assertRegex(block, r"\.sec-ctl, \.rbar-hint \{ animation: m-in var\(--dur-state\) var\(--ease-enter\) 1; \}")
        self.assertNotRegex(CSS.replace(block, ""), r"modes\.seg\.glide|\.rbar-hint \{ animation")
        tg = (ROOT / "src/clark/page/src/edit/Toggle.jsx").read_text(encoding="utf-8")
        self.assertRegex(tg, r'class=\{pill \? "modes seg glide"')
        self.assertRegex(tg, r'setProperty\("--tx"')
        self.assertRegex(tg, r"new ResizeObserver\(")
        self.assertRegex(tg, r"disconnect\(\)")
        self.assertNotRegex(tg, r"setTimeout|Date\.now")


if __name__ == "__main__":
    unittest.main()
