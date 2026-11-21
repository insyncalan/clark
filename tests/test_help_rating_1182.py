"""Row 1182: the Help lines for a risk's or issue's Rating chip (src/clark/page/src/help/helpContent.json).

Run: python3 dev/run_tests.py test_help_rating_1182
Quick tier: reads the JSON only, no browser.
"""
import unittest

from _paths import SRC

HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"

GONE = [
    "A risk’s or issue’s status menu also sets its colour (Red, Amber or Green), which sets its priority.",
    "Its colour from its priority: Urgent or High red, Medium amber, Low green",
    "A risk or issue’s colour follows its priority, which is set from impact and likelihood. Priorities are Urgent, High, Medium and Low.",
    "the state’s colour, the priority’s, and the date’s",
]
PRESENT = [
    "For a risk or issue the chip is **Rating**: click it and pick impact and likelihood on the grid. One click sets both and gives the colour.",
    "Its colour from its rating: Urgent or High red, Medium amber, Low green",
    "A risk or issue’s colour follows its rating, which is set from impact and likelihood. Ratings are Urgent, High, Medium and Low.",
    "**The title**, then the chips **Status**, **Priority** (a risk or issue says **Rating**), **Owner** and **Due**, each in colour.",   # row 1205 item 10, approved words (NEW-WORDS.md lines 1756 and 1759), replaces the longer sentence
]


class HelpRating1182(unittest.TestCase):
    def setUp(self):
        self.text = HELP.read_text(encoding="utf-8")

    def test_old_sentences_gone(self):
        for s in GONE:
            self.assertNotIn(s, self.text)

    def test_new_sentences_present(self):
        for s in PRESENT:
            self.assertEqual(self.text.count(s), 1, s)


if __name__ == "__main__":
    unittest.main()
