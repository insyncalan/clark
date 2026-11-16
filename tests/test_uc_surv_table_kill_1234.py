"""Row 1234: the heading row of the use case table is hidden from a screen reader, and in Edit its first heading lines up with the ref column.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_surv_table_kill_1234
Widths 1400 and 900 px only. Kills two mutants: the heading row without its hidden mark, and the Edit heading row without its left padding.
"""
import unittest

from _demo import USER
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

LEFTS = """(() => {
  const left = e => e.getBoundingClientRect().left;
  return {head: left(document.querySelector('.uc .ucheads > :first-child')),
          second: left(document.querySelector('.uc .ucheads > :nth-child(2)')),
          ref: left(document.querySelector('.uc .ucrow-ed .ucbar [data-uccol=ref]')),
          title: left(document.querySelector('.uc .ucrow-ed .ucbar [data-uccol=title]'))};
})()"""


class Heads(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3,
                                    "headline": "No login for the smallest suppliers", "source": "demo"})

    def test_the_heading_row_is_hidden_from_a_screen_reader_in_view_and_in_edit(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until("!!document.querySelector('.uc .ucheads')", "the headings drew")
                self.assertEqual(p.js("document.querySelector('.uc .ucheads').getAttribute('aria-hidden')"), "true", "View")
                p.js("document.querySelector('[data-mode=edit]').click()")
                p.until("!!document.querySelector('.uc .ucheads-ed')", "Edit headings")
                self.assertEqual(p.js("document.querySelector('.uc .ucheads').getAttribute('aria-hidden')"), "true", "Edit")

    def test_in_edit_the_first_heading_starts_where_the_ref_column_starts_and_the_second_where_the_title_starts(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.js("document.querySelector('[data-mode=edit]').click()")
                p.until("!!document.querySelector('.uc .ucrow-ed [data-uccol=ref]') && !!document.querySelector('.uc .ucheads-ed')", "Edit")
                p.until("document.getAnimations().length === 0", "the animations to end before anything is measured")
                got = p.js(LEFTS)
                self.assertAlmostEqual(got["head"], got["ref"], delta=1, msg=f"the Ref heading is over the ref column: {got}")
                self.assertAlmostEqual(got["second"], got["title"], delta=1, msg=f"the Use case heading is over the title column: {got}")


if __name__ == "__main__":
    unittest.main()
