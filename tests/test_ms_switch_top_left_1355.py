"""Row 1355: the Milestones page in the Classic theme has no white card round the timeline, the Timeline / Calendar switch sits at the top left on one row
with the Zoom hint, which sits at the far right (space-between), and the hint says 'Drag the bottom edge to zoom'. The Cards theme keeps its switch at the top right.

Run: python3 dev/run_tests.py test_ms_switch_top_left_1355
Chrome at 1400 and 900 px, light and dark; positions and styles are computed in Chrome.
"""
import time
import unittest

from test_ms_timeline_classic_1315 import Base
from test_server import chrome

M = """(() => { const r = (e) => e.getBoundingClientRect(), msv = document.querySelector('.msv'), cs = getComputedStyle(msv), sw = document.querySelector('.msv-sw'),
  bar = document.querySelector('.mv-bar'), zm = bar.querySelector('.mv-zoom'), a = r(sw), b = r(bar), m = r(msv), z = r(zm), tr = (() => { const g = document.createRange(); g.selectNodeContents(zm); return g.getBoundingClientRect(); })(), td = r(bar.querySelector('[data-mv="0"]'));
  return { bg: cs.backgroundColor, border: cs.borderTopWidth, shadow: cs.boxShadow, pos: getComputedStyle(sw).position,
    swLeft: a.left, swTop: a.top, swBottom: a.bottom, swRight: a.right, msvLeft: m.left, msvRight: m.right, msvTop: m.top, barTop: b.top, zTop: z.top, todayTop: td.top, zBottom: z.bottom, zRight: z.right, zLeft: tr.left, tRight: tr.right,
    hint: (bar.querySelector('.mv-zoom') || {}).textContent || '' }; })()"""


class Classic(Base, unittest.TestCase):
    def test_no_card_the_switch_top_left_and_zoom_far_right_in_one_row(self):
        for cdp, sid, w in self.every():
            time.sleep(0.8)      # the view's 4px rise on a switch has finished
            g = cdp.js(M, sid)
            self.assertEqual(g["bg"], "rgba(0, 0, 0, 0)")
            self.assertEqual(g["border"], "0px")
            self.assertEqual(g["shadow"], "none")
            self.assertEqual(g["pos"], "absolute")
            self.assertAlmostEqual(g["swLeft"], g["msvLeft"], delta=1)
            self.assertAlmostEqual(g["swTop"], g["msvTop"], delta=1)
            self.assertLess(g["swRight"], g["msvRight"] - 400)
            self.assertAlmostEqual(g["swTop"], g["zTop"], delta=1, msg="View and Zoom share one row")
            self.assertAlmostEqual(g["zRight"], g["msvRight"], delta=1, msg="the Zoom row spans to the far right")
            self.assertAlmostEqual(g["tRight"], g["msvRight"], delta=1, msg="the Zoom text ends at the far right of the row")
            self.assertGreater(g["zLeft"], g["swRight"], "Zoom is right of the switch")
            self.assertLessEqual(g["swBottom"], g["todayTop"] + 0.5, "the controls row (Today) starts under the View and Zoom row")
            self.assertEqual(g["hint"], "Drag the bottom edge to zoom")


class Cards(Base, unittest.TestCase):
    THEME = None

    def test_cards_keeps_its_switch_at_the_top_right(self):
        for cdp, sid, w in self.every():
            g = cdp.js(M, sid)
            self.assertEqual(g["pos"], "absolute")
            self.assertAlmostEqual(g["swRight"], g["msvRight"] - (28 if w > 900 else 16), delta=1.5)


if __name__ == "__main__":
    unittest.main()
