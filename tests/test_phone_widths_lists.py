"""The Use cases list, the Settings project list and the Edit use case row fit a 360 and a 420 px window.

Run: python3 dev/run_tests.py test_phone_widths_lists

In a real browser, light and dark: the page never scrolls sideways on those three views, and the section handle hint stays in the window.
No new words: the test reads no text.
"""
import json
import time
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

WIDE = "(() => { const d = document.documentElement; return d.scrollWidth - d.clientWidth; })()"
HEAD = "(() => [...document.querySelectorAll('.ucrow-ed .uchead-in')].map(e => Math.round(e.getBoundingClientRect().width)))()"


class PhoneLists(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode

    def go(self, cdp, sid, hash_, ready):
        cdp.js(f"location.hash = {json.dumps(hash_)}", sid)
        self.assertTrue(wait(lambda: cdp.js(ready, sid)), hash_)
        time.sleep(0.4)

    def test_the_three_lists_do_not_scroll_sideways_at_360_and_420(self):
        for width in (360, 420):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    where = f"{width} {theme}"
                    self.go(cdp, sid, f"#usecases&p={self.code}", "!!document.querySelector('.ucl-row')")
                    self.assertLessEqual(cdp.js(WIDE, sid), 0, "use cases " + where)
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.ucl-hd')).display", sid), "none", where)
                    self.go(cdp, sid, f"#settings&p={self.code}", "!!document.querySelector('#projects-table td.acts')")
                    self.assertLessEqual(cdp.js("(() => Math.max(...[...document.querySelectorAll('#projects-table td.acts .btn')].map(b => b.getBoundingClientRect().right)) - document.documentElement.clientWidth)()", sid), 0, "project buttons " + where)
                self.edit_mode(cdp, sid)
                cdp.js("document.querySelector('[data-view=dashboard]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ucrow-ed .uchead-in')", sid)))
                for w in cdp.js(HEAD, sid):
                    self.assertGreaterEqual(w, 150, f"headline width {width}")
                for e in cdp.js("[...document.querySelectorAll('.ucrow-ed .ucsteps, .sec-hint')].map(e => e.getBoundingClientRect().right - document.documentElement.clientWidth)", sid):
                    self.assertLessEqual(e, 0, f"past the window {width}")


if __name__ == "__main__":
    unittest.main()
