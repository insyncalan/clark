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

    def test_a_line_checks_the_data_folder_when_userprofile_is_not_set(self):
        """item 629: compose.windows.yaml defaults the data folder from USERPROFILE; with it unset the default reads /clark-data. The
        yaml is not changed untested, so a Windows tester checks it by hand on this sheet."""
        line = next((l for l in self.check_lines() if "USERPROFILE" in l), "")
        self.assertIn("/clark-data", line)
        self.assertIn("(#629)", line)

    def test_the_sheet_keeps_every_windows_check_line(self):
        self.assertGreaterEqual(len(self.check_lines()), 12, "a Windows check line was deleted from the 1.1.0 sheet")

    def test_a_docker_file_the_sheet_names_exists_or_its_line_says_which_item_adds_it(self):
        """item 627: lines 16 and 7 name compose files that other pull requests add. Until those merge, the line must say so and name the item;
        a line naming a file that is absent and not explained would send a tester to a file that is not there."""
        for l in self.check_lines():
            for name in set(re.findall(r"docker/[\w.-]+", l)):
                if (ROOT / name).exists():
                    continue
                self.assertRegex(l, r"item \d{3}.*merged", f"{name} is not in the tree and the line does not say which item adds it")

    def test_the_backup_line_tags_every_item_it_depends_on(self):
        line = next(l for l in self.check_lines() if "compose.copy.yaml" in l)
        for n in ("634", "629"):
            self.assertIn(f"#{n}", line)

    def test_the_0_2_0_sheet_no_longer_says_do_not_check_windows(self):
        old = (ROOT / "dev" / "handchecks" / "0.2.0-sheet.md").read_text(encoding="utf-8")
        self.assertNotIn("Windows and Linux downloads. Do not check them", old)


if __name__ == "__main__":
    unittest.main()
