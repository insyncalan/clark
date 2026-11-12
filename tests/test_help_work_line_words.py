"""Help names the Work items controls as the screen does (row 1084): List and Board, Group by, and Import and Export, all at the
right end of the filter line. Quick tier: reads files, starts no browser."""
import json
import re
import unittest

from _paths import ROOT

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
TEXT = HELP.read_text(encoding="utf-8")


class WorkLineWords(unittest.TestCase):
    def test_json_is_valid(self):
        json.loads(TEXT)

    def test_the_layout_buttons_are_named_list_and_board(self):
        self.assertIsNone(re.search(r"\*\*Table\*\*", TEXT), "the screen's button is List, not Table")
        self.assertIn("**List** and **Board**", TEXT)

    def test_group_by_is_not_beside_the_saved_views(self):
        self.assertNotIn("beside the saved views", TEXT)
        self.assertNotIn("next to Table and Board", TEXT)

    def test_the_excel_icons_are_on_the_filter_line(self):
        self.assertNotIn("Export to Excel** icon in the page header, beside the add button.", TEXT)
        self.assertNotIn("Work items toolbar", TEXT)
        self.assertIn("**Export to Excel** icon at the right end of the filter line", TEXT)

    def test_the_icon_list_calls_the_layout_button_list(self):
        self.assertIn('"List",\n    "Work items as a list, in groups"', TEXT)


if __name__ == "__main__":
    unittest.main()
