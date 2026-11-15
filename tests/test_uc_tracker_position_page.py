"""Row 1234: the Use case summary's status tracker (the count pills and the bar) above the rows, below them or not drawn, in a real browser.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_tracker_position_page
The choice is kept in the usecases section's body as {"tracker": "top" | "bottom" | "off"}; nothing kept reads as top. Laptop widths only: 1400 and 900 px.
Fictional data (the glance page's two use cases in project ABC).
"""
import unittest

from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome
from _uc_view import put_view

STRIP = "document.querySelector('.ucstrip')"
ROWS = "document.querySelector('.ucrows')"


class Place(Setup):
    def put(self, p, value):
        put_view(self, None if value is None else {"tracker": value})
        p.reload()
        p.until("!!document.querySelector('.uc')", "the summary drew again")

    def top_of(self, p, sel):
        return p.js(f"{sel}.getBoundingClientRect().top")

    def test_nothing_kept_draws_the_tracker_above_the_rows(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.put(p, None)
                self.assertEqual(p.js("document.querySelectorAll('.ucstrip').length"), 1)
                self.assertLess(self.top_of(p, STRIP), self.top_of(p, ROWS))

    def test_top_draws_it_above_and_bottom_below_the_rows(self):
        for width in (1400, 900):
            for where in ("top", "bottom"):
                with self.subTest(width=width, where=where), chrome() as cdp:
                    p = self.show(cdp, width)
                    self.put(p, where)
                    self.assertEqual(p.js("document.querySelectorAll('.ucstrip').length"), 1, "drawn once, never twice")
                    rows_bottom = p.js(f"{ROWS}.getBoundingClientRect().bottom")
                    if where == "top":
                        self.assertLess(self.top_of(p, STRIP), self.top_of(p, ROWS))
                    else:
                        self.assertGreaterEqual(self.top_of(p, STRIP), rows_bottom - 1)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_off_draws_no_pills_and_no_bar_and_the_rows_stay(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.put(p, "off")
                self.assertEqual(p.js("document.querySelectorAll('.ucstrip, .ucn, .meter, .uctotal').length"), 0)
                self.assertGreaterEqual(p.js("document.querySelectorAll('.ucrows > .ucrow').length"), 2)

    def test_the_bottom_tracker_keeps_its_counts_and_bar(self):
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            self.put(p, "top")
            top = p.js("[document.querySelector('.uctotal').textContent, [...document.querySelectorAll('.ucn')].map(e => e.textContent), document.querySelectorAll('.meter i').length]")
            self.put(p, "bottom")
            self.assertEqual(p.js("[document.querySelector('.uctotal').textContent, [...document.querySelectorAll('.ucn')].map(e => e.textContent), document.querySelectorAll('.meter i').length]"), top)

    def test_a_bad_kept_value_reads_as_top(self):
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            self.put(p, "sideways")
            self.assertLess(self.top_of(p, STRIP), self.top_of(p, ROWS))


if __name__ == "__main__":
    unittest.main()
