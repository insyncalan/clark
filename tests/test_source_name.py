"""Row 1077 (the owner's ruling of 10-11-2026): a Source is shown by its NAME, never by a path, everywhere the line is drawn (the live
peek through activity_read, a published file through publish). clark.source_name.source_name is the one rule: each part of the stored
words keeps only what follows its last / or \\, a stored YYYY-MM-DD reads DD-MM-YYYY, and the words are otherwise as they were.
Run: python3 dev/run_tests.py test_source_name
"""
import unittest

from _paths import SRC  # noqa: F401

from clark.source_name import source_name


class Name(unittest.TestCase):
    def test_plain_words_are_as_they_were(self):
        for words in ("Added by hand in clark", "Added by ask clark", "Duplicated from ABC-A-001", "Demo data (fictional)", "People list"):
            self.assertEqual(source_name(words), words)

    def test_words_with_a_slash_that_are_not_a_path_are_as_they_were(self):
        for words in ("Steering, 01/10/2026", "<b>x</b>", "Either/or", "Added by hand in clark / checked", "A/B test notes"):
            self.assertEqual(source_name(words), words, words)

    def test_a_path_keeps_its_last_part_only(self):
        self.assertEqual(source_name("projects/HRB secret/minutes/2026-10-20 Pilot readiness review.html"), "20-10-2026 Pilot readiness review.html")
        self.assertEqual(source_name("ZQ-SOURCE-PATH/actions.xlsx"), "actions.xlsx")
        self.assertEqual(source_name("C:\\Users\\someone\\Documents\\plan.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("https://example.test/share/notes.docx"), "notes.docx")
        self.assertEqual(source_name("/Users/someone/folder/"), "folder", "a trailing separator names the folder, not nothing")

    def test_each_comma_part_is_named_on_its_own(self):
        self.assertEqual(source_name("Excel import, 2026-10-01, /Volumes/share/HRB/plan.xlsx"), "Excel import, 01-10-2026, plan.xlsx")
        self.assertEqual(source_name("Word import, 2026-11-07, team/notes.docx, under Risks"), "Word import, 07-11-2026, notes.docx, under Risks")

    def test_a_date_reads_day_first_and_digits_that_are_not_a_date_stay(self):
        self.assertEqual(source_name("Excel import, 2026-10-01, plan.xlsx"), "Excel import, 01-10-2026, plan.xlsx")
        for text in ("Ref 12345-67-89 from the PMO", "Ticket 2026-13-45 filed", "Batch 20261001 and 2026-10-1"):
            self.assertEqual(source_name(text), text, text)

    def test_nothing_or_not_text_is_nothing(self):
        for v in (None, "", "   ", 7, "/", "\\", " / , / ", "C:\\"):
            self.assertEqual(source_name(v), "", repr(v))

    def test_the_words_are_trimmed_and_hidden_characters_dropped(self):
        self.assertEqual(source_name("  Added by hand in clark \n"), "Added by hand in clark")
        self.assertEqual(source_name("plan\u0007.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("a/b\u200b.xlsx"), "b.xlsx")


if __name__ == "__main__":
    unittest.main()
