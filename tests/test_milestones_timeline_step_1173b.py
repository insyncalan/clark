"""Item 1173b: the Timeline's Earlier and Later buttons step 30 days at the scale's pixels a day and the zoom.

At 100% that is 600 (Week), 150 (Month) and 48 (Quarter) pixels. Clicking Later moves scrollLeft by that much;
clicking Earlier moves it back.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_milestones_timeline_step_1173b
Chrome launches at 1400 and 900 px.
"""
import unittest

from test_milestones_page import BrowserBase
from test_server import chrome, wait

HASH = "#milestones&p=TUL"
LEFT = "document.querySelector('.mv-wrap').scrollLeft"
STEPS = (("week", 600), ("month", 150), ("quarter", 48))


class Step(BrowserBase, unittest.TestCase):
    def settle(self, cdp, sid):
        """Wait until scrollLeft has stopped moving (a smooth scroll is done) and return it."""
        seen = []

        def still():
            seen.append(cdp.js(LEFT, sid))
            return len(seen) >= 3 and seen[-1] == seen[-2] == seen[-3]
        self.assertTrue(wait(still), "the scroll came to rest")
        return seen[-1]

    def pick(self, cdp, sid, scale):
        cdp.js(f"document.querySelector('.mv-bar [data-scale-b={scale}]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js(f"document.querySelector('.mv-bar [data-scale-b={scale}]').getAttribute('aria-current')", sid) == "true"))

    def test_later_and_earlier_step_thirty_days_at_each_scale(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                zoom = cdp.js("+document.querySelector('.mv-wrap').dataset.zoomPct", sid) / 100
                for scale, base in STEPS:
                    where = f"{width} {scale}"
                    want = base * zoom
                    self.pick(cdp, sid, scale)
                    start = self.settle(cdp, sid)
                    room = cdp.js("document.querySelector('.mv-wrap').scrollWidth - document.querySelector('.mv-wrap').clientWidth", sid)
                    self.assertGreater(room - start, want * 2, f"{where}: room to step later")
                    self.assertGreater(start, want * 2, f"{where}: room to step earlier")
                    cdp.js("document.querySelector('.mv-bar [data-mv=\"1\"]').click()", sid)
                    self.assertTrue(wait(lambda: abs(cdp.js(LEFT, sid) - (start + want)) <= 1.5), f"{where}: Later moved by {want}")
                    later = self.settle(cdp, sid)
                    self.assertAlmostEqual(later - start, want, delta=1.5, msg=f"{where}: Later")
                    cdp.js("document.querySelector('.mv-bar [data-mv=\"-1\"]').click()", sid)
                    self.assertTrue(wait(lambda: abs(cdp.js(LEFT, sid) - start) <= 1.5), f"{where}: Earlier moved back by {want}")
                    self.assertAlmostEqual(later - self.settle(cdp, sid), want, delta=1.5, msg=f"{where}: Earlier")


if __name__ == "__main__":
    unittest.main()
