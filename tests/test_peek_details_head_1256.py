"""Row 1256-B1 (ticket item 2e): the peek's Details header. The button is 13px at weight 700, the chevron sits LEFT of the label, and the
closed summary (workstream, milestone, Raised date, Client-visible) follows the label. Measured in a real browser at 1400 and 900 wide,
light and dark, on an action (TUL-A-002) in Edit.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_peek_details_head_1256
"""
import unittest

from _paths import ROOT

import test_peek_latest  # noqa: E402
from test_work_filters import click  # noqa: E402
from test_server import chrome, wait  # noqa: E402

REF = "TUL-A-002"
MEASURE = """(() => {
  const b = document.querySelector('[data-pk-details]'), car = b.querySelector('.pk-details-car'), t = b.querySelector('[data-pk-details-t]');
  const sum = b.querySelector('[data-pk-details-sum]'), cs = getComputedStyle(b), r = (e) => e.getBoundingClientRect();
  return { size: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight, 10), carRight: r(car).right, tLeft: r(t).left, tRight: r(t).right,
           sumLeft: sum ? r(sum).left : null, sum: sum ? sum.textContent : null, carLeft: r(car).left, bLeft: r(b).left };
})()"""


class Head(test_peek_latest.Browser):
    def measure(self, width, dark):
        with chrome() as cdp:
            sent, sid = self.load(cdp, width, REF, dark=dark)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-details]')", sid)))
            if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) == "true":
                click(cdp, sid, "[data-pk-details]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-details-sum]')", sid)))
            return cdp.js(MEASURE, sid)

    def test_header_is_13px_700_with_the_chevron_left_of_the_label(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark):
                    m = self.measure(width, dark)
                    print("measured", width, "dark" if dark else "light", m)
                    self.assertEqual(m["size"], 13)
                    self.assertEqual(m["weight"], 700)
                    self.assertLessEqual(m["carRight"], m["tLeft"], f"chevron left of the label: {m}")
                    self.assertLess(m["carLeft"] - m["bLeft"], 8, f"chevron at the left edge: {m}")

    def test_closed_summary_follows_the_label_with_the_four_parts(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                m = self.measure(width, False)
                self.assertGreaterEqual(m["sumLeft"], m["tRight"], m)
                parts = m["sum"].split(" · ")
                self.assertEqual(len(parts), 4, m["sum"])
                self.assertTrue(parts[2].startswith("Raised "), m["sum"])
                self.assertEqual(parts[3], "Client visible", m["sum"])


class Source(unittest.TestCase):
    def test_chevron_comes_before_the_label_and_is_not_pushed_right(self):
        jsx = (ROOT / "src/clark/page/src/components/PeekDetails.jsx").read_text(encoding="utf-8")
        self.assertLess(jsx.index("pk-details-car"), jsx.index("pk-details-t"))
        css = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
        line = next(l for l in css.splitlines() if l.startswith(".pk-details-car"))
        self.assertNotIn("margin-left: auto", line)


if __name__ == "__main__":
    unittest.main()
