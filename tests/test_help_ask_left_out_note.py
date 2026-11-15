"""Row 1213: Help says ask names the report sections it cannot read, in the words ask uses.

Run: python3 dev/run_tests.py test_help_ask_left_out_note
"""
import json
import unittest

from _paths import ROOT, SRC  # noqa: F401  (puts src/ on the path)

from clark import ask_service

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"


def ask_bullets():
    ref = json.loads(HELP.read_text(encoding="utf-8"))["reference"]["sections"]
    sec = next(s for s in ref if s["id"] == "ask-clark")
    return [x for b in sec["b"] if b[0] == "ul" for x in b[1]]


class HelpNamesTheLeftOutNote(unittest.TestCase):
    def line(self):
        got = [x for x in ask_bullets() if x.startswith("ask reads the project as the report would show it")]
        self.assertEqual(len(got), 1, "ask clark's Help entry has one line on left-out sections")
        return got[0]

    def test_help_quotes_the_note_ask_really_shows(self):
        note = ask_service.kinds_note(["milestones"])
        for words in ("leaves out milestones", "may be missing something"):
            self.assertIn(words, note, "ask no longer says this; change the Help line to match")
            self.assertIn(words, self.line())

    def test_help_says_only_a_whole_section_is_covered(self):
        self.assertIn("a whole section", self.line())


if __name__ == "__main__":
    unittest.main()
