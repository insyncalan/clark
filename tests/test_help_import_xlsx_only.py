"""#752: Help must not say the Excel import takes CSV. The import picker takes .xlsx only.

Run: python3 dev/run_tests.py test_help_import_xlsx_only
Quick tier: no browser. Reads the Help source and the held Help entries as text.
"""
import re
import unittest

from _help_shown import HELP
from _paths import ROOT

PICKER = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "ImportWorkbook.jsx").read_text(encoding="utf-8")
FILES = ["helpContent.json", "helpLater.json", "helpHeld.json"]


def sentences():
    for name in FILES:
        text = (HELP / name).read_text(encoding="utf-8")
        for line in text.splitlines():
            yield name, line


class TheImportTakesXlsxOnly(unittest.TestCase):
    def test_the_picker_takes_xlsx_and_not_csv(self):
        accept = re.search(r'accept="([^"]*)"', PICKER).group(1)
        self.assertIn(".xlsx", accept)
        self.assertNotIn(".csv", accept.lower())

    def test_no_help_line_about_choosing_or_importing_a_file_says_csv(self):
        bad = [(n, l.strip()[:90]) for n, l in sentences()
               if re.search(r"csv", l, re.I) and re.search(r"choose a file|import", l, re.I)]
        self.assertEqual(bad, [])

    def test_the_choose_a_file_step_names_the_xlsx_workbook(self):
        steps = [l for _, l in sentences() if "**Choose a file**" in l]
        self.assertTrue(steps)
        for l in steps:
            self.assertIn(".xlsx", l)


if __name__ == "__main__":
    unittest.main()
