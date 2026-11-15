"""Item 627: the 1.1 hand-check sheet names every v1.1 row and the Windows lines; the docs call Windows the Docker route.

Run: python3 dev/run_tests.py test_docs_windows_route
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V11_IDS = [623, 624, 625, 626, 627, 629, 630, 631, 632, 633, 634, 635, 636, 637, 638]  # plan rows labelled v1.1
# Items 510, 511, 512 and 1026 are not rows of the Windows release, so they have no row on the sheet
# and are left out of this list on purpose.


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class Windows(unittest.TestCase):
    def setUp(self):
        self.sheet = read("dev/handchecks/1.1.0-sheet.md")

    def test_the_sheet_names_every_v11_row(self):
        ids = set(int(m) for m in re.findall(r"^\| (\d{3}) \|", self.sheet, re.M))
        self.assertEqual(sorted(set(V11_IDS) - ids), [], "rows missing from the sheet")
        self.assertEqual(sorted(ids - set(V11_IDS)), [], "rows on the sheet that are not v1.1")

    def test_the_sheet_has_the_windows_lines(self):
        for word in ("PowerShell", "Command Prompt", "OneDrive", "restart", "backup"):
            self.assertIn(word, self.sheet)

    def test_every_hand_check_reference_exists(self):
        lines = set(re.findall(r"^\| (627\.\d+) \|", self.sheet, re.M))
        for ref in re.findall(r"\b627\.\d+\b", self.sheet.split("## Rows of v1.1")[1]):
            self.assertIn(ref, lines)

    def test_the_sheet_holds_only_the_scoped_windows_lines(self):
        lines = re.findall(r"^\| (627\.\d+) \|", self.sheet, re.M)
        self.assertEqual(lines, ["627.%d" % n for n in range(1, 7)])  # the 633 lines have their own test

    def test_the_old_sheet_does_not_dismiss_windows(self):
        self.assertNotIn("Windows and Linux downloads. Do not check them", read("dev/handchecks/0.2.0-sheet.md"))

    def test_the_docs_name_windows_as_the_docker_route(self):
        for rel in ("dev/RELEASING.md", "docs/testing-on-linux.md", "docs/handoff/packaging-57.md",
                    "docs/handoff/portability-and-sharing.md"):
            text = read(rel)
            self.assertRegex(text, r"Windows[^\n]*Docker route|Docker route[^\n]*Windows", rel)

    def test_the_windows_release_order_is_not_circular(self):
        text = read("dev/RELEASING.md")
        self.assertNotIn("steps 5 to 12 are repeated", text)
        self.assertNotIn("steps 13 to 18 are done on a real Windows laptop", text)
        self.assertIn("Steps 10 to 12 (attach, download back, compare) are done for the Windows zip only after those lines pass", text)

    def test_lines_that_wait_on_other_rows_say_so(self):
        for line_id, row in (("627.2", 624), ("627.4", 635), ("627.6", 634)):
            line = [l for l in self.sheet.splitlines() if l.startswith("| %s |" % line_id)][0]
            self.assertIn("waits on item %d" % row, line)


if __name__ == "__main__":
    unittest.main()
