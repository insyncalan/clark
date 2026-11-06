"""#912: the generated sheet-choice tests of test_excel_sheet_choice (one test per choice of ticked sheets), in a file of their own so
CI spreads them. Run: python3 dev/run_tests.py test_excel_sheet_choice_picks
"""
import json
import time
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_excel_sheet_choice import SHEET, TABLES, Sheets, add_row


class Choices(Sheets):
    """The generated tests: one for each choice of sheets."""


def choice(tables):
    """One test for one choice of sheets."""
    def test(self):
        ticked = set(tables)
        status, got = self.pick(tables)
        self.assertEqual((status, got["ok"], got["refused"]), (200, True, []), got)
        self.assertEqual({i["table"] for i in got["items"]}, ticked, "only the ticked sheets are in the check")
        before = self.counts()
        archived_before = self.archived()
        status, done = self.import_all_numbers(got)             # EVERY listed line is accepted, the "no longer in the workbook" one too
        self.assertEqual(status, 200, done)
        after = self.counts()
        for t in TABLES:
            self.assertEqual(after[t] - before[t], 1 if t in ticked else 0, f"{t}: a row is added only if the sheet was ticked")
        self.assertEqual(self.archived(), ({self.a2} if "actions" in ticked else set()) | archived_before, "archived only if Actions was ticked")
        self.assertEqual(self.description_of(self.a1) == "Draft the cut-over plan, version two", "actions" in ticked)
    return test


for name, tables in (("all", TABLES), *((t, (t,)) for t in TABLES), ("two", ("raid", "milestones"))):
    setattr(Choices, f"test_ticking_{name}_changes_only_those_sheets", choice(tables))


def broken(tables):
    """The same choice, with a row that breaks a rule in every sheet that is NOT ticked."""
    def test(self):
        wb = load_workbook(str(self.path))
        for t in TABLES:
            if t not in tables:
                ws = wb[SHEET[t]]
                add_row(ws, t, f"Broken {t}", Status="Not a status")
        wb.save(str(self.path))
        status, listed = self.sheets()
        self.assertEqual(status, 200)
        if set(TABLES) - set(tables):
            self.assertNotEqual(self.post(op="check", project="ABC", file=listed["file"], sheets=list(TABLES))[1]["refused"], [],
                                "ticking the broken sheets does refuse")
            status, listed = self.sheets()
        status, got = self.post(op="check", project="ABC", file=listed["file"], sheets=list(tables))
        self.assertEqual((status, got["refused"], got["problems"]), (200, [], []), "a broken row in an unticked sheet blocks nothing")
        self.assertEqual({i["table"] for i in got["items"]}, set(tables))
        self.assertNotIn("Broken", json.dumps(got), "and is not even named")
    return test


for name, tables in (("all", TABLES), *((t, (t,)) for t in TABLES)):
    setattr(Choices, f"test_a_broken_row_in_an_unticked_sheet_blocks_nothing_when_{name}_is_ticked", broken(tables))


if __name__ == "__main__":
    unittest.main()
