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

WORK_ITEMS_LINE = "Live rows from Work items, chosen by a filter: open actions due soon, red risks, decisions needed."


class ThreeListsHelp(unittest.TestCase):
    def test_exact_sentence_in_one_entry(self):
        data = json.loads(HELP.read_text(encoding="utf-8"))
        hits = [t for t in data["howto"]["tasks"] if SENTENCE in t["s"]]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["go"], "dashboard")
        self.assertEqual(hits[0]["s"], [SENTENCE])

    def test_title_label_and_position(self):
        tasks = json.loads(HELP.read_text(encoding="utf-8"))["howto"]["tasks"]
        ids = [t["id"] for t in tasks]
        entry = tasks[ids.index("the-three-starting-lists")]
        self.assertEqual(entry["t"], "The three lists a new Dashboard starts with")
        self.assertEqual(entry["w"], "Dashboard")
        prev = tasks[ids.index("the-three-starting-lists") - 1]
        self.assertEqual(prev["t"], "Add a section from a template")

    def test_generic_work_items_line_unchanged(self):
        """AP5: the generic Work items line (helpContent.json:1075, the Work items list row of the reference) stays unchanged."""
        data = json.loads(HELP.read_text(encoding="utf-8"))
        row = data["reference"]["sections"][4]["b"][2][2][9]
        self.assertEqual(row[0], "Work items list")
        self.assertEqual(row[1], WORK_ITEMS_LINE)
        self.assertEqual(HELP.read_text(encoding="utf-8").splitlines()[1074].strip(), '"' + WORK_ITEMS_LINE + '",')

    def test_sentence_once_in_the_file(self):
        raw = HELP.read_text(encoding="utf-8")
        self.assertEqual(raw.count(SENTENCE), 1)


if __name__ == "__main__":
    unittest.main()
