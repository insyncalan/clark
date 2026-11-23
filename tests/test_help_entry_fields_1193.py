"""Row 1193 AP1-AP3 and AP5: the Help entry title, label, opening page and position, and the generic 'Work items list' line of the Help reference stays unchanged (pinned by text, not by line number)."""
import json
import unittest

from _paths import ROOT

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
WORK_ITEMS_LINE = "Live rows from Work items, chosen by a filter: open actions due soon, red risks, decisions needed."
ENTRY_ID = "the-three-starting-lists"


def _tasks():
    return json.loads(HELP.read_text(encoding="utf-8"))["howto"]["tasks"]


def _entry_index(tasks):
    return [t["id"] for t in tasks].index(ENTRY_ID)


def _rows(node):
    if isinstance(node, list):
        if len(node) >= 2 and node[0] == "Work items list" and isinstance(node[1], str):
            yield node
        for item in node:
            yield from _rows(item)
    elif isinstance(node, dict):
        for item in node.values():
            yield from _rows(item)


class HelpEntryFields(unittest.TestCase):
    def test_the_entry_title_is_pinned(self):
        tasks = _tasks()
        self.assertEqual(tasks[_entry_index(tasks)]["t"], "The three lists a new Dashboard starts with")

    def test_the_entry_label_is_dashboard(self):
        tasks = _tasks()
        entry = tasks[_entry_index(tasks)]
        self.assertEqual(entry["w"], "Dashboard")
        self.assertEqual(entry["go"], "dashboard")

    def test_the_entry_follows_add_a_section_from_a_template(self):
        tasks = _tasks()
        i = _entry_index(tasks)
        prev = tasks[i - 1]
        self.assertEqual(prev["t"], "Add a section from a template")
        self.assertEqual(prev["g"], "The report")
        self.assertEqual(tasks[i]["g"], "The report")

    def test_the_generic_work_items_line_is_unchanged(self):
        raw = HELP.read_text(encoding="utf-8")
        rows = list(_rows(json.loads(raw)["reference"]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], WORK_ITEMS_LINE)
        self.assertEqual(raw.count('"' + WORK_ITEMS_LINE + '"'), 1)


if __name__ == "__main__":
    unittest.main()
