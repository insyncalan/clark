"""Tech Debt 1507: on the Classic Milestones page, Calendar view, the Timeline / Calendar switch, the Earlier, Later and Today buttons and the
Week / Month / Quarter switch each have their own space: no two overlap and at least 8px lie between neighbours; a narrow toolbar wraps.
The Row 1355 values stay (the switch is at the top left; the Timeline view is not changed).

Run: python3 dev/run_tests.py test_ms_calendar_toolbar_no_overlap_td
Chrome at 1400 and 900 px, light and dark; boxes are measured in Chrome.
"""
import time
import unittest

from test_ms_timeline_classic_1315 import Base
from test_server import chrome, wait

TO_CALENDAR = "[...document.querySelectorAll('.msv-sw .msv-b')].find((b) => /calendar/i.test(b.textContent)).click()"

BOXES = """(() => { const box = (e) => { const r = e.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; },
  q = (s) => document.querySelector(s);
  return { sw: box(q('.msv-sw')), earlier: box(q('.cal-bar [data-cal="-1"]')), later: box(q('.cal-bar [data-cal="1"]')), today: box(q('.cal-bar [data-cal="0"]')),
    scale: box(q('.cal-bar .cal-sc')), title: box(q('.cal-bar .cal-t')), bar: box(q('.cal-bar')), msv: box(q('.msv')) }; })()"""


def apart(a, b, gap=8):
    """True when the boxes do not overlap and lie at least `gap` px apart (horizontally or vertically)."""
    return a["r"] + gap <= b["l"] or b["r"] + gap <= a["l"] or a["b"] + gap <= b["t"] or b["b"] + gap <= a["t"]


class Calendar(Base, unittest.TestCase):
    def calendar(self, cdp, sid):
        cdp.js(TO_CALENDAR, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-bar')", sid)))
        time.sleep(0.8)      # the view's 4px rise has finished

    def test_calendar_toolbar_items_do_not_overlap_and_keep_8px_between_them(self):
        for cdp, sid, w in self.every():
            self.calendar(cdp, sid)
            g = cdp.js(BOXES, sid)
            names = ["sw", "earlier", "later", "today", "scale"]
            for i, x in enumerate(names):
                for y in names[i + 1:]:
                    self.assertTrue(apart(g[x], g[y], 8), f"{x} and {y} overlap or are under 8px apart at {w}: {g[x]} {g[y]}")
            self.assertAlmostEqual(g["sw"]["l"], g["msv"]["l"], delta=1, msg="the switch stays at the top left (row 1355)")
            self.assertAlmostEqual(g["sw"]["t"], g["msv"]["t"], delta=1)

    def test_calendar_toolbar_wraps_at_900_without_overlap(self):
        for cdp, sid, w in self.every():
            self.calendar(cdp, sid)
            cdp.js("document.querySelector('.cal').style.maxWidth = '420px'; document.querySelector('.cal').style.width = '420px'", sid)
            time.sleep(0.3)
            g = cdp.js(BOXES, sid)
            for k in ("earlier", "later", "today", "scale", "title"):
                self.assertLessEqual(g[k]["r"], g["bar"]["r"] + 1, f"{k} is cut off at the right in a narrow bar")
            names = ["sw", "earlier", "today", "scale"]
            for i, x in enumerate(names):
                for y in names[i + 1:]:
                    self.assertTrue(apart(g[x], g[y], 8), f"{x} and {y} overlap or are under 8px apart in a narrow bar: {g[x]} {g[y]}")


if __name__ == "__main__":
    unittest.main()
