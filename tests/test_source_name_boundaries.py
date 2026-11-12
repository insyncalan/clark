"""Row 1077 (PR 1349) mutation hunt: the boundaries of source_name that the first tests left open. Each case is one limit of the rule
(the extension length, the cut at 2000 characters, the 120-character ellipsis, which hidden characters go, the date edges, the
last-name-wins rule for a published list). Run: python3 dev/run_tests.py test_source_name_boundaries
"""
import unittest

from _paths import SRC  # noqa: F401

from clark.source_name import source_name


class Boundaries(unittest.TestCase):
    def test_an_extension_is_one_to_eight_letters_or_digits_after_a_stem(self):
        self.assertEqual(source_name("/x/file.abcdefgh"), "file.abcdefgh")
        self.assertEqual(source_name("/x/file.abcdefghi"), "")
        self.assertEqual(source_name("/x/file.7"), "file.7")
        self.assertEqual(source_name("/x/file."), "")
        self.assertEqual(source_name("\\\\host\\share\\file."), "")

    def test_a_web_address_with_a_backslash_after_the_host_has_a_path_so_its_file_name_shows(self):
        self.assertEqual(source_name("https://host.example\\folder\\plan.docx"), "plan.docx")
        self.assertEqual(source_name("https://host.example"), "")

    def test_a_value_a_little_over_the_cut_is_read_only_as_far_as_the_cut(self):
        """The live peek keeps the first 2000 characters: the 2001st is never read, so a file name ending there loses its last letter."""
        words = "a" * 1994 + "/" + "z.docx"
        self.assertEqual(len(words), 2001)
        self.assertEqual(source_name(words), "z.doc")
        self.assertEqual(source_name(words[:-1]), "z.doc")

    def test_a_published_value_over_the_cut_keeps_its_end(self):
        words = "/" * 5 + "q" * 2000 + "/z.docx"
        self.assertEqual(source_name(words, published=True), "z.docx")

    def test_the_ellipsis_comes_straight_after_the_last_word_with_no_space_before_it(self):
        words = "a" * 118 + " " + "b" * 10
        self.assertEqual(source_name(words), "a" * 118 + "…")
        self.assertEqual(len(source_name("a" * 130)), 120)

    def test_a_value_wrapped_in_many_layers_of_escape_is_read_through_to_the_words(self):
        self.assertEqual(source_name("Report %" + "25" * 6 + "41"), "Report A")
        self.assertEqual(source_name("%" + "25" * 6 + "2Fplan.docx"), "plan.docx")

    def test_an_unassigned_private_or_surrogate_character_is_taken_out_like_a_zero_width_one(self):
        for ch in ("͸", "", "\ud800", "\U000e0001"):
            with self.subTest(ch=hex(ord(ch))):
                self.assertEqual(source_name("a" + ch + "b"), "ab")

    def test_a_date_is_changed_only_when_it_stands_alone(self):
        for text in ("Ref 12026-10-01 x", "Ref 2026-10-011 x", "Ref 2026-10-01-5 x", "Ref -2026-10-01 x"):
            with self.subTest(text=text):
                self.assertEqual(source_name(text), text)
        self.assertEqual(source_name("Ref 2026-10-01 x"), "Ref 01-10-2026 x")

    def test_a_published_list_gives_the_last_part_that_is_a_file_name_and_never_a_bare_extension(self):
        self.assertEqual(source_name("Excel import, a.xlsx, b.docx", published=True), "b.docx")
        self.assertEqual(source_name("Excel import, a.xlsx, notes", published=True), "a.xlsx")
        self.assertEqual(source_name("Added, .docx", published=True), "")
        self.assertEqual(source_name("Imported, report.123", published=True), "")
        self.assertEqual(source_name("Imported, report.1a", published=True), "report.1a")


if __name__ == "__main__":
    unittest.main()
