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
from pathlib import Path
from _demo import USER as excel_route_user_const
from test_excel_route import Base, encoded, ON as ON_DAY
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

    def test_a_sheet_of_exactly_5000_rows_shows_its_number(self):
        wb = load_workbook(str(self.path))
        ws = wb["Decisions"]
        for r in range(2, 5002):                      # data rows 2 to 5001: exactly 5,000 of them
            ws.cell(r, 2).value = f"Filler {r}"
        for r in range(5002, ws.max_row + 1):
            ws.cell(r, 2).value = None
        wb.save(str(self.path))
        self.assertEqual({s["table"]: s["rows"] for s in self.sheets()[1]["sheets"]}["decisions"], 5000)

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


class Hidden(Base):
    """Issue 723: a hidden (or very hidden) data sheet is not listed, not read and behaves as an unticked sheet; clark's own hidden Lists sheet is still ignored."""
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", excel_route_user_const) as st:
            self.d1 = st.create("decisions", {"project": "ABC", "decision": "Use the shared drive", "date": "2026-10-02", "status": "Made", "source": "demo"})
        fresh = self.tmp / "again" / "ABC work items.xlsx"          # a new export, now with a decision in it
        fresh.parent.mkdir()
        made = excel_import.excel.export_project(self.store, "ABC", fresh, self.tmp / "state2.json", on=ON_DAY)
        record = excel_import.excel.load_state(self.tmp / "state2.json", made)
        excel_import.excel.save_state(Path(self.store.path).parent / excel_import.excel.STATE_FILE,
                                      excel_import.excel.id_key("ABC", record["export_id"]), record)
        self.path.write_bytes(fresh.read_bytes())

    def hide(self, state="hidden", sheet="Decisions"):
        """Hide `sheet`, and give the workbook something to apply (an Action edit) and a new decision row."""
        wb = load_workbook(str(self.path))
        add_row(wb["Decisions"], "decisions", "A hidden new decision")
        wb[sheet].sheet_state = state
        wb["Actions"].cell(2, {c.value: c.column for c in wb["Actions"][1]}["Description"]).value = "Draft the cut-over plan, version two"
        wb.save(str(self.path))

    def sheets(self):
        return self.post(op="sheets", project="ABC", name="ABC work items.xlsx", data=encoded(self.path))

    def decisions(self):
        return [(r["id"], r["decision"], r["archived"]) for r in self.store.read("decisions", project="ABC")]

    def hidden_data_sheet_is_read(self, state):
        self.hide(state)
        status, got = self.sheets()
        self.assertEqual([s["table"] for s in got["sheets"]], list(TABLES), "listed like a visible one")
        status, got = self.post(op="check", project="ABC", file=got["file"], sheets=list(TABLES))
        self.assertEqual((status, got["refused"]), (200, []))
        self.assertEqual(self.post(op="apply", project="ABC", plan=got["plan"], accept="all", confirm=True)[0], 200)
        self.assertIn("A hidden new decision", [d[1] for d in self.decisions()], "and imported")

    def test_a_hidden_data_sheet_is_listed_and_imported(self):
        self.hidden_data_sheet_is_read("hidden")

    def test_a_very_hidden_data_sheet_is_listed_and_imported(self):
        self.hidden_data_sheet_is_read("veryHidden")

    def test_the_check_with_sheets_omitted_reads_a_hidden_data_sheet(self):
        self.hide()
        status, got = self.check()
        self.assertEqual((status, got["refused"]), (200, []))
        self.assertIn("decisions", {i["table"] for i in got["items"]})

    def test_a_hidden_data_sheet_with_an_old_spelling_is_listed_and_read(self):
        wb = load_workbook(str(self.path))
        wb["Risks & Issues"].title = "Risks and Issues"
        wb["Risks and Issues"].sheet_state = "hidden"
        wb.save(str(self.path))
        status, got = self.sheets()
        self.assertEqual([s["table"] for s in got["sheets"]], list(TABLES))
        status, got = self.post(op="check", project="ABC", file=got["file"], sheets=["raid"])
        self.assertEqual((status, got["refused"]), (200, []))

    def test_a_hidden_sheet_with_another_name_is_not_listed_not_read_and_nothing_is_archived(self):
        wb = load_workbook(str(self.path))
        scratch = wb.create_sheet("Scratch")
        scratch.append(["Decision", "Status"])
        scratch.append(["A scratch decision", "Not a status"])
        scratch.sheet_state = "hidden"
        wb.save(str(self.path))
        before = self.decisions()
        status, got = self.sheets()
        self.assertEqual([s["table"] for s in got["sheets"]], list(TABLES))
        self.assertNotIn("Scratch", json.dumps(got))
        status, got = self.check()
        self.assertEqual((status, got["refused"], got["problems"]), (200, [], []))
        self.assertNotIn("scratch", json.dumps(got).lower())
        self.assertEqual(self.decisions(), before)

    def test_the_hidden_lists_sheet_is_not_listed_and_not_read(self):
        wb = load_workbook(str(self.path))
        self.assertEqual(wb["Lists"].sheet_state, "hidden")
        status, got = self.sheets()
        self.assertEqual([s["table"] for s in got["sheets"]], list(TABLES))
        self.assertNotIn("Lists", json.dumps(got))

    def test_a_hidden_duplicate_of_a_visible_data_sheet_still_gives_the_two_sheets_refusal(self):
        wb = load_workbook(str(self.path))
        copy = wb.copy_worksheet(wb["Decisions"])
        copy.title = "Decisions "
        copy.sheet_state = "hidden"
        wb.save(str(self.path))
        status, got = self.sheets()
        self.assertEqual(status, 400)
        self.assertIn("two sheets for the same thing", got["message"])


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
