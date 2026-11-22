"""Item 1390, the ticket's DoD6 and DoD7 under the names the ticket gives them, plus the Help words of the Report sheet.

Both DoD tests check behaviour that already exists (the alias tables and the Milestones columns); the longer cases are in
tests/test_excel_old_headings_1390.py, whose helper writes the old headings over a fresh export. Fictional data only.

Run: python3 dev/run_tests.py test_excel_redesign_1390
"""
import json
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from openpyxl import load_workbook

from clark import excel
from clark import excel_import as xi
from test_excel_old_headings_1390 import OLD, make_old
from test_excel_roundtrip import RoundTrip, edit, setUpModule, tearDownModule  # noqa: F401  (the hooks keep a brand logo out of every test)

HELP = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"


class OldHeadingWorkbook(RoundTrip):
    def setUp(self):
        super().setUp()
        make_old(self.path)

    def test_old_heading_workbook_still_imports(self):
        """DoD6: a workbook with every old heading is read with no change and no problem, and an edit made under an old name lands."""
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))
        edit(self.path, "Actions", self.a1, Description="Old file, reworded", **{"Client-visible": "No"})
        p = self.read()
        self.assertEqual(p.problems, [])
        after = {c.table: c.after for c in p.changes}
        self.assertEqual(after["actions"], {"description": "Old file, reworded", "client_visible": 0})


class MilestoneStateColumns(RoundTrip):
    def test_milestones_state_columns_are_gone(self):
        """DoD7: the export writes one State column and not State set by you or Shown state, and the import does not read them."""
        labels = [c.value for c in load_workbook(str(self.path))["Milestones"][1]]
        self.assertEqual(labels.count("State"), 1, labels)
        for gone in ("State set by you", "Shown state", "State chosen", "Chosen by you"):
            self.assertNotIn(gone, labels)
        before = {r["id"]: (r["state"], r["state_set"]) for r in self.s.read("milestones", "ABC")}
        make_old(self.path)      # puts the two old state columns back, with a state that differs
        p = self.read()
        self.assertEqual([c for c in p.changes if c.table == "milestones"], [])
        for old in ("State set by you", "State chosen", "Chosen by you"):
            self.assertIn(xi._key(old), xi.OLD_STATE_COLUMNS, old)
        self.assertEqual(before, {r["id"]: (r["state"], r["state_set"]) for r in self.s.read("milestones", "ABC")})


class HelpSaysReport(unittest.TestCase):
    def test_no_help_text_calls_the_first_sheet_the_cover(self):
        """The first sheet is the Report (excel.REPORT_NAME); Help says so in the approved words and never says Cover."""
        text = HELP.read_text(encoding="utf8")
        self.assertEqual(excel.REPORT_NAME, "Report")
        self.assertNotIn("Cover", text)
        self.assertIn("It opens on the Report sheet: a title band with the project name, tagged INTERNAL, and under it the same line "
                      "the Dashboard header shows (with Shown as at and the date when the report is shown as at a day).", text)
        self.assertIn("After the Report come the sheets of rows", text)
        self.assertIn("Changes made on the Report are ignored.", text)
        json.loads(text)


if __name__ == "__main__":
    unittest.main()
