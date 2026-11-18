"""Row 1239 follow-up: the --topbar token follows a window resize at once.

Since the top bar may grow (a long name wraps), the page sets --topbar from the bar's real height. When the bar is exactly as tall as the
stylesheet's token (85 px at 1400, 129 px at 900), nothing is set, so a resize changes --topbar in the same frame and nothing that reads it
(the selection bar, the jump margins, the pill) sees the old width's height for a frame. Only a bar grown past its token carries an override.

Run: python3 dev/run_tests.py test_topbar_token_no_lag_1239
Browser tests: headless Chrome through the harness against a real server, fictional data, at 1400 and 900 px only.
"""
import time
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

HEIGHT = {1400: 85, 900: 129}
VAR = "parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topbar'))"
INLINE = "document.documentElement.style.getPropertyValue('--topbar')"
BAR = "document.querySelector('header.top').getBoundingClientRect().height"


class NoLag(Base):
    def test_a_bar_as_tall_as_its_token_sets_no_override(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900, 1400):
                size(cdp, p, w)
                p.until(f"Math.round({BAR}) === {HEIGHT[w]}", f"the bar is {HEIGHT[w]} px at {w}")
                p.until(f"{INLINE} === ''", f"no override at {w}")
                self.assertEqual(p.js(VAR), HEIGHT[w], f"--topbar at {w}")

    def test_a_grown_bar_carries_its_real_height_and_drops_it_when_the_name_is_short_again(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 900)
            p.until(f"Math.round({BAR}) === {HEIGHT[900]}", "the bar at 900")
            name = "document.querySelector('.top .hdr-project > span, .top .top-name')"
            old = p.js(f"{name}.textContent")
            p.js(f"{name}.textContent = {('Example Client Records Migration Programme ' * 6)!r}")
            p.until(f"Math.round({BAR}) > {HEIGHT[900]}", "the long name grew the bar")
            p.until(f"{VAR} === {BAR}", "the token follows the grown bar")
            self.assertNotEqual(p.js(INLINE), "", "a grown bar carries an override")
            p.js(f"{name}.textContent = {old!r}")
            p.until(f"Math.round({BAR}) === {HEIGHT[900]}", "the bar is back to its token")
            p.until(f"{INLINE} === ''", "the override is dropped")
            self.assertEqual(p.js(VAR), HEIGHT[900])

    def test_a_bar_a_few_pixels_taller_than_its_token_carries_its_real_height(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400)
            p.until(f"Math.round({BAR}) === {HEIGHT[1400]}", "the bar at 1400")
            p.js("document.querySelector('header.top').style.minHeight = '88px'")
            p.until(f"{VAR} === {BAR}", "the token follows a bar 3 px past its token")
            self.assertNotEqual(p.js(INLINE), "", "3 px past the token is an override")
            p.js("document.querySelector('header.top').style.minHeight = ''")
            p.until(f"{INLINE} === ''", "the override is dropped again")

    def test_a_hidden_bar_sets_no_zero_height(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400)
            p.until(f"Math.round({BAR}) === {HEIGHT[1400]}", "the bar at 1400")
            p.js("document.querySelector('header.top').style.display = 'none'")
            p.until(f"{BAR} === 0", "the bar is hidden")
            time.sleep(0.6)      # the observer has had its frames
            self.assertNotEqual(p.js(INLINE), "0px", "a hidden bar never sets a 0 px token")


if __name__ == "__main__":
    unittest.main()
