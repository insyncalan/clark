"""The 1.1.0 Windows hand-check sheet names every Windows item id (item 627).

Run: python3 dev/run_tests.py test_v110_sheet
"""
import re
import unittest

from _paths import ROOT

SHEET = ROOT / "dev" / "handchecks" / "1.1.0-sheet.md"

# The v1.1 items this sheet checks by hand (items 626 and 630 are the CI job and the release path, which a person cannot check on a laptop).
WINDOWS_ITEMS = ["623", "624", "625", "629", "631", "632", "634", "635", "636", "638"]

# What the issue says the Windows lines cover.
TOPICS = ["extract", "PowerShell", "Command Prompt", "OneDrive", "restart", "backup",
          "Edge", "Chrome", "offline", "LAN", "time zone", "ask clark"]

HEADINGS = ["# Hand-check sheet for clark 1.1.0, Windows (Docker route)", "## Windows checks"]


class WindowsSheet(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SHEET.exists(), "dev/handchecks/1.1.0-sheet.md is missing")
        self.text = SHEET.read_text(encoding="utf-8")

    def check_lines(self):
        return [l for l in self.text.splitlines() if l.startswith("- [ ]")]

    def test_the_sheet_names_every_windows_item_id(self):
        for n in WINDOWS_ITEMS:
            self.assertRegex(self.text, rf"#{n}\b", f"item {n} is not named on the 1.1.0 sheet")

    def test_the_sheet_covers_every_topic_the_issue_lists(self):
        for t in TOPICS:
            found = any(re.search(rf"\b{re.escape(t)}", l, re.I) for l in self.check_lines())
            self.assertTrue(found, f"no Windows check line about: {t}")

    def test_the_sheet_keeps_its_title_and_heading(self):
        lines = self.text.splitlines()
        for h in HEADINGS:
            self.assertIn(h, lines, f"heading missing: {h}")

    def test_each_check_line_names_an_item_id(self):
        lines = self.check_lines()
        self.assertGreaterEqual(len(lines), len(TOPICS))
        for l in lines:
            self.assertRegex(l, r"#\d{3}\b", f"check line without an item id: {l[:60]}")

    def test_the_0_2_0_sheet_no_longer_says_do_not_check_windows(self):
        old = (ROOT / "dev" / "handchecks" / "0.2.0-sheet.md").read_text(encoding="utf-8")
        self.assertNotIn("Windows and Linux downloads. Do not check them", old)


if __name__ == "__main__":
    unittest.main()
