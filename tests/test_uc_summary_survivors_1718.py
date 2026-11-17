"""Row 1234 (PR 1718): three mutants of UseCases.jsx / useCaseView.js that the tests on the PR head let through.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_summary_survivors_1718
  1. print with a set number: printing draws every use case even when the stored number is smaller (dropping `|| printing.value` shows only n).
  2. scroll on with no stored number: the list scrolls with every use case and has no Show all (dropping `!scrolls` from the button brings Show all back).
Laptop widths only: 1400 and 900 px.
"""
import unittest

from _publish import PublishedFile
from _uc_view import put_view
from test_use_case_summary_1234 import BUTTON, ROWS, Demo, tearDownModule  # noqa: F401
from test_server import chrome


class PrintAndScroll(Demo, PublishedFile):
    def test_a_published_file_with_a_number_set_prints_every_use_case_and_goes_back_to_n_afterwards(self):
        put_view(self, {"n": 3, "scroll": False})
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width)
                self.assertEqual(p.js(ROWS), 3, "on screen the file shows its n")
                p.js("window.dispatchEvent(new Event('beforeprint'))")
                p.until(f"{ROWS} === {self.total}", "a print draws every use case")
                self.assertIsNone(p.js(BUTTON), "no Show all in a print")
                p.js("window.dispatchEvent(new Event('afterprint'))")
                p.until(f"{ROWS} === 3", "after the print the file is back to n")

    def test_scroll_on_with_no_number_stored_lists_every_use_case_with_no_show_all(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, scroll=True)
                self.assertEqual(p.js(ROWS), self.total, "every use case is in the scrolling list")
                self.assertIsNone(p.js(BUTTON), "nothing is hidden, so no Show all (the default 5 does not apply while scrolling)")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.ucrows')).overflowY"), "auto")


if __name__ == "__main__":
    unittest.main()
