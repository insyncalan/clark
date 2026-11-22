"""Tech-debt row 1342 (Feedback tag, Classic): the dialog heading and paddings as the 1298 mockup draws them.
Measured in Chrome at 1400 and 900 (values equal at both): h2 17px / 600 / margin 0 0 2px; dialog padding-bottom 14; tag padding 14 7.

Run: python3 dev/run_tests.py test_td_1342
"""
import unittest

from test_ms_timeline_classic_1315 import Base
from test_server import chrome, wait

M = """(() => { const c = (e, p) => getComputedStyle(e)[p], h = document.querySelector('.fbt-head h2'), d = document.querySelector('.fbt-dlg'), t = document.querySelector('#feedback-tag');
  return { size: c(h, 'fontSize'), weight: c(h, 'fontWeight'), margin: c(h, 'margin'), pad: c(d, 'padding'), tagPad: c(t, 'padding'), tagRadius: c(t, 'borderRadius'), dlgRadius: c(d, 'borderRadius'), w: d.getBoundingClientRect().width, top: d.getBoundingClientRect().top }; })()"""


class FeedbackTagClassic(Base, unittest.TestCase):
    def test_heading_and_paddings(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width, "#settings&p=appearance", self.serve(), ready="#feedback-tag")
                cdp.js("document.querySelector('#feedback-tag').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.fbt-dlg')", sid)))
                m = cdp.js(M, sid)
                self.assertEqual((m["size"], m["weight"], m["margin"]), ("17px", "600", "0px 0px 2px"))
                self.assertEqual(m["pad"], "16px 18px 14px 17px")   # row 1334: left 17 px plus the 1 px border is the 18 px inset of the 324 px box
                self.assertEqual(m["tagPad"], "14px 7px")
                self.assertEqual(m["tagRadius"], "10px 0px 0px 10px")
                self.assertEqual(m["dlgRadius"], "14px 0px 0px 14px")
                self.assertEqual((m["w"], m["top"]), (360, 110))


if __name__ == "__main__":
    unittest.main()
