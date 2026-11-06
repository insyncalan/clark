"""Row 847: below 1000 px the peek fills the window over the list; from 1000 px up the side panel (and its 560 px default) stays.

Run: python3 dev/run_tests.py test_peek_narrow

In a real browser at 900 and 1400 px, light and dark, View and Edit, on Work items and the Dashboard: the peek is as wide as the
window at 900 and 560 px at 1400; Esc closes it at 900 and the focus goes back to the row; widening it at 1400 still works.
No new words: the test reads no text.
"""
import json
import time
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_peek import key  # noqa: E402
from test_server import chrome, wait  # noqa: E402

SHELL = ROOT / "src" / "clark" / "page" / "shell.css"
WIDTH = "(() => { const p = document.querySelector('#peek'); const r = p.getBoundingClientRect(); return [r.left, r.right, r.width, document.documentElement.clientWidth]; })()"


class NarrowBrowser(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page

    def show(self, cdp, sid, view, item):
        cdp.js(f"location.hash = '#{view}&p={self.code}&item={item}'", sid)
        self.assertTrue(wait(lambda: cdp.js("(() => { const p = document.querySelector('#peek'); return !!p && p.dataset.peek === " + json.dumps(item) + "; })()", sid)), item)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)))

    def test_the_peek_fills_the_window_below_1000_px_and_keeps_its_side_panel_above(self):
        for width in (900, 1400):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                for mode in ("view", "edit"):
                    if mode == "edit":
                        self.edit_mode(cdp, sid)
                    for theme in ("light", "dark"):
                        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                        for view in ("work", "dashboard"):
                            where = f"{width} {mode} {theme} {view}"
                            with self.subTest(where):
                                cdp.js(f"document.querySelector('[data-view={view}]').click()", sid)
                                time.sleep(0.4)
                                self.show(cdp, sid, view, item)
                                left, right, w, win = cdp.js(WIDTH, sid)
                                if width < 1000:
                                    self.assertEqual((round(left), round(w)), (0, round(win)), f"{where}: the peek takes the whole window")
                                else:
                                    self.assertEqual(round(w), 560, f"{where}: the owner's 560 px default")
                                    self.assertGreater(left, 300, f"{where}: the list stays beside it")
                                self.assertEqual(round(right), round(win), where)
                                self.assertEqual(cdp.js("document.documentElement.scrollWidth - document.documentElement.clientWidth", sid) <= 1, True, where)
                                cdp.js("document.activeElement.blur()", sid)
                                key(cdp, sid, "Escape")
                                time.sleep(0.7)
                                self.assertFalse(cdp.js("!!document.querySelector('#peek')", sid), f"{where}: Esc closes it")
                cdp.js("document.documentElement.dataset.theme = 'light'", sid)

    def test_the_rule_is_in_the_stylesheet(self):
        css = SHELL.read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 999px) { .peek:not(.hpk) { width: 100% !important; } .peek:not(.hpk) .pk-edge { display: none; } }", css)      # the drag handle goes with the width it can no longer change


if __name__ == "__main__":
    unittest.main()
