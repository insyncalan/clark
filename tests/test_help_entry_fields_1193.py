"""Row 1193 AP5: the generic 'Work items list' line of the Help reference stays unchanged (pinned by text, not by line number)."""
import json
import unittest

from _paths import ROOT

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
WORK_ITEMS_LINE = "Live rows from Work items, chosen by a filter: open actions due soon, red risks, decisions needed."


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
    def test_the_generic_work_items_line_is_unchanged(self):
        raw = HELP.read_text(encoding="utf-8")
        rows = list(_rows(json.loads(raw)["reference"]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], WORK_ITEMS_LINE)
        self.assertEqual(raw.count('"' + WORK_ITEMS_LINE + '"'), 1)


if __name__ == "__main__":
    unittest.main()
