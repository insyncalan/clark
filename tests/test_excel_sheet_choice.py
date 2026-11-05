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

    def test_a_sheet_over_5000_rows_is_counted_to_one_past_the_limit_never_to_a_wrong_number(self):
        # The box says "more than 5,000 rows" for it (dataCard.sheetWord); the count stops at 5,001 so the page can tell 5,000 from more.
        wb = load_workbook(str(self.path))
        ws = wb["Decisions"]
        for r in range(2, 5003):                      # data rows 2 to 5002: 5,001 of them
            ws.cell(r, 2).value = f"Filler {r}"
        wb.save(str(self.path))
        self.assertEqual({s["table"]: s["rows"] for s in self.sheets()[1]["sheets"]}["decisions"], 5001)

    def decisions_with(self, data_rows, stray=None):
        """Decisions holding exactly `data_rows` rows with something in them (rows 2 and up), and a far-off cell at row `stray` if given."""
        wb = load_workbook(str(self.path))
        ws = wb["Decisions"]
        for r in range(2, ws.max_row + 1):
            ws.cell(r, 2).value = None
        for r in range(2, data_rows + 2):
            ws.cell(r, 2).value = f"Filler {r}"
        if stray:
            ws.cell(stray, 1).value = "far off"
        wb.save(str(self.path))

    def decisions_rows(self):
        return {s["table"]: s["rows"] for s in self.sheets()[1]["sheets"]}["decisions"]

    def test_a_sheet_of_4999_rows_shows_its_number(self):
        # Row 1 is the header, so 4,999 data rows end at row 5,000: the last size the check's size test (MAX_SHEET_ROWS) lets through.
        # (The check then refuses it in words for holding more than MAX_ROWS rows with something in them: a separate, lower limit.)
        self.decisions_with(4999)
        self.assertEqual(self.decisions_rows(), 4999)

    def test_a_sheet_of_exactly_5000_rows_is_listed_as_over_the_limit_because_ticking_it_is_refused(self):
        self.decisions_with(5000)
        self.assertEqual(self.decisions_rows(), excel_import.MAX_SHEET_ROWS + 1)
        status, listed = self.sheets()
        status, got = self.post(op="check", project="ABC", file=listed["file"], sheets=["decisions"])
        self.assertEqual(status, 400, "the list and the limit agree: what is labelled 'more than 5,000 rows' is refused")

    def test_a_sheet_of_5001_rows_is_listed_as_over_the_limit(self):
        self.decisions_with(5001)
        self.assertEqual(self.decisions_rows(), excel_import.MAX_SHEET_ROWS + 1)

    def test_a_few_rows_and_one_far_off_cell_is_listed_as_over_the_limit_as_the_check_reads_it(self):
        self.decisions_with(3, stray=excel_import.MAX_SHEET_ROWS + 50)
        self.assertEqual(self.decisions_rows(), excel_import.MAX_SHEET_ROWS + 1)

    def test_a_stray_cell_inside_the_limit_does_not_change_the_count(self):
        self.decisions_with(3)
        plain = self.decisions_rows()
        self.decisions_with(3, stray=excel_import.MAX_SHEET_ROWS)
        self.assertEqual(self.decisions_rows(), plain + 1, "the stray cell's row is a row with something in it, nothing more")

    def test_a_sheet_wider_than_the_limit_is_listed_as_over_the_limit_as_the_check_reads_it(self):
        wb = load_workbook(str(self.path))
        wb["Decisions"].cell(2, excel_import.MAX_SHEET_COLUMNS + 5).value = "far right"
        wb.save(str(self.path))
        self.assertEqual(self.decisions_rows(), excel_import.MAX_SHEET_ROWS + 1)

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
