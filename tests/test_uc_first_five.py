"""Row 1108: the Use case summary shows the first 5 use cases, with a quiet control for all of them and back.

Run: python3 dev/run_tests.py test_uc_first_five
Same harness and fictional data as test_glance_page (two use cases), plus five more. Laptop widths only: 1400 and 900 px, light and dark.
"""
import unittest

from test_glance_page import Published, Setup, USER, tearDownModule  # noqa: F401
from test_server import chrome

ROWS = "document.querySelectorAll('.uc .ucrow').length"
WORD = "(document.querySelector('[data-ucall]') || {}).textContent"


def more(self):
    with self.store.step("dashboard", USER) as st:
        for n in range(3, 8):
            st.create("use_cases", {"project": "ABC", "title": f"Case {n}", "status": "On track", "ref": f"1.{n}", "source": "demo"})


class Editor(Setup):
    def test_five_rows_then_all_and_back_with_the_count_and_bar_for_every_use_case(self):
        more(self)
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.assertEqual(p.js(ROWS), 5)
                    self.assertEqual(p.js(WORD), "Show all 7 use cases")
                    self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "7 use cases")
                    self.assertEqual(p.js("document.querySelectorAll('.uc .meter i').length"), 7)
                    p.js("document.querySelector('[data-ucall]').click()")
                    p.until(f"{ROWS} === 7", "all rows")
                    self.assertEqual(p.js(WORD), "Show the first 5")
                    p.js("document.querySelector('[data-ucall]').click()")
                    p.until(f"{ROWS} === 5", "back to five")

    def test_five_or_fewer_have_no_control(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('[data-ucall]').length"), 0)


class PublishedFile(Published):
    def test_the_published_page_does_the_same_and_still_has_no_button(self):
        more(self)
        with chrome() as cdp:
            p = self.draw(cdp, self.publish())
            self.assertEqual(p.js(ROWS), 5)
            self.assertEqual(p.js(WORD), "Show all 7 use cases")
            self.assertEqual(p.js("document.querySelectorAll('.uc button').length"), 0)
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === 7", "all rows")


if __name__ == "__main__":
    unittest.main()
