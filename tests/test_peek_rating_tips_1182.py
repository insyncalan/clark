"""Row 1182: the risk Rating chip's tip. Run: CLARK_CHROME=<path to Chrome> python3 dev/run_tests.py test_peek_rating_tips_1182.py
The page runs in headless Chrome (set CLARK_CHROME to its path).

A risk's Rating chip says "Priority from impact and likelihood" on hover and on keyboard focus (the CSS tip drawn from data-tip, as the other chips do),
and its button names the same words for a screen reader (aria-description). An issue's chip keeps its own tip.
"""
import unittest

import test_inline_edits as T
from test_inline_edits import chrome

BTN = "#peek .pk-chips [data-row=priority] button"


class RatingTips(unittest.TestCase):
    setUp = T.Live.setUp
    open_page = T.Live.open_page
    until = T.Live.until
    read = T.Live.read

    def peek(self, cdp, sid, ref):
        cdp.js(f"clarkPage.openPeek('{ref}', 'item')", sid)
        self.until(cdp, sid, f"!!document.querySelector('#peek [data-peek], #peek[data-peek=\"{ref}\"]')", "the peek drew")
        self.until(cdp, sid, "document.querySelector('#peek').getAnimations({subtree: true}).length === 0", "the slide-in has ended")

    def test_the_risk_rating_chip_has_its_tip(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.peek(cdp, sid, "TUL-007")
            self.assertEqual(cdp.js(f"document.querySelector('{BTN}').dataset.tip", sid), "Priority from impact and likelihood")
            self.assertEqual(cdp.js(f"document.querySelector('{BTN}').getAttribute('aria-description')", sid), "Priority from impact and likelihood", "a screen reader hears it")

    def test_the_issue_rating_chip_keeps_its_tip(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.peek(cdp, sid, "TUL-010")
            self.assertRegex(cdp.js(f"document.querySelector('{BTN}').dataset.tip", sid), r"^(Red|Amber|Green) rating, set from impact and likelihood$")
            self.assertEqual(cdp.js(f"document.querySelector('{BTN}').getAttribute('aria-description')", sid), cdp.js(f"document.querySelector('{BTN}').dataset.tip", sid))


if __name__ == "__main__":
    unittest.main()
