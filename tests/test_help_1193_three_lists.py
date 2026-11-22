"""Row 1193: the Dashboard Help says how the three starting lists work, in the approved words, exactly."""
import json
import unittest

from _paths import ROOT

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
SENTENCE = (
    "A new project’s Dashboard starts with three lists: Risks and issues, Open actions and Decisions. "
    "Each is a Work items list with its filter already saved; change the filter, the columns or the number of rows in Edit. "
    "Reports made before this keep the lists they have."
)


class ThreeListsHelp(unittest.TestCase):
    def test_exact_sentence_in_one_entry(self):
        data = json.loads(HELP.read_text(encoding="utf-8"))
        hits = [t for t in data["howto"]["tasks"] if SENTENCE in t["s"]]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["go"], "dashboard")
        self.assertEqual(hits[0]["s"], [SENTENCE])

    def test_sentence_once_in_the_file(self):
        raw = HELP.read_text(encoding="utf-8")
        self.assertEqual(raw.count(SENTENCE), 1)


if __name__ == "__main__":
    unittest.main()
