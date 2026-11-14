"""Issue 1173c: the Timeline's scales have the pixel spacing they promise, and the Quarter axis names Jan, Apr, Jul and Oct, each with its year.

Run: python3 dev/run_tests.py test_milestones_timeline_scale_1173c
Chrome launches at 1400 and 900 px.
"""
import unittest

from test_milestones_page import BrowserBase
from test_server import chrome, wait

HASH = "#milestones&p=TUL"
# the pixels a day between the first and the last mark, and how many days they are apart
SPACING = """(() => { const m = [...document.querySelectorAll('.mv-mk[data-mark-at]')].sort((a, b) => a.dataset.markAt < b.dataset.markAt ? -1 : 1);
  const a = m[0], b = m[m.length - 1], days = (Date.parse(b.dataset.markAt) - Date.parse(a.dataset.markAt)) / 86400000;
  return [(b.getBoundingClientRect().left - a.getBoundingClientRect().left) / days, days]; })()"""
LABELS = "[...document.querySelectorAll('.mv-strip .mv-month')].map(e => e.textContent.trim())"
EXPECT = {"week": 20, "month": 5, "quarter": 1.6}


class Scale(BrowserBase, unittest.TestCase):
    def pick(self, cdp, sid, scale):
        cdp.js(f"document.querySelector('.mv-bar [data-scale-b={scale}]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js(f"document.querySelector('.mv-bar [data-scale-b={scale}]').getAttribute('aria-current')", sid) == "true"))

    def test_each_scale_spaces_a_day_by_its_pixels_at_100_percent(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.assertEqual(cdp.js("document.querySelector('.mv-wrap').dataset.zoomPct", sid), "100", width)
                for scale, want in EXPECT.items():
                    self.pick(cdp, sid, scale)
                    got, days = cdp.js(SPACING, sid)
                    self.assertGreater(days, 30, f"{width} {scale}: the marks are far enough apart to measure")
                    # each mark's left is rounded to a whole pixel, so the error over the span is at most about 1px
                    self.assertAlmostEqual(got, want, delta=max(0.1, 1.5 / days), msg=f"{width} {scale}: pixels a day")

    def test_the_quarter_axis_names_only_jan_apr_jul_oct_and_each_has_its_year(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.pick(cdp, sid, "quarter")
                labels = cdp.js(LABELS, sid)
                self.assertGreater(len(labels), 3, f"{width}: the axis has names")
                for text in labels:
                    parts = text.split(" ")
                    self.assertEqual(len(parts), 2, f"{width}: {text!r} is a month and a year")
                    self.assertIn(parts[0], ("Jan", "Apr", "Jul", "Oct"), f"{width}: {text!r}")
                    self.assertTrue(parts[1].isdigit() and len(parts[1]) == 4, f"{width}: {text!r} carries a year")
                self.assertEqual({t.split(" ")[0] for t in labels}, {"Jan", "Apr", "Jul", "Oct"}, width)
                self.pick(cdp, sid, "month")
                month = cdp.js(LABELS, sid)
                self.assertGreater(len(month), len(labels), f"{width}: Month names more months than Quarter")


if __name__ == "__main__":
    unittest.main()
