"""Row 1309: killers for the removal of the Choose from lists panel (messages and dead source).

Run: python3 dev/run_tests.py test_work_items_edit_1309_killers
Quick tier: no browser.
"""
import unittest

from _paths import SRC
from test_workitems_line_node import run_node

PAGE = SRC / "clark" / "page" / "src"


class RefusalWords(unittest.TestCase):
    def test_an_unknown_value_is_refused_with_the_spelling_hint_only(self):
        r = run_node("readLine('status:Bogus', defaults(), known)")
        self.assertEqual(r["problem"], '"Bogus" is not a value status can take here. Check the spelling.')

    def test_two_use_cases_of_one_title_are_refused_with_the_spelling_hint_only(self):
        r = run_node("readLine('usecase:Twin', defaults(), known)")
        self.assertEqual(r["problem"], '"Twin" is not a value usecase can take here. Check the spelling.')


class NothingLeftOfThePanel(unittest.TestCase):
    def test_no_source_names_the_panel_its_class_or_its_words(self):
        for rel in ("edit/edit.css", "edit/templates/WorkItemsList.jsx", "templates/workItemsLine.js", "templates/WorkItemsList.jsx"):
            text = (PAGE / rel).read_text(encoding="utf-8")
            for gone in ("wil-more", "wil-form-in", "data-wil-more", "Choose from lists", "<details"):
                with self.subTest(file=rel, gone=gone):
                    self.assertNotIn(gone, text)


if __name__ == "__main__":
    unittest.main()
