"""Row 1077 mutation sweep, leftovers of source_name: conditions the first two test files left unpinned. Each case is one limit of the
rule: a Mac path made of colons, a host name with an @, a left-over "%" that is not an escape, double spaces, an escape that decodes to a
character NFKC folds, a lower-case %u escape, the "&#" left-over made of file-name characters only, and the web-address scheme characters.
Run: python3 dev/run_tests.py test_source_name_survivors
"""
import unittest

from _paths import SRC  # noqa: F401

from clark.source_name import source_name


class Survivors(unittest.TestCase):
    def test_a_colon_path_shows_only_its_file_name_but_a_title_with_a_colon_stays(self):
        self.assertEqual(source_name("Macintosh HD:Users:bob:plan.docx"), "plan.docx")
        self.assertEqual(source_name("Plan: v2"), "Plan: v2")
        self.assertEqual(source_name("Run at 12:30"), "Run at 12:30")

    def test_a_host_name_after_an_at_sign_is_no_file_name(self):
        self.assertEqual(source_name("bob@host.example"), "")
        self.assertEqual(source_name("bob@host.example", published=True), "")

    def test_a_percent_sign_that_starts_no_escape_still_makes_the_value_not_plain(self):
        self.assertEqual(source_name("50% done"), "")
        self.assertEqual(source_name("Q3%zz.docx"), "zz.docx")     # the "%" stays in the text, so only the file name after it shows

    def test_runs_of_spaces_become_one(self):
        self.assertEqual(source_name("Word  import"), "Word import")
        self.assertEqual(source_name("a   b"), "a b")

    def test_an_escape_that_decodes_to_a_wide_character_is_folded_to_its_plain_form(self):
        self.assertEqual(source_name("plan%uFF0Edocx"), "plan.docx")      # U+FF0E full-width full stop: NFKC makes it "."
        self.assertEqual(source_name("plan&#xFF0E;docx"), "plan.docx")

    def test_a_lower_case_u_escape_is_decoded_like_an_upper_case_one(self):
        self.assertEqual(source_name("plan%uff0edocx"), "plan.docx")
        self.assertEqual(source_name("%u002fplan.docx"), "plan.docx")

    def test_an_entity_left_over_made_only_of_file_name_characters_is_kept_whole_not_cut(self):
        self.assertEqual(source_name("&#plan.docx"), "&#plan.docx")   # not plain, but no character to cut at: the whole text is the name

    def test_a_web_address_with_any_scheme_character_or_no_scheme_publishes_nothing(self):
        for url in ("//host.example", "a-b://host.example", "a.b://host.example", "a+b://host.example", "a1://host.example"):
            self.assertEqual(source_name(url), "", url)
            self.assertEqual(source_name(url, published=True), "", url)


if __name__ == "__main__":
    unittest.main()
