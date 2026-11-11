"""Row 1061: the commitment word Planned 2026 in the help text, the demo data and the chip's CSS (source reads, no browser).

Run: python3 dev/run_tests.py test_planned_2026_words
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class Planned2026Words(unittest.TestCase):
    def test_help_never_names_the_old_word(self):
        text = read("src/clark/page/src/help/helpContent.json")
        self.assertNotIn("candidate", text.lower())

    def test_help_names_the_three_words_in_order(self):
        text = read("src/clark/page/src/help/helpContent.json")
        self.assertIn("commitment: Planned 2026, Committed or Planned 2027", text)
        self.assertIn("Commitment column that reads Planned 2026, Committed or Planned 2027", text)

    def test_demo_data_uses_the_new_word(self):
        text = read("dev/demo_data.py")
        self.assertNotIn("Candidate", text)
        self.assertIn('commitment="Planned 2026"', text)

    def test_chip_class_is_dashed_planned_2026(self):
        css = read("src/clark/page/shell.css")
        self.assertNotIn("cc-candidate", css)
        self.assertTrue(re.search(r"\.cchip\.cc-planned-2026\s*\{[^}]*border-style:\s*dashed", css))


if __name__ == "__main__":
    unittest.main()
