"""#272: the use case empty-state words follow the prototype ("Not written yet."), source and built pages."""
import re
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
            # The old words are gone from the use case screens. Other screens (the client report's own blank, the rich text reader's default)
            # keep their own wording, so this looks for the old use case lines in the built page, not for the phrase anywhere.
            for old in ('||"Nothing written yet."', 'class:"muted",children:"Nothing written yet."', 'empty:"Nothing written yet. Click to write."'):
                self.assertNotIn(old, text, name)
        self.assertIn("Not written yet. Click to write.", read(ROOT / "src/clark/page/page.html"))

    def test_prototype_says_not_written_yet_for_use_cases(self):
        text = read(ROOT / "system/prototype/usecases.js")
        self.assertGreaterEqual(text.count('<p class="muted">Not written yet.</p>'), 2)

    def test_exact_words_come_from_the_source_and_reach_the_built_pages(self):
        # Read the words the screen shows from the source, then pin them (full stop included) in the built page.
        detail = read(COMPONENTS / "UseCaseDetail.jsx")
        row = read(COMPONENTS / "UseCases.jsx")
        read_only = re.search(r'dangerouslySetInnerHTML=\{\{ __html: safe\(u\.standing\) \}\} /> : <p class="muted">([^<]*)</p>', detail).group(1)
        edit = re.search(r'field="standing"[^\n]*? empty="([^"]*)"', detail).group(1)
        summary = re.search(r'plain\(u\.standing\) \|\| "([^"]*)"', row).group(1)
        self.assertEqual((read_only, edit, summary), ("Not written yet.", "Not written yet. Click to write.", "Not written yet."))
        page = read(ROOT / "src/clark/page/page.html")
        self.assertIn('class:"muted",children:"%s"' % read_only, page)
        self.assertIn('empty:"%s"' % edit, page)
        for name in PAGES:
            self.assertIn('||"%s"' % summary, read(ROOT / "src/clark/page" / name), name)

    def test_the_words_end_with_a_full_stop(self):
        for words in ("Not written yet.", "Not written yet. Click to write."):
            self.assertTrue(words.endswith("."))


if __name__ == "__main__":
    unittest.main()
