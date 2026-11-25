"""Row 1289 AP4 (the Help peek half): below 1000 px the item and milestone peeks are full width, but the Help peek (.hpk) keeps its own width
var(--hpk-w), 380px (shell.css :377, :1202; the full-width rule at :741 is .peek:not(.hpk)). Measured in a real browser at 1400 and 900, light and dark:
the open Help peek is 380 px wide, flush right, and not full width.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_help_peek_width_1289.py
"""
import unittest

import test_help_peek as base
from test_server import chrome

MEASURE = """(function () {
  var e = document.querySelector('#help-peek'), b = e.getBoundingClientRect();
  return { w: b.width, right: b.right, vw: document.documentElement.clientWidth, token: getComputedStyle(document.documentElement).getPropertyValue('--hpk-w').trim(),
           width: getComputedStyle(e).width, hpk: e.classList.contains('hpk'), peek: e.classList.contains('peek') };
})()"""


class HelpWidth(base.Base):
    page, q = base.Peek.page, base.Peek.q              # the peek tests' own helpers, none of their tests

    def setUp(self):
        super().setUp()
        self.stub = base.Stub()
        self.s.httpd.ask = self.stub

    def test_the_help_peek_is_380px_at_1400_and_900_light_and_dark(self):
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=ABC")
            p.until("!!document.querySelector('#main')", "settings")
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for scheme in ("light", "dark"):
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                    p.js("document.activeElement && document.activeElement.blur()")
                    where = f"{w} {scheme}"
                    with self.subTest(where=where):
                        self.q(p)
                        p.until("!!document.querySelector('#help-peek')", f"{where}: the peek opened")
                        p.until("document.querySelector('#help-peek').getAnimations({subtree: true}).length === 0 && document.querySelector('#help-peek').getBoundingClientRect().right === document.documentElement.clientWidth", f"{where}: the slide in has ended")
                        r = p.js(MEASURE)
                        self.assertTrue(r["hpk"] and r["peek"], f"{where}: the Help peek is a .peek.hpk: {r}")
                        self.assertEqual(r["token"], "380px", f"{where}: --hpk-w: {r}")
                        self.assertEqual(r["width"], "380px", f"{where}: computed width: {r}")
                        self.assertEqual(r["w"], 380, f"{where}: drawn width: {r}")
                        self.assertEqual(r["right"], r["vw"], f"{where}: flush right: {r}")
                        self.assertLess(r["w"], r["vw"], f"{where}: not full width (the 100% rule is for .peek:not(.hpk)): {r}")
                        p.key("Escape", code="Escape", vk=27)
                        p.until(base.GONE, f"{where}: closed")


if __name__ == "__main__":
    unittest.main()
