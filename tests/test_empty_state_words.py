"""#272: the use case empty-state words follow the prototype ("Not written yet."), source and built pages."""
import unittest

import _paths  # noqa: F401
from _paths import ROOT

COMPONENTS = ROOT / "src/clark/page/src/components"
PAGES = ("page.html", "page-view.html")


def read(path):
    return path.read_text(encoding="utf-8")


class EmptyStateWordsTest(unittest.TestCase):
    def test_use_case_summary_row_says_not_written_yet(self):
        self.assertIn('plain(u.standing) || "Not written yet."', read(COMPONENTS / "UseCases.jsx"))

    def test_use_case_detail_read_only_says_exactly_not_written_yet(self):
        self.assertIn('<p class="muted">Not written yet.</p>', read(COMPONENTS / "UseCaseDetail.jsx"))

    def test_use_case_detail_edit_says_how_to_add_text(self):
        self.assertIn('empty="Not written yet. Click to write."', read(COMPONENTS / "UseCaseDetail.jsx"))

    def test_old_words_are_gone_from_the_source(self):
        for name in ("UseCaseDetail.jsx", "UseCases.jsx"):
            text = read(COMPONENTS / name)
            self.assertNotIn("Nothing written yet", text, name)
            self.assertNotIn("Nothing recorded", text, name)

    def test_built_pages_carry_the_words(self):
        for name in PAGES:
            text = read(ROOT / "src/clark/page" / name)
            self.assertIn("Not written yet.", text, name)
            self.assertNotIn("Nothing written yet", text, name)
            self.assertNotIn("Nothing recorded", text, name)
        self.assertIn("Not written yet. Click to write.", read(ROOT / "src/clark/page/page.html"))

    def test_prototype_says_not_written_yet_for_use_cases(self):
        text = read(ROOT / "system/prototype/usecases.js")
        self.assertGreaterEqual(text.count('<p class="muted">Not written yet.</p>'), 2)


if __name__ == "__main__":
    unittest.main()
