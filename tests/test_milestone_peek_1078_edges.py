"""Row 1078 (PR 1350) mutation hunt: the refusals of a milestone's rich client wording that test_milestone_peek_1078 left open.

The editor's HTML for client_message is held to the same words as the plain field always was: a hidden character is refused with
"Use plain text, with no line breaks or hidden characters." (not the internal note's sentence), a value that is not text with
"That value isn't one clark can use.", and the limit counts the words, not the markup.

Run: python3 dev/run_tests.py test_milestone_peek_1078_edges     No browser. Fictional data.
"""
import unittest

from _paths import SRC  # noqa: F401

from clark import changes, excel_client


class RichClientWording(unittest.TestCase):
    def refused(self, value):
        with self.assertRaises(changes.Refused) as e:
            changes._checked_milestone_changes({"client_message": value})
        return str(e.exception)

    def test_a_hidden_character_in_the_editors_html_is_refused_in_the_plain_fields_words(self):
        for bad in ("<p>Going​ well</p>", "<p>Going\x00 well</p>", "<p>Going‮ well</p>"):
            with self.subTest(bad=bad):
                self.assertEqual(self.refused(bad), changes.ITEM_TEXT_WORDS)

    def test_a_value_that_is_not_text_is_refused_in_the_item_value_words(self):
        for bad in (5, ["<p>x</p>"], {"a": 1}):
            with self.subTest(bad=bad):
                self.assertEqual(self.refused(bad), changes.ITEM_VALUE_WORDS)

    def test_markup_over_the_body_limit_is_refused_but_words_at_the_limit_are_kept(self):
        self.assertEqual(self.refused("<p>" + "w" * (changes.TEXT_BODY_MAX + 1) + "</p>"), changes.ITEM_VALUE_WORDS)
        ok = "<p>" + "w" * 500 + "</p>"
        self.assertEqual(changes._checked_milestone_changes({"client_message": ok}), {"client_message": ok})

    def test_a_line_break_between_tags_is_not_a_hidden_character(self):
        got = changes._checked_milestone_changes({"client_message": "<p>One</p>\n<p>Two</p>"})
        self.assertIn("One", got["client_message"])
        self.assertIn("Two", got["client_message"])


class ClientWorkbookWords(unittest.TestCase):
    def test_a_milestones_client_wording_is_the_plain_words_of_its_html_and_stands_in_for_the_description(self):
        row = {"client_message": "  <p>Going <strong>well</strong> &amp; fast</p>  ", "description": "<p>Own</p>"}
        self.assertEqual(excel_client.value_of("milestones", row, "_words"), "Going well & fast")

    def test_html_with_no_words_falls_back_to_the_description_and_blank_text_is_no_wording(self):
        self.assertEqual(excel_client.value_of("milestones", {"client_message": "<p> </p>", "description": "<p>Own</p>"}, "_words"), "Own")
        self.assertEqual(excel_client.value_of("milestones", {"client_message": "   ", "description": "<p>Own</p>"}, "_words"), "Own")
        self.assertEqual(excel_client.value_of("milestones", {"description": "<p>Own</p>"}, "_words"), "Own")


if __name__ == "__main__":
    unittest.main()
