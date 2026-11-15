"""Help names the Work items controls where the page now has them (rows 1084 and 1067): List and Board (not Table and Board),
the icons at the right end of the filter line (not beside the saved views or in the page header). Quick tier: reads files."""
import unittest

from _help_shown import RAW
from _paths import ROOT

TEXT = (ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8")
LAYOUT = (ROOT / "src" / "clark" / "page" / "src" / "components" / "FilterLine.jsx").read_text(encoding="utf-8")


class WorkIconsHelp(unittest.TestCase):
    def test_page_calls_the_switch_list(self):
        self.assertIn('"List" : "Board"', LAYOUT)

    def test_no_table_icon_name(self):
        for bad in ("**Table** and **Board**", "next to Table and Board", "with the **Table** and **Board** icons"):
            self.assertNotIn(bad, TEXT, bad)

    def test_icons_are_on_the_filter_line(self):
        for bad in ("beside the saved views (the icon", "icon in the page header, beside the add button", "icon in the page header, ringed"):
            self.assertNotIn(bad, TEXT, bad)
        self.assertIn("**List** and **Board**", TEXT)
        self.assertNotIn("filter line", TEXT.split('"id": "send-the-workbook-out"')[1][:600])      # Export and Import moved to Settings, Data: the guide names the profile circle and Settings


if __name__ == "__main__":
    unittest.main()
