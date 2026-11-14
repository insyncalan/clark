"""The 1.1.0 Windows hand-check sheet names every Windows item id (item 627).

Run: python3 dev/run_tests.py test_v110_sheet
"""
import re
import unittest

from _paths import ROOT

SHEET = ROOT / "dev" / "handchecks" / "1.1.0-sheet.md"

# The v1.1 items about Windows, from the plan's v1.1 list (item 627 is this sheet itself).
WINDOWS_ITEMS = ["623", "624", "625", "626", "627", "629", "630", "634", "635", "636", "638"]

# What the issue says the Windows lines cover.
TOPICS = ["extract", "PowerShell", "Command Prompt", "OneDrive", "restart", "backup",
          "Edge", "Chrome", "offline", "LAN", "Dubai"]


class WindowsSheet(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SHEET.exists(), "dev/handchecks/1.1.0-sheet.md is missing")
        self.text = SHEET.read_text(encoding="utf-8")

    def test_the_sheet_names_every_windows_item_id(self):
        for n in WINDOWS_ITEMS:
            self.assertRegex(self.text, rf"#{n}\b", f"item {n} is not named on the 1.1.0 sheet")

    def test_the_sheet_covers_every_topic_the_issue_lists(self):
        for t in TOPICS:
            self.assertIn(t.lower(), self.text.lower(), f"no Windows line about: {t}")

    def test_each_check_line_names_an_item_id(self):
        lines = [l for l in self.text.splitlines() if l.startswith("- [ ]")]
        self.assertGreaterEqual(len(lines), len(TOPICS))
        for l in lines:
            self.assertRegex(l, r"#\d{3}\b", f"check line without an item id: {l[:60]}")

    def test_the_0_2_0_sheet_no_longer_says_do_not_check_windows(self):
        old = (ROOT / "dev" / "handchecks" / "0.2.0-sheet.md").read_text(encoding="utf-8")
        self.assertNotIn("Windows and Linux downloads. Do not check them", old)


if __name__ == "__main__":
    unittest.main()
