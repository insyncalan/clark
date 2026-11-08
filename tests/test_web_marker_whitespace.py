"""Row 619: a left-out row's words pasted into a kept row with different spacing (doubled spaces, a tab, a non-breaking space, a
line break) are refused by the web publish as the Word copy refuses them. Whole-value exact text and text that differs in words
still save. Fictional data only (the demo store's project ABC).
Run: python3 dev/run_tests.py test_web_marker_whitespace
"""
import unittest

from _demo import DemoStore  # noqa: F401
from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import publish_flow, to_client
from test_word_client_held_back import Setup, USER, WORD_HELD

LEFT_OUT = "Hidden supplier review of the contract"


class Pasted(Setup, unittest.TestCase):
    visible = f"Remember: {LEFT_OUT}."

    def plant(self):
        self.demo.action(description=LEFT_OUT, client_visible=0)
        (hidden,) = [r for r in self.store.read("actions", "ABC") if r["description"] == LEFT_OUT]
        self.hidden_id = hidden["id"]
        self.demo.action(description=self.visible, client_visible=1)

    def fresh(self, visible):
        self.visible = visible
        self.setUp()

    def refused(self, visible):
        self.fresh(visible)
        status, web = self.web_publish()
        self.assertEqual((status, web["action"]), (409, "refused"), web)
        self.assertTrue(web["message"].startswith(to_client.MESSAGES["held_back"].format(
            what="text that was meant to be left out")), web["message"])
        self.assertIn(publish_flow.MESSAGES["look_at"].format(items=self.hidden_id), web["message"])
        self.assertEqual((self.names(self.client), self.names(self.local)), ([], []), "the web publish wrote nothing")
        status, word = self.word_export()
        self.assertEqual((status, word["ok"]), (409, False), word)
        self.assertTrue(word["message"].startswith(WORD_HELD), word["message"])
        self.assertEqual((self.names(self.client), self.names(self.word_local)), ([], []), "the Word copy wrote nothing")

    def test_doubled_spaces(self):
        self.refused("Remember: Hidden  supplier  review of the contract.")

    def test_a_tab(self):
        self.refused("Remember: Hidden supplier\treview of the contract.")

    def test_a_non_breaking_space(self):
        self.refused("Remember: Hidden supplier review of the contract.")

    def test_other_unicode_spaces(self):
        for sp in (" ", " ", "　"):
            with self.subTest(sp=repr(sp)):
                self.refused(f"Remember: Hidden{sp}supplier review of the contract.")

    def test_a_newline(self):
        self.refused("Remember: Hidden supplier\nreview of the contract.")

    def test_letter_case_still_ignored_with_odd_spacing(self):
        self.refused("Remember: HIDDEN  SUPPLIER review of the contract.")

    def test_exact_text_in_a_kept_row_still_saves(self):
        self.fresh(f"Remember: {LEFT_OUT}.")
        status, web = self.web_publish()
        self.assertEqual(status, 200, web)

    def test_different_words_still_save(self):
        self.fresh("Remember: Hidden supplier  review of the lease.")
        status, web = self.web_publish()
        self.assertEqual(status, 200, web)
        self.fresh("Remember: Hidden supplier\treview of the lease.")
        status, web = self.web_publish()
        self.assertEqual(status, 200, web)


if __name__ == "__main__":
    unittest.main()
