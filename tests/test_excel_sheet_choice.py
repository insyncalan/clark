"""#655: Excel import lets the person choose which sheets to import. Run: python3 dev/run_tests.py test_excel_sheet_choice

The server is what keeps an unticked sheet safe, so it is tested here and not through the page: POST /api/excel-import op "sheets" lists
the sheets a workbook has with their row counts, and op "check" with `sheets` reads only those. For each choice (all five, each one alone,
and a workbook that lacks a sheet) an unticked sheet is not read (a row that breaks a rule in it blocks nothing, even one far too big),
adds, updates and archives nothing, and says nothing; a sheet that is ticked is checked and applied as before.
"""
import json
import time
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_excel_route import Base, encoded
from clark import excel_import, excel_route

TABLES = excel_import.CHOICE_ORDER
SHEET = {"actions": "Actions", "raid": "Risks & Issues", "decisions": "Decisions", "milestones": "Milestones", "use_cases": "Use cases"}
TITLE = {"actions": "Description", "raid": "Description", "decisions": "Decision", "milestones": "Milestone", "use_cases": "Use case"}
EXTRA = {"raid": {"Type": "Risk"}, "decisions": {"Status": "Pending"}, "use_cases": {"Status": "On track"}}


def add_row(ws, table, text, **cells):
    head = {c.value: c.column for c in ws[1]}
    row = ws.max_row + 1
    for label, value in {TITLE[table]: text, **EXTRA.get(table, {}), **cells}.items():   # (cells may override the status)
        ws.cell(row, head[label]).value = value


class Sheets(Base):
    def setUp(self):
        super().setUp()
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == self.a2)
        ws.delete_rows(row)                                         # a2 is now "not in the workbook"
        for r in range(2, ws.max_row + 1):
            if ws.cell(r, 1).value == self.a1:
                ws.cell(r, head["Description"]).value = "Draft the cut-over plan, version two"
        for t in TABLES:
            add_row(wb[SHEET[t]], t, f"A new {t} row")
        wb.save(str(self.path))
        self.fresh = self.path.read_bytes()

    def counts(self):
        return {t: len(self.store.read(t, project="ABC")) for t in TABLES}

    def archived(self):
        return {r["id"] for r in self.store.read("actions", project="ABC") if r["archived"]}

    def sheets(self):
        return self.post(op="sheets", project="ABC", name="ABC work items.xlsx", data=encoded(self.path))

    def pick(self, tables):
        status, listed = self.sheets()
        self.assertEqual(status, 200, listed)
        return self.post(op="check", project="ABC", file=listed["file"], sheets=list(tables))

    def import_all_numbers(self, got):
        return self.post(op="apply", project="ABC", plan=got["plan"], accept=[i["n"] for i in got["items"]], confirm=True)


