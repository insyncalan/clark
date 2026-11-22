"""Row 1205 item 15: the Help lines for Clear (folders) and Remove / Undo (brands) say when those buttons show.
Run: python3 dev/run_tests.py test_help_clear_remove_undo_1205
"""
import json
import unittest
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v)


class ClearRemoveUndoLines(unittest.TestCase):
    def test_clear_remove_undo_lines_say_when_they_show(self):
        lines = list(strings(json.loads(CONTENT.read_text(encoding="utf-8"))))
        folder = [s for s in lines if "**Local folder**" in s and "**Client folder**" in s and "**Clear**" in s]
        brand = [s for s in lines if "**Remove** on a brand" in s and "**Undo** puts back" in s]
        self.assertEqual(len(folder), 1)
        self.assertEqual(len(brand), 1)
        self.assertEqual(folder[0].count("Clear shows only when a folder is set."), 1)
        self.assertEqual(brand[0].count("Remove and Undo show only when there is something to remove or take back."), 1)


if __name__ == "__main__":
    unittest.main()
