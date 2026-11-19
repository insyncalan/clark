"""Row 1355: the Milestones page in the Classic theme has no white card round the timeline, the Timeline / Calendar switch sits at the top left on a row
of its own above the controls, and the hint says 'Drag the bottom edge to zoom'. The Cards theme keeps its switch at the top right.

Run: python3 dev/run_tests.py test_ms_switch_top_left_1355
Chrome at 1400 and 900 px, light and dark; positions and styles are computed in Chrome.
"""
import unittest

from test_ms_timeline_classic_1315 import Base
from test_server import chrome

M = """(() => { const r = (e) => e.getBoundingClientRect(), msv = document.querySelector('.msv'), cs = getComputedStyle(msv), sw = document.querySelector('.msv-sw'),
  bar = document.querySelector('.mv-bar'), a = r(sw), b = r(bar), m = r(msv);
  return { bg: cs.backgroundColor, border: cs.borderTopWidth, shadow: cs.boxShadow, pos: getComputedStyle(sw).position,
    swLeft: a.left, swTop: a.top, swBottom: a.bottom, swRight: a.right, msvLeft: m.left, msvRight: m.right, msvTop: m.top, barTop: b.top,
    hint: (bar.querySelector('.mv-zoom') || {}).textContent || '' }; })()"""


class Classic(Base, unittest.TestCase):
    def test_no_card_the_switch_top_left_above_the_controls_and_the_hint(self):
        for cdp, sid, w in self.every():
            g = cdp.js(M, sid)
            self.assertEqual(g["bg"], "rgba(0, 0, 0, 0)")
            self.assertEqual(g["border"], "0px")
            self.assertEqual(g["shadow"], "none")
            self.assertEqual(g["pos"], "static")
            self.assertAlmostEqual(g["swLeft"], g["msvLeft"], delta=1)
            self.assertAlmostEqual(g["swTop"], g["msvTop"], delta=1)
            self.assertLess(g["swRight"], g["msvRight"] - 400)
            self.assertLessEqual(g["swBottom"], g["barTop"] + 0.5, "the controls start under the switch")
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
