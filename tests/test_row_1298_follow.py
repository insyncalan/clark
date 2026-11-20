"""Row 1298 follow-up (Feedback tag, Classic): the mock-up's measures, pinned on computed style at 1400 and 900.
Tag 29 wide, kind chips 13.5px, added-automatically block 12.5px with 8px 10px padding, the mail link a 38px button (padding 0 22px, as Row 1319), Copy 34px tall.

Run: python3 dev/run_tests.py test_row_1298_follow
"""
import unittest

from test_ms_timeline_classic_1315 import Base
from test_server import chrome, wait

M = """(() => { const d = document.querySelector('.fbt-dlg'), c = (e) => getComputedStyle(e), b = (e) => e.getBoundingClientRect();
  const tag = document.querySelector('#feedback-tag'), mail = d.querySelector('[data-fbt-mail]'), copy = d.querySelector('[data-fbt-copy]'), add = d.querySelector('#fbt-added');
  return { tagW: b(tag).width, chip: c(d.querySelector('.fbt-kind')).fontSize, addFs: c(add).fontSize, addPad: c(add).padding,
    mailH: b(mail).height, mailMin: c(mail).minHeight, mailPad: c(mail).padding, mailDisplay: c(mail).display, copyH: b(copy).height }; })()"""


class FeedbackTagMock(Base, unittest.TestCase):
    def test_measures(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width, "#settings&p=appearance", self.serve(), ready="#feedback-tag")
                cdp.js("document.querySelector('#feedback-tag').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.fbt-dlg')", sid)))
                m = cdp.js(M, sid)
                self.assertEqual(m["tagW"], 29)
                self.assertEqual(m["chip"], "13.5px")
                self.assertEqual((m["addFs"], m["addPad"]), ("12.5px", "8px 10px"))
                self.assertEqual((m["mailH"], m["mailMin"], m["mailPad"], m["mailDisplay"]), (38, "38px", "0px 22px", "inline-flex"))
                self.assertEqual(m["copyH"], 34)


if __name__ == "__main__":
    unittest.main()
