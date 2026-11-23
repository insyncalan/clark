"""Row 1287, the exception 'View removes, never hides': the Dashboard in View draws no edit component, with ONE ruled exception (M10041):
the four cells priority, due, owner and status of a list in a full-width section are pickers. These tests pin the exception by its name:
the four cells are pickers in View, a published file has none, and a description (the title cell) is never editable in the list.
Classic layer, widths 1400 and 900. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_exception   (headless Chrome; fails, never skips, without it)
"""
import unittest

import test_tpl_workitems as T
from test_view_picks_1287_more import classic
from _publish import PublishedFile
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome

CONTROLS = ".cell-pick, [data-cell], input, textarea, select, [contenteditable=true]"


class ViewRemovesNeverHidesException(PublishedFile, T.InThePage):
    def section(self, kind, title, order=1):
        with self.store.step("dashboard", T.USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": order})

    def test_view_removes_never_hides_exception_the_four_cells_are_pickers(self):
        classic(self)
        acts = self.section("actions", "Fictional actions", 1)
        risks = self.section("raid", "Fictional risks", 2)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                a = f"[data-id=\"{acts}\"] .wl-row[data-id=\"{self.a_due}\"]"
                r = f"[data-id=\"{risks}\"] .wl-row[data-id=\"{self.risk}\"]"
                p.until(f"!!document.querySelector('{a}') && !!document.querySelector('{r}')", "both lists drew")
                got = set(p.js(f"[...document.querySelectorAll('{a} .cell-pick, {r} .cell-pick')].map(e => e.dataset.cell.split(':').pop())"))
                self.assertEqual(got, {"owner", "due", "status", "priority"}, "exactly the four ruled cells are pickers in View")
                self.assertEqual(p.js("document.querySelectorAll('#report input, #report textarea, #report select, #report [contenteditable=true]').length"), 0, "every other part stays removed: no input, text area, select or editable text")

    def test_descriptions_are_not_editable_in_a_list_in_view(self):
        classic(self)
        acts = self.section("actions", "Fictional actions", 1)
        risks = self.section("raid", "Fictional risks", 2)
        wil = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"]})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('[data-id=\"{wil}\"] .wil-c-title') && !!document.querySelector('[data-id=\"{acts}\"] .c-title')", "the lists drew")
                for title in (f"[data-id=\"{acts}\"] .c-title", f"[data-id=\"{risks}\"] .c-title", f"[data-id=\"{wil}\"] .wil-c-title"):
                    self.assertGreater(p.js(f"document.querySelectorAll('{title}').length"), 0, title + " drew")
                    self.assertEqual(p.js(f"document.querySelectorAll('{title} {CONTROLS.replace(', ', ', ' + title + ' ')}').length"), 0, title + ": the description cell has no picker and no input")
                    self.assertEqual(p.js(f"[...document.querySelectorAll('{title}')].filter(e => e.isContentEditable || e.closest('[data-cell]')).length"), 0, title + ": not editable text")

    def test_a_published_file_has_no_pickers_in_any_list_and_no_editable_description(self):
        self.section("actions", "Fictional actions", 1)
        self.section("raid", "Fictional risks", 2)
        self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"]})
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width)
                p.until("document.querySelectorAll('.wl-row').length > 0 && document.querySelectorAll('.wil-table tbody tr').length > 0", "the file drew actions, risks and the work items list")
                self.assertEqual(p.js(f"document.querySelectorAll('{CONTROLS}').length"), 0, "no picker, no cell, no input in the file")
                self.assertEqual(p.js("document.querySelectorAll('.c-title [data-cell], .wil-c-title [data-cell]').length"), 0, "no editable description in the file")


if __name__ == "__main__":
    unittest.main()
