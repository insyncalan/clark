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

    def test_bottom_draws_one_strip_below_the_rows_and_below_show_all(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, n=3, tracker="bottom")
                self.assertEqual(p.js(STRIPS), 1, "one strip, not one above and one below")
                self.assertEqual(p.js(ORDER), "below")
                self.assertTrue(p.js("document.querySelector('.uc .ucstrip').classList.contains('ucstrip-below')"), "marked as the bottom one")
                self.assertTrue(p.js("!!(document.querySelector('[data-ucall]').compareDocumentPosition(document.querySelector('.ucstrip')) & 4)"), "after Show all")


class ShowAll(Demo):
    def test_show_all_is_there_only_when_rows_are_hidden_and_the_list_does_not_scroll(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                for view, want in (({"n": self.total - 1}, True), ({"n": self.total}, False), ({"n": "all"}, False),
                                   ({"n": 3, "scroll": True}, False), ({"n": 3, "scroll": False}, True)):
                    self.set_local(p, **view)
                    self.assertEqual(p.js(BUTTON) is not None, want, view)


class Heights(Demo):
    def test_scrolling_fixes_the_height_at_n_rows_and_all_has_none(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, n=3, scroll=True)
                self.assertEqual(p.js(ROWS), self.total, "every row is there to scroll to")
                self.assertEqual(p.js(f"getComputedStyle({LIST}).overflowY"), "auto")
                style = p.js(f"{LIST}.getAttribute('style')")
                self.assertIn("3.25rem", style, "the row height falls back to 3.25rem")
                self.assertRegex(style, r"\* 3\)", "three rows high")
                self.set_local(p, n="all", scroll=True)
                self.assertIsNone(p.js(f"{LIST}.getAttribute('style')"), "all has no height to fix")
                self.set_local(p, n=3, scroll=False)
                self.assertIsNone(p.js(f"{LIST}.getAttribute('style')"), "no scrolling, no fixed height")
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

    def test_a_published_file_draws_its_own_view_has_no_edit_parts_and_writes_no_browser_key(self):
        put_view(self, {"n": 3, "scroll": False, "tracker": "bottom"})
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            self.assertEqual(p.js(ROWS), 3, "the file's own number")
            self.assertEqual(p.js(ORDER), "below", "the file's own tracker place")
            self.assertFalse(p.js("!!document.querySelector('#ucAdd, [data-mode=edit]')"), "a file has no Edit")
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === {self.total}", "all shown in the file")
            self.assertEqual(p.js("Object.keys(localStorage).filter(k => /ucAll/.test(k)).length"), 0, "the file stores nothing of the editor's key")


if __name__ == "__main__":
    unittest.main()
