"""Row 1234: the Use case summary's drawing rules that the first page tests left open (survivor group B).
Each test names one thing the page must do. They only read the page: the view setting is written with put_view, as the first tests do.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_view_survivors_b_1234
Laptop widths only: 1400 and 900 px.
"""
import json
import unittest

from _uc_view import put_view
from test_use_case_summary_1234 import BUTTON, ROWS, Demo, tearDownModule  # noqa: F401
from _publish import PublishedFile
from test_server import chrome

STRIPS = "document.querySelectorAll('.uc .ucstrip').length"
LIST = "document.querySelector('.ucrows')"
# where the first strip sits against the rows (compareDocumentPosition: 4 = the rows follow it)
ORDER = "(s => s ? (s.compareDocumentPosition(" + LIST + ") & 4 ? 'above' : 'below') : 'none')(document.querySelector('.uc .ucstrip'))"


class TrackerPlace(Demo):
    def test_top_draws_one_strip_above_the_rows_and_off_draws_none(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, n=3, tracker="top")
                self.assertEqual(p.js(STRIPS), 1, "one strip")
                self.assertEqual(p.js(ORDER), "above")
                self.assertFalse(p.js("!!document.querySelector('.ucstrip-below')"), "the top strip is not the bottom one")
                self.set_local(p, n=3, tracker="off")
                self.assertEqual(p.js(STRIPS), 0, "off draws no strip")

    def test_bottom_draws_one_strip_below_the_rows(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, n=3, tracker="bottom")
                self.assertEqual(p.js(STRIPS), 1, "one strip, not one above and one below")
                self.assertEqual(p.js(ORDER), "below")
                self.assertTrue(p.js("document.querySelector('.uc .ucstrip').classList.contains('ucstrip-below')"), "marked as the bottom one")
                self.assertIsNone(p.js(BUTTON), "a number is set, so there is no Show all for the strip to follow")


class ShowAll(Demo):
    def test_there_is_no_show_all_once_a_number_is_set_whether_or_not_rows_are_hidden(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                for view in ({"n": self.total - 1}, {"n": self.total}, {"n": "all"}, {"n": 3, "scroll": True}, {"n": 3, "scroll": False}):
                    self.set_local(p, **view)
                    self.assertIsNone(p.js(BUTTON), view)


class Heights(Demo):
    def test_scrolling_fixes_the_height_at_n_rows_and_all_has_none(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, n=3, scroll=True)
                self.assertEqual(p.js(ROWS), self.total, "every row is there to scroll to")
                self.assertEqual(p.js(f"getComputedStyle({LIST}).overflowY"), "auto")
                style = p.js(f"{LIST}.getAttribute('style')")
                self.assertIn("var(--ucrow-h", style, "the height is n times the measured row height (the 3.25rem is only the fallback before it is measured)")
                self.assertRegex(style, r"\* 3\)", "three rows high")
                self.set_local(p, n="all", scroll=True)
                self.assertEqual(p.js(f"{LIST}.style.maxHeight"), "", "all has no height to fix (the measured row height may stay as a variable)")
                self.set_local(p, n=3, scroll=False)
                self.assertEqual(p.js(f"{LIST}.style.maxHeight"), "", "no scrolling, no fixed height")
                self.assertEqual(p.js(f"getComputedStyle({LIST}).overflowY"), "visible")


class Pills(Demo):
    def test_only_the_statuses_in_use_get_a_count(self):
        with self.store.step("dashboard", "x") as st:
            for r in self.store.read("use_cases", "ABC"):
                st.update("use_cases", r["id"], {"status": "Flag"})
        with chrome() as cdp:
            p = self.show(cdp)
            self.set_local(p, n=3)
            self.assertEqual(p.js("[...document.querySelectorAll('.uc [data-count]')].map(e => e.dataset.count)"), ["Flag"])
            self.assertEqual(p.js("document.querySelector('.uc .meter').getAttribute('aria-label')"), f"{self.total} Flag")

    def test_one_use_case_says_the_singular(self):
        with self.store.step("dashboard", "x") as st:
            for r in self.store.read("use_cases", "ABC")[1:]:
                st.update("use_cases", r["id"], {"client_visible": 0})
        with chrome() as cdp:
            p = self.show(cdp)
            self.set_local(p, n=3)
            self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "1 use case")


class EditAndFile(Demo, PublishedFile):
    def test_view_has_no_edit_parts_and_the_empty_list_says_why(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.set_local(p, n=3)
            self.assertEqual(p.js("document.querySelectorAll('.ucrow-ed').length"), 0, "View has none of Edit's row parts")
            self.edit(p)
            self.assertEqual(p.js("document.querySelectorAll('.ucrow-ed').length"), self.total, "Edit gives every row its parts")
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("!document.querySelector('.ucrow-ed')", "back in View")
            with self.store.step("dashboard", "x") as st:
                for r in self.store.read("use_cases", "ABC"):
                    st.update("use_cases", r["id"], {"client_visible": 0})
            p.reload()
            p.until("!!document.querySelector('[data-nouc]')", "the empty line")
            self.assertEqual(p.js("document.querySelector('[data-nouc]').textContent"), "No use cases are on the dashboard.")

    def test_a_published_file_with_a_number_and_scroll_off_shows_only_those_rows_with_no_way_to_open_the_rest_and_writes_no_browser_key(self):
        put_view(self, {"n": 3, "scroll": False, "tracker": "bottom"})
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            self.assertEqual(p.js(ROWS), 3, "the file's own number")
            self.assertEqual(p.js(ORDER), "below", "the file's own tracker place")
            self.assertFalse(p.js("!!document.querySelector('[data-uc-configure], [data-mode=edit]')"), "a file has no Edit")
            self.assertIsNone(p.js(BUTTON), "ruled 16-11: a number with scroll off shows only the first n, no Show all")
            self.assertEqual(p.js(ROWS), 3, "still the file's own number")
            self.assertEqual(p.js("Object.keys(localStorage).filter(k => /ucAll/.test(k)).length"), 0, "the file stores nothing of the editor's key")


if __name__ == "__main__":
    unittest.main()
