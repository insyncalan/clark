"""Help accuracy: the milestone peek and client-visibility help name only what the screen has.

Run: python3 dev/run_tests.py test_help_milestone_screen_words
Quick tier: reads files, starts no browser.
"""
import json
import unittest

from _paths import ROOT

SRC = ROOT / "src" / "clark" / "page" / "src"
HELP = (SRC / "help" / "helpContent.json").read_text(encoding="utf-8")
json.loads(HELP)
PAGE = "".join(p.read_text(encoding="utf-8") for p in SRC.rglob("*.jsx") if "help" not in p.parts)


class HelpNamesWhatIsThere(unittest.TestCase):
    def test_words_the_milestone_peek_does_not_have_are_not_in_help(self):
        for word in ("Client view", "Rebaseline", "Linked work items", "the line under it says why"):
            self.assertNotIn(word, HELP, word)

    def test_the_peek_has_no_eye_and_help_does_not_say_it_has(self):
        self.assertNotIn("it is the eye at the top", HELP)
        self.assertIn("Shown to client", PAGE)

    def test_milestone_row_names_are_on_the_screen(self):
        for word in ("Agreed date", "Forecast date", "Visible to client", "Client wording"):
            self.assertIn(word, PAGE)
            self.assertIn(word, HELP)


if __name__ == "__main__":
    unittest.main()
