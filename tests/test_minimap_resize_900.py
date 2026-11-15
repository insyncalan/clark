"""The contents lines follow the header across 900 px: the bar is 85 px tall at 1400 and 129 px at 900, and the lines mark the section
that sits under the bar's height NOW, not the height the page was first drawn with (task from Cap, 1597 area).
Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_minimap_resize_900
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

BAR = "Math.round(document.querySelector('.top').getBoundingClientRect().height)"
LIVE = "(document.querySelector('.toc-lines i.on') || {dataset: {}}).dataset.tl"


class MinimapResize(Base):
    def test_after_a_resize_from_1400_to_900_the_marked_section_uses_the_bar_height_of_900(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400, 700)
            p.until(f"{BAR} === 85", "the bar is 85 px at 1400")
            size(cdp, p, 900, 700)
            p.until(f"{BAR} === 129", "the bar is 129 px at 900")
            # A section whose top lies between the line the old height gives and the line the new height gives: with 85 the section
            # before it is marked, with 129 this one is. The scroll is set so the top sits 15 px under the 85 px line.
            got = p.js("(function(){var vh = innerHeight, line85 = 85 + (vh - 85) * 0.3, ids = [...document.querySelectorAll('.toc-lines i')].map(i => i.dataset.tl), out = null;"
                       "for (var k = 1; k < ids.length && !out; k++) { var el = document.getElementById('sec-' + ids[k].replace(/[^A-Za-z0-9_-]/g, '-'));"
                       "if (!el) continue; var top = el.getBoundingClientRect().top + scrollY, s = Math.round(top - line85 - 15);"
                       "if (s > 0 && s + vh < document.documentElement.scrollHeight - 2) out = [ids[k], ids[k - 1], s]; } return out; })()")
            self.assertIsNotNone(got, "a section to place the line against was found")
            want, before, s = got
            p.js(f"window.scrollTo(0, {s})")
            p.until(f"{LIVE} === {want!r}", f"the section under the 129 px line ({want}) is marked, not the one before ({before})")


if __name__ == "__main__":
    unittest.main()
