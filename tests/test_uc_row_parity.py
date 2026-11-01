"""Prototype parity A-D10: the use case summary's reference box, merged references, the download icon and the row tint.

Run: python3 dev/run_tests.py test_uc_row_parity
Same harness and fictional data as test_glance_page. Laptop widths only: 1400 and 900 px, light and dark.
"""
import unittest

from test_glance_page import Published, Setup, USER, tearDownModule  # noqa: F401
from test_server import chrome


class Reference(Setup):
    def merge(self):
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc2, {"ref": "1.3, 1.4"})

    def test_the_reference_sits_in_a_small_box_and_merged_ones_read_with_a_plus(self):
        self.merge()
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.assertEqual(p.js("[...document.querySelectorAll('.ucref')].map(e => e.textContent)"), ["1.1", "1.3 + 1.4"])
                    self.assertGreater(p.js("parseFloat(getComputedStyle(document.querySelector('.ucref')).borderTopWidth)"), 0, "a box, not plain text")

    def test_the_download_icon_is_in_view_only_and_exports_the_workbook(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-export]').length"), 1)
            self.assertIn("Excel", p.js("document.querySelector('[data-uc-export]').getAttribute('aria-label')"))
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-export] svg[data-icn=dl]').length"), 1)
            p.edit()
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-export]').length"), 0, "Edit hides the export icons")

    def test_a_row_under_the_pointer_and_an_open_row_take_a_grey_tint(self):
        with chrome() as cdp:
            p = self.show(cdp)
            bg = lambda: p.js("getComputedStyle(document.querySelector('.ucrow .ucbar')).backgroundColor")
            rest = bg()
            p.js("document.querySelector('.ucrow .ucbar').click()")
            p.until("!!document.querySelector('.ucdetail')", "opened")
            self.assertNotEqual(bg(), rest, "the open row is tinted")


class PublishedFile(Published):
    def test_the_file_has_the_box_and_merged_reference_but_no_download_icon(self):
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc2, {"ref": "1.3 and 1.4"})
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            self.assertEqual(p.js("[...document.querySelectorAll('.ucref')].map(e => e.textContent)"), ["1.1", "1.3 + 1.4"])
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-export], .uc button').length"), 0, "a published file calls no server")


if __name__ == "__main__":
    unittest.main()
