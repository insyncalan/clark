"""Item 1147: the coloured bars of the Use case summary sit at the right end of the tile, on the counts' line.

Run: python3 dev/run_tests.py test_uc_strip_1147
Same harness and fictional data as test_glance_page. 1400 and 900 px, light and dark. One component draws the strip, so View, Edit and a published file are checked.
"""
import unittest

from test_glance_page import Published, Setup, tearDownModule  # noqa: F401
from test_server import chrome

# The strip's box, the bars' box and the first count's box, in the page's pixels.
PROBE = """(() => {
  const s = document.querySelector('.ucstrip'), m = s.querySelector('.meter'), c = s.querySelector('.ucn') || s.querySelector('.uctotal');
  const a = s.getBoundingClientRect(), b = m.getBoundingClientRect(), n = c.getBoundingClientRect(), cs = getComputedStyle(s);
  const inner = a.right - parseFloat(cs.paddingRight);
  return { right: Math.round(inner - b.right), width: Math.round(b.width), tile: Math.round(a.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)),
           sameLine: Math.abs((b.top + b.height / 2) - (n.top + n.height / 2)) < 12, after: b.left >= n.right - 1, bars: m.querySelectorAll('i').length };
})()"""


class Bars(Setup):
    def check(self, p, width):
        got = p.js(PROBE)
        self.assertGreaterEqual(got["bars"], 2, got)
        self.assertLessEqual(abs(got["right"]), 1, f"the bars end at the right edge of the tile's content: {got}")
        self.assertTrue(got["sameLine"] and got["after"], f"on the counts' line, after them: {got}")
        if width > 900:
            self.assertLessEqual(got["width"], 280, got)
            self.assertLessEqual(got["width"], got["tile"] * 0.4 + 1, f"never over 40% of the tile: {got}")
        else:
            self.assertLessEqual(got["width"], 81, f"at 900 px the bars shrink to about 80 px: {got}")
            self.assertGreaterEqual(got["width"], 40, got)

    def test_the_bars_are_at_the_right_of_the_tile_in_view_and_edit(self):
        for width in (1400, 900):
            for dark in (False, True):
                for edit in (False, True):
                    with self.subTest(width=width, dark=dark, edit=edit), chrome() as cdp:
                        p = self.show(cdp, width, dark)
                        if edit:
                            p.edit()
                            p.until("!!document.querySelector('.ucstrip .meter')", "edit drew the strip")
                        self.check(p, width)
                        self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")


class PublishedBars(Published):
    def test_the_published_file_has_the_bars_at_the_right_too(self):
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until("!!document.querySelector('.ucstrip .meter')", "the strip")
                got = p.js(PROBE)
                self.assertLessEqual(abs(got["right"]), 1, got)
                self.assertTrue(got["sameLine"], got)


if __name__ == "__main__":
    unittest.main()
