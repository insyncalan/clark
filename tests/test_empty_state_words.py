"""#272: the use case empty-state words follow the prototype ("Not written yet."), in the sources and in the built pages.

Run: python3 dev/run_tests.py test_empty_state_words
The built pages are not committed (#495), so the test asks the page module for them: page.ensure_built() builds them in a
source checkout when they are missing or out of date, and the test then reads page.PAGE and page.VIEW_PAGE.
"""
import unittest

import _paths  # noqa: F401
from _paths import ROOT

from clark import page  # noqa: E402

COMPONENTS = ROOT / "src/clark/page/src/components"


def read(path):
    return path.read_text(encoding="utf-8")


class EmptyStateWordsTest(unittest.TestCase):
    def test_use_case_summary_row_says_not_written_yet(self):
        self.assertIn('plain(u.standing) || "Not written yet."', read(COMPONENTS / "UseCases.jsx"))

    def test_use_case_detail_read_only_says_exactly_not_written_yet(self):
        self.assertIn('<p class="muted">Not written yet.</p>', read(COMPONENTS / "UseCaseDetail.jsx"))

    def test_use_case_detail_edit_says_how_to_add_text(self):
        self.assertIn("empty={STANDING_PROMPT}", read(COMPONENTS / "UseCaseDetail.jsx"))
        self.assertIn('STANDING_PROMPT = "What is done, what is happening now, and what is next. Add anything that is blocked or at risk."', read(COMPONENTS / "UseCaseDetail.jsx"))

    def test_old_words_are_gone_from_the_source(self):
        for name in ("UseCaseDetail.jsx", "UseCases.jsx"):
            text = read(COMPONENTS / name)
            self.assertNotIn("Nothing written yet", text, name)
            self.assertNotIn("Nothing recorded", text, name)

    def test_built_pages_carry_the_words(self):
        page.ensure_built()
        for built in (page.PAGE, page.VIEW_PAGE):
            text = read(built)
            self.assertIn("Not written yet.", text, built.name)
            # The old words are gone from the use case screens. Other screens (the client report's own blank, the rich text
            # reader's default) keep their own wording, so this looks for the old use case lines in the built page, not for
            # the phrase anywhere.
            for old in ('||"Nothing written yet."', 'class:"muted",children:"Nothing written yet."', 'empty:"Nothing written yet. Click to write."'):
                self.assertNotIn(old, text, built.name)
        self.assertIn("What is done, what is happening now, and what is next. Add anything that is blocked or at risk.", read(page.PAGE))
        self.assertIn("Today's position, in one line", read(page.PAGE))
        for old in ("One line on where", "Where the use case stands", "Not written yet. Click to write."):
            self.assertNotIn(old, read(page.PAGE))
            self.assertNotIn(old, read(page.VIEW_PAGE))
        self.assertIn('empty={ro ? "No headline yet" : HEADLINE_PROMPT}', read(COMPONENTS / "UseCaseDetail.jsx"))   # the read-only page says it as text, not as a prompt
        self.assertIn("No headline yet", read(page.PAGE))

    def test_prototype_use_case_prompts_are_the_approved_ones(self):
        text = read(ROOT / "system/prototype/usecases.js")
        self.assertIn("Today's position, in one line", text)
        self.assertIn("What is done, what is happening now, and what is next. Add anything that is blocked or at risk.", text)
        for old in ("One line on where", "Where the use case stands"):
            self.assertNotIn(old, text)

    def test_prototype_says_not_written_yet_for_use_cases(self):
        text = read(ROOT / "system/prototype/usecases.js")
        self.assertGreaterEqual(text.count('<p class="muted">Not written yet.</p>'), 2)


if __name__ == "__main__":
    unittest.main()