class Listing(Sheets):
    def test_it_lists_the_five_sheets_in_order_with_their_row_counts_and_writes_nothing(self):
        before, steps = self.counts(), self.steps()
        status, got = self.sheets()
        self.assertEqual(status, 200)
        self.assertEqual([(s["table"], s["name"]) for s in got["sheets"]], [(t, SHEET[t]) for t in TABLES])
        self.assertEqual({s["table"]: s["rows"] for s in got["sheets"]}, {"actions": 2, "raid": 1, "decisions": 1, "milestones": 2, "use_cases": 2})
        self.assertEqual((self.counts(), self.steps()), (before, steps))
        self.assertNotIn("items", got)

    def test_a_sheet_the_file_does_not_have_and_a_history_sheet_are_not_listed(self):
        wb = load_workbook(str(self.path))
        del wb["Decisions"]
        wb.create_sheet("History").append(["Anything"])
        wb.save(str(self.path))
        status, got = self.sheets()
        self.assertEqual([s["table"] for s in got["sheets"]], ["actions", "raid", "milestones", "use_cases"])

    def test_a_blank_row_is_not_counted(self):
        wb = load_workbook(str(self.path))
        wb["Decisions"].cell(wb["Decisions"].max_row + 3, 2).value = "  "
        wb.save(str(self.path))
        self.assertEqual({s["table"]: s["rows"] for s in self.sheets()[1]["sheets"]}["decisions"], 1)

    def decisions_with(self, data_rows, stray=None, stray_col=1):
        """Decisions holding exactly `data_rows` rows with something in them (rows 2 and up), and a far-off cell at row `stray` if given."""
        wb = load_workbook(str(self.path))
        ws = wb["Decisions"]
        for r in range(2, ws.max_row + 1):
            ws.cell(r, 2).value = None
        for r in range(2, data_rows + 2):
            ws.cell(r, 2).value = f"Filler {r}"
        if stray:
            ws.cell(stray, stray_col).value = "far off"
        wb.save(str(self.path))

    def decisions_rows(self):
        return {s["table"]: s["rows"] for s in self.sheets()[1]["sheets"]}["decisions"]

    def check_decisions(self):
        status, listed = self.sheets()
        self.assertEqual(status, 200, listed)
        return self.post(op="check", project="ABC", file=listed["file"], sheets=["decisions"])

    def test_the_shown_limit_is_the_checks_limit(self):
        self.assertEqual((excel_import.MAX_ROWS, excel_import.OVER_LIMIT), (2000, 2001))

    def actions_with(self, data_rows):
        """Actions holding `data_rows` rows that each carry an ID the project has (the same one over again): the check reads every one
        of them, and none is a new item, so the project's 999 numbers are not used up however many rows there are."""
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        for r in range(2, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                ws.cell(r, c).value = None
        for r in range(2, data_rows + 2):
            ws.cell(r, 1).value = self.a1
        wb.save(str(self.path))

    def check_actions(self):
        status, listed = self.sheets()
        self.assertEqual(status, 200, listed)
        shown = {x["table"]: x["rows"] for x in listed["sheets"]}["actions"]
        return shown, self.post(op="check", project="ABC", file=listed["file"], sheets=["actions"])

    def test_a_sheet_of_1999_and_of_2000_rows_shows_its_number_and_ticking_it_is_checked(self):
        for n in (1999, 2000):
            self.actions_with(n)
            shown, (status, got) = self.check_actions()
            self.assertEqual(shown, n)
            self.assertEqual(status, 200, f"{n} rows: listed with its number, so ticking it is not refused: {got}")

    def test_a_sheet_of_2001_rows_is_over_the_limit_and_refused_in_words(self):
        self.actions_with(2001)
        shown, (status, got) = self.check_actions()
        self.assertEqual((shown, status), (excel_import.OVER_LIMIT, 400))
        self.assertIn("has more than 2,000 rows", got["message"])

    def test_every_sheet_over_2000_rows_is_listed_as_over_the_limit_and_ticking_it_is_refused(self):
        for n in (2001, 3000, 4999, 5000, 5001, 5002):
            self.decisions_with(n)
            self.assertEqual(self.decisions_rows(), excel_import.OVER_LIMIT, f"{n} rows")
            status, got = self.check_decisions()
            self.assertEqual(status, 400, f"{n} rows: labelled over the limit, so refused")
            self.assertIn("more than", got["message"])      # (up to 4,999 rows: "has more than 2,000 rows"; beyond, the reach test says so)

    def test_a_few_rows_and_one_far_off_cell_is_listed_as_over_the_limit_and_refused(self):
        for at in (excel_import.MAX_SHEET_ROWS + 1, excel_import.MAX_SHEET_ROWS + 50):
            self.decisions_with(3, stray=at)
            self.assertEqual(self.decisions_rows(), excel_import.OVER_LIMIT, f"stray at row {at}")
            self.assertEqual(self.check_decisions()[0], 400)

    def test_a_cell_at_row_2500_and_column_90_is_over_the_limit_by_its_cell_count_and_refused(self):
        # Inside both reach limits (5,000 rows, 100 columns) but 2,500 x 90 = 225,000 cells is more than MAX_SHEET_CELLS.
        self.decisions_with(3, stray=2500, stray_col=90)
        self.assertLessEqual(2500, excel_import.MAX_SHEET_ROWS)
        self.assertLessEqual(90, excel_import.MAX_SHEET_COLUMNS)
        self.assertGreater(2500 * 90, excel_import.MAX_SHEET_CELLS)
        self.assertEqual(self.decisions_rows(), excel_import.OVER_LIMIT)
        self.assertEqual(self.check_decisions()[0], 400)

    def test_a_far_off_cell_just_inside_every_limit_keeps_its_count_and_is_checked(self):
        self.decisions_with(3, stray=1500, stray_col=100)         # 150,000 cells
        self.assertEqual(self.decisions_rows(), 4)
        self.assertEqual(self.check_decisions()[0], 200)

    def test_a_sheet_wider_than_the_limit_is_listed_as_over_the_limit_and_refused(self):
        wb = load_workbook(str(self.path))
        wb["Decisions"].cell(2, excel_import.MAX_SHEET_COLUMNS + 5).value = "far right"
        wb.save(str(self.path))
        self.assertEqual(self.decisions_rows(), excel_import.OVER_LIMIT)
        self.assertEqual(self.check_decisions()[0], 400)

    def test_rows_with_something_only_under_a_heading_the_import_does_not_read_are_not_counted_as_the_check_does_not(self):
        # 2,100 rows whose only content is under an unknown heading: the check counts none of them, so the list does not either.
        wb = load_workbook(str(self.path))
        ws = wb["Decisions"]
        for r in range(2, ws.max_row + 1):
            ws.cell(r, 2).value = None
        col = ws.max_column + 1
        ws.cell(1, col).value = "Spare notes"
        for r in range(2, 2102):
            ws.cell(r, col).value = f"note {r}"
        wb.save(str(self.path))
        self.assertEqual(self.decisions_rows(), 1, "only the row that still has its ID counts")
        self.assertEqual(self.check_decisions()[0], 200)

    def test_rows_whose_id_is_a_formula_are_not_counted_as_the_check_does_not(self):
        self.actions_with(0)
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        for r in range(2, 2102):
            ws.cell(r, 1).value = "=A1"
        wb.save(str(self.path))
        shown, (status, got) = self.check_actions()
        self.assertEqual((shown, status), (0, 200))

    def test_without_a_store_to_name_the_columns_the_list_never_counts_fewer_rows_than_the_check(self):
        self.decisions_with(2100)
        by_store = {s["table"]: s["rows"] for s in excel_import.list_sheets(self.path, self.store)}["decisions"]
        bare = {s["table"]: s["rows"] for s in excel_import.list_sheets(self.path)}["decisions"]
        self.assertEqual((by_store, bare), (excel_import.OVER_LIMIT, excel_import.OVER_LIMIT))
        self.decisions_with(1500)
        self.assertEqual({s["table"]: s["rows"] for s in excel_import.list_sheets(self.path)}["decisions"], 1500)

    def test_a_stray_cell_on_the_last_row_inside_the_limit_is_a_row_like_any_other(self):
        self.decisions_with(3)
        plain = self.decisions_rows()
        self.decisions_with(3, stray=excel_import.MAX_SHEET_ROWS)
        self.assertEqual(self.decisions_rows(), plain + 1)
        self.assertEqual(self.check_decisions()[0], 200)

    def test_not_a_workbook_is_refused_in_words(self):
        status, got = self.post(op="sheets", project="ABC", name="x.xlsx", data=__import__("base64").b64encode(b"nope").decode())
        self.assertEqual(status, 400)
        self.assertIn("can't be read as an Excel workbook", got["message"])
        self.assertEqual(excel_route.PLANS, {})

    def test_the_request_is_checked(self):
        status, got = self.post(op="sheets", project="ABC", name="x.xlsx", data="x", sheets=["actions"])
        self.assertEqual(status, 400)
        for bad in ([], "actions", ["nope"], ["actions", "actions"], [1], ["actions"] * 9):
            status, listed = self.sheets()
            self.assertEqual(self.post(op="check", project="ABC", file=listed["file"], sheets=bad)[0], 400, bad)
        self.assertEqual(self.post(op="check", project="ABC", file=listed["file"])[0], 400, "a kept file needs the ticked sheets")
        self.assertEqual(self.post(op="check", project="ABC", file="nope", sheets=["actions"])[0], 410)
        self.assertEqual(self.post(op="check", project="ABC", file=listed["file"], sheets=["actions"], data="x")[0], 400)

    def test_a_kept_workbook_cannot_be_applied_before_it_is_checked_and_goes_when_it_expires(self):
        _, listed = self.sheets()
        self.assertEqual(self.post(op="apply", project="ABC", plan=listed["file"], accept="all", confirm=True)[0], 410)
        self.now[0] += 31 * 60
        self.assertEqual(self.post(op="check", project="ABC", file=listed["file"], sheets=["actions"])[0], 410)
        self.assertEqual(excel_route.PLANS, {})

    def test_the_old_check_with_the_whole_workbook_still_reads_every_sheet(self):
        status, got = self.check()
        self.assertEqual({i["table"] for i in got["items"]}, set(TABLES))


class Followups(Base):
    """Issue 723: what a "sheets" call with no check after it leaves behind. A fake clock (self.now) is used, so nothing waits."""

    def listed(self):
        status, got = self.post(op="sheets", project="ABC", name="ABC work items.xlsx", data=encoded(self.path))
        self.assertEqual(status, 200, got)
        return got["file"]

    def test_a_held_workbook_with_no_check_goes_after_the_wait_and_not_before(self):
        key = self.listed()
        held = excel_route.PLANS[key]
        self.assertTrue(held["dir"].exists())
        self.assertEqual(held["timer"].interval, excel_route.PLAN_MINUTES * 60 + 5)   # the timer runs just after the calls' own limit
        self.now[0] += excel_route.PLAN_MINUTES * 60                                  # exactly the wait: still held
        self.assertEqual(self.post(op="check", project="ABC", file=key, sheets=["actions"])[0], 200)
        self.now[0] += excel_route.PLAN_MINUTES * 60 + 1                              # (the check above held it again from now)
        self.assertEqual(self.post(op="check", project="ABC", file=key, sheets=["actions"])[0], 410)
        self.assertEqual((excel_route.PLANS, held["dir"].exists()), ({}, False))

    def test_a_held_workbook_with_no_check_goes_when_its_timer_runs_with_no_later_call(self):
        key = self.listed()
        held = excel_route.PLANS[key]
        excel_route._expire_one(key, held)
        self.assertEqual((excel_route.PLANS, held["dir"].exists()), ({}, False))

    def test_a_new_workbook_pushes_out_a_held_file_before_a_plan_waiting_for_apply(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        self.now[0] += 1
        plan = self.check()[1]["plan"]                                                 # the oldest of all
        files = []
        for _ in range(excel_route.MAX_PLANS - 1):
            self.now[0] += 1
            files.append(self.listed())
        self.assertEqual(len(excel_route.PLANS), excel_route.MAX_PLANS)
        self.now[0] += 1
        newest = self.listed()
        self.assertEqual(len(excel_route.PLANS), excel_route.MAX_PLANS)
        self.assertIn(plan, excel_route.PLANS)
        self.assertNotIn(files[0], excel_route.PLANS)                                  # the oldest file went
        self.assertIn(newest, excel_route.PLANS)
        status, done = self.apply(plan)
        self.assertEqual((status, done["ok"]), (200, True), done)

    def test_when_every_held_one_is_a_plan_the_oldest_plan_still_goes(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        plans = []
        for _ in range(excel_route.MAX_PLANS):
            self.now[0] += 1
            plans.append(self.check()[1]["plan"])
        self.now[0] += 1
        self.listed()
        self.assertNotIn(plans[0], excel_route.PLANS)
        self.assertEqual(len(excel_route.PLANS), excel_route.MAX_PLANS)


if __name__ == "__main__":
    unittest.main()
