"""Item 627: the docs call Windows the Docker route and the Windows release order is not circular.

Run: python3 dev/run_tests.py test_docs_windows_route
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class Windows(unittest.TestCase):
    def test_the_sheet_names_the_windows_route_rows_it_checks(self):
        sheet = read("dev/handchecks/1.1.0-sheet.md")
        for n in (627, 633):
            self.assertRegex(sheet, r"\b%d\b" % n, "row %d is not named on the 1.1.0 sheet" % n)

    def test_the_633_lines_are_whole_and_the_row_table_points_at_them(self):
        sheet = read("dev/handchecks/1.1.0-sheet.md")
        lines = re.findall(r"^\| (633\.\d+) \|", sheet, re.M)
        self.assertEqual(lines, ["633.%d" % n for n in range(1, 7)])
        self.assertRegex(sheet, r"(?m)^\| 633 \| Updating on Docker \| 633\.1 to 633\.6 \|")

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


if __name__ == "__main__":
    unittest.main()
