"""A-D3 in a real browser: each Dashboard section is a card with a square before its heading, in all four section styles.

Run: python3 dev/run_tests.py test_section_card_look_page
Same set-up as test_glance_page (a real server over a temporary store, fictional data). Laptop widths only: 1400 and 900 px, light
and dark. The published file is opened from file:// and follows the same shared CSS.
"""
import unittest

import test_glance_page as g
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

SQUARE = ("(() => { const h = document.querySelector('.secs > .sec .sec-head'); const s = getComputedStyle(h, '::before');"
          " return [s.width, s.height, s.backgroundColor, getComputedStyle(h.closest('.sec')).borderTopWidth,"
          " getComputedStyle(h.closest('.sec')).borderTopLeftRadius, getComputedStyle(h.closest('.sec')).backgroundColor,"
          " getComputedStyle(document.documentElement).getPropertyValue('--brand-blue').trim()]; })()")


class Cards(g.Setup):
    def test_every_section_is_a_card_with_one_square_in_each_style(self):
        for width, dark in ((1400, False), (900, False), (1400, True)):
            with chrome() as cdp:
                p = self.show(cdp, width=width, dark=dark)
                for style in ("slim", "roomy", "grey", "card"):
                    p.js(f"document.documentElement.dataset.secstyle = '{style}'")
                    w, h, bg, border, radius, sec_bg, _ = p.js(SQUARE)
                    self.assertEqual((w, h), ("10px", "10px"), f"{style} {width}: the square is drawn")
                    self.assertNotEqual(bg, "rgba(0, 0, 0, 0)", style)
                    if style == "card":
                        self.assertEqual(sec_bg, "rgba(0, 0, 0, 0)", "One card: the sections are flat")
                    else:
                        self.assertEqual(border, "1px", f"{style}: a card has one border")
                        self.assertNotEqual(radius, "0px", style)
                p.js("document.documentElement.dataset.secstyle = 'slim'")
                gap = p.js("parseFloat(getComputedStyle(document.querySelector('.secs')).rowGap)")
                self.assertLessEqual(gap, 16, "a slim gap between cards")
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"no sideways scroll at {width}")


class PublishedCards(g.Setup):
    publish = g.Published.publish          # the finished file, written the way test_glance_page writes it
    draw = g.Published.draw

    def test_the_published_file_draws_the_same_cards(self):
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            w, h, bg, border, radius, _, _ = p.js(SQUARE)
            self.assertEqual((w, h, border), ("10px", "10px", "1px"))


if __name__ == "__main__":
    unittest.main()
