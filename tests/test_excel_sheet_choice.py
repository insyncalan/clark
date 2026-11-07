"""#655: Excel import lets the person choose which sheets to import. Run: python3 dev/run_tests.py test_excel_sheet_choice

The server is what keeps an unticked sheet safe, so it is tested here and not through the page: POST /api/excel-import op "sheets" lists
the sheets a workbook has with their row counts, and op "check" with `sheets` reads only those. For each choice (all five, each one alone,
and a workbook that lacks a sheet) an unticked sheet is not read (a row that breaks a rule in it blocks nothing, even one far too big),
adds, updates and archives nothing, and says nothing; a sheet that is ticked is checked and applied as before.
(#912: the Listing tests are in test_excel_sheet_listing, the Followups in test_excel_sheet_followups.)
"""
import json
import time
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_excel_route import encoded
from _sheet_choice_base import *  # noqa: F401,F403
from _sheet_choice_base import Cached, Sheets, TABLES, SHEET, add_row
from clark import excel_import, excel_route


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


class Dangerous(Sheets):
    def test_an_unticked_sheet_with_an_empty_workbook_side_is_never_archived(self):
        """The 'not in the workbook' archive: the Actions sheet is emptied; unticked, nothing in clark is offered for archiving."""
        wb = load_workbook(str(self.path))
        wb["Actions"].delete_rows(2, wb["Actions"].max_row)
        wb.save(str(self.path))
        status, got = self.pick(["milestones"])
        self.assertEqual([i["table"] for i in got["items"]], ["milestones"])
        self.assertEqual(got["counts"]["removed"], 0)
        self.assertEqual(self.post(op="apply", project="ABC", plan=got["plan"], accept=[1], confirm=True)[0], 200)
        self.assertEqual(self.archived(), set())
        status, got = self.pick(["actions"])
        self.assertEqual(got["counts"]["removed"], 2, "ticked, the same sheet does offer them")

    def test_a_sheet_that_is_ticked_but_not_in_the_file_reads_nothing(self):
        wb = load_workbook(str(self.path))
        del wb["Decisions"]
        wb.save(str(self.path))
        status, got = self.pick(["decisions"])
        self.assertEqual((status, got["items"]), (200, []))
        self.assertEqual(self.archived(), set())
        status, got = self.pick(["actions", "decisions"])
        self.assertEqual({i["table"] for i in got["items"]}, {"actions"})

    def test_an_oversize_unticked_sheet_is_not_read_and_a_ticked_one_is_refused_in_words(self):
        wb = load_workbook(str(self.path))
        wb["Use cases"].cell(excel_import.MAX_SHEET_ROWS + 50, 1).value = "far off"
        wb.save(str(self.path))
        status, got = self.pick(["actions"])
        self.assertEqual((status, got["ok"], {i["table"] for i in got["items"]}), (200, True, {"actions"}))
        status, listed = self.sheets()
        self.assertEqual(status, 200, "listing counts it without reading it all")
        status, got = self.post(op="check", project="ABC", file=listed["file"], sheets=["use_cases"])
        self.assertEqual(status, 400)
        self.assertIn("Nothing was changed.", got["message"])

    def test_a_partial_import_does_not_mark_the_whole_file_as_imported(self):
        status, got = self.pick(["actions"])
        self.assertEqual(self.post(op="apply", project="ABC", plan=got["plan"], accept="all", confirm=True)[0], 200)
        status, listed = self.sheets()
        status, got = self.post(op="check", project="ABC", file=listed["file"], sheets=["milestones"])
        self.assertEqual((status, got["already_imported"], got["counts"]["new"]), (200, False, 1), "the other sheets can still be imported")

    def test_importing_the_other_sheets_afterwards_makes_nothing_twice(self):
        status, got = self.pick(["actions"])
        self.assertEqual(self.post(op="apply", project="ABC", plan=got["plan"], accept="all", confirm=True)[0], 200)
        n = self.counts()
        status, got = self.pick(["actions", "raid"])
        self.assertEqual([i["table"] for i in got["items"] if i["kind"] == "new"], ["raid"], "the action row made already is not made again")
        self.assertEqual(self.counts(), n)


class Speed(Sheets):
    def test_an_unticked_big_sheet_costs_nothing_to_check(self):
        wb = load_workbook(str(self.path))
        ws = wb["Milestones"]
        for n in range(900):
            add_row(ws, "milestones", f"Milestone number {n}")
        wb.save(str(self.path))
        _, listed = self.sheets()
        t = time.perf_counter()
        _, small = self.post(op="check", project="ABC", file=listed["file"], sheets=["use_cases"])
        quick = time.perf_counter() - t
        self.assertEqual({i["table"] for i in small["items"]}, {"use_cases"})
        _, listed = self.sheets()
        t = time.perf_counter()
        _, big = self.post(op="check", project="ABC", file=listed["file"], sheets=["milestones"])
        slow = time.perf_counter() - t
        self.assertEqual(big["counts"]["new"], 901)
        self.assertLess(quick, slow)


if __name__ == "__main__":
    unittest.main()
