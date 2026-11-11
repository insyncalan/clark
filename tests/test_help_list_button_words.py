"""Row 1084: the layout switch names its buttons List and Board, so Help says **List** and **Board**, never **Table** (words sweep, dash-1333).

Quick tier: reads the page source and Help's JSON, starts no browser.
"""
import json
import re
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page" / "src"
HELP = (PAGE / "help" / "helpContent.json").read_text(encoding="utf-8")
FILTER_LINE = (PAGE / "components" / "FilterLine.jsx").read_text(encoding="utf-8")


class HelpNamesTheListButton(unittest.TestCase):
    def test_the_button_is_named_list(self):
        self.assertIn('"List" : "Board"', FILTER_LINE)

    def test_help_does_not_call_the_button_table(self):
        json.loads(HELP)
        bad = re.findall(r"[^.\n]*\*\*Table\*\*[^.\n]*", HELP)
        self.assertEqual(bad, [], "Help names a **Table** button; the screen says List")

    def test_help_names_list_and_board_together(self):
        self.assertGreaterEqual(len(re.findall(r"\*\*List\*\*(?: icon)?(?: and |, )\*\*Board\*\*", HELP)), 3)


if __name__ == "__main__":
    unittest.main()
