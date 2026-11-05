"""Item 655: Import from Excel, choose which sheets to import. Server side (POST /api/excel-import, src/clark/excel_route.py and
excel_import.read_workbook). Fictional data only. Run: python3 dev/run_tests.py test_item_655_sheets

An unticked sheet is left completely alone: none of its rows is read, counted, listed or imported, and the rows of its table are never
proposed as "no longer in the workbook". The sheets are named in the check; the apply uses the plan the check stored, so the same sheets.
"""
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_excel_route import Base, encoded

from clark import excel, excel_route

ALL = ["Actions", "Risks and issues", "Decisions", "Milestones", "Use cases"]


class Sheets(Base):
    def setUp(self):
        super().setUp()
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        self.edit("Milestones", self.demo.milestone, Milestone="Pilot live, moved")
        self.edit("Use cases", self.demo.use_case, Headline="Matching is fast")

    def tables(self, got):
        return sorted({i["table"] for i in got["items"]})

    def drop_row(self, sheet, item_id):
        wb = load_workbook(str(self.path))
        ws = wb[sheet]
        ws.delete_rows(next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == item_id))
        wb.save(str(self.path))

    def test_no_sheets_in_the_request_reads_all_five_as_before(self):
        status, got = self.check()
        self.assertEqual(status, 200)
        self.assertEqual(self.tables(got), ["actions", "milestones", "use_cases"])
        self.assertEqual(got["sheets"], ALL)

    def test_only_the_ticked_sheets_are_read_and_listed(self):
        status, got = self.sheets_check(["Milestones"])
        self.assertEqual(status, 200, got)
        self.assertEqual(self.tables(got), ["milestones"])
        self.assertEqual(got["sheets"], ["Milestones"])
        self.assertEqual(got["counts"], {"new": 0, "changed": 1, "removed": 0})

    def sheets_check(self, sheets):
        return self.post(op="check", project="ABC", name="a.xlsx", data=encoded(self.path), sheets=sheets)

    def test_an_unticked_sheets_rows_are_not_counted_or_listed(self):
        got = self.sheets_check(["Decisions"])[1]
        self.assertEqual(got["items"], [])
        self.assertEqual(got["counts"], {"new": 0, "changed": 0, "removed": 0})
        self.assertNotIn("Pilot live", got["report"])
        self.assertNotIn("Milestones", got["report"])
        every = self.check()[1]
        self.assertGreater(every["unchanged"], 0)                      # the other rows are counted when their sheets are read...
        self.assertEqual(got["unchanged"], 0)                          # ...and not when they are left alone

    def test_rows_missing_from_an_unticked_sheet_propose_nothing_for_it(self):
        self.drop_row("Actions", self.a2)
        self.drop_row("Milestones", self.demo.milestone)
        ticked = self.sheets_check(["Actions"])[1]
        self.assertEqual([(i["table"], i["kind"]) for i in ticked["items"] if i["kind"] == "removed"], [("actions", "removed")])
        only_actions_off = self.sheets_check(["Milestones", "Use cases"])[1]
        self.assertEqual([i["table"] for i in only_actions_off["items"] if i["kind"] == "removed"], ["milestones"])
        nothing_for_actions = self.sheets_check(["Use cases"])[1]
        self.assertEqual([i for i in nothing_for_actions["items"] if i["kind"] == "removed"], [])
        self.assertNotIn("no longer in the workbook:", " ".join(nothing_for_actions["notes"]))

    def test_a_sheet_that_is_not_ticked_is_not_even_size_checked_or_checked_for_a_twin(self):
        wb = load_workbook(str(self.path))
        wb.create_sheet("RAID")                                        # a second sheet for the same thing as "Risks and issues"
        wb.save(str(self.path))
        status, got = self.sheets_check(None)
        self.assertEqual(status, 400)
        self.assertIn("two sheets for the same thing", got["message"])
        status, got = self.sheets_check(["Actions"])
        self.assertEqual(status, 200, got)

    def test_an_unknown_sheet_name_is_refused(self):
        for bad in (["Actions", "Budget"], ["actions"], [7], "Actions", {"Actions": True}):
            status, got = self.sheets_check(bad)
            self.assertEqual(status, 400, bad)
            self.assertFalse(got["ok"], bad)
        self.assertEqual(self.sheets_check(["Budget"])[1]["message"], excel_route.BAD_SHEET.format(sheet="Budget"))
        self.assertEqual(excel_route.PLANS, {})

    def test_no_sheet_ticked_is_refused_in_words_and_nothing_waits(self):
        was = self.temp_folders()
        status, got = self.sheets_check([])
        self.assertEqual((status, got["message"]), (400, excel_route.NO_SHEETS))
        self.assertEqual(excel_route.PLANS, {})
        self.assertEqual(self.temp_folders(), was)

    def test_the_apply_uses_the_sheets_of_the_check(self):
        got = self.sheets_check(["Actions"])[1]
        before = self.steps()
        status, done = self.apply(got["plan"], "all")
        self.assertEqual((status, done["counts"]["changed"]), (200, 1), done)
        self.assertEqual(self.steps(), before + 1)
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan, version two")
        self.assertEqual(self.store.read("milestones", ref=self.demo.milestone)["name"], "Pilot live")      # the unticked sheet was left alone
        self.assertEqual(self.store.read("use_cases", ref=self.demo.use_case).get("headline"), "")

    def test_an_apply_cannot_name_other_sheets(self):
        got = self.sheets_check(["Actions"])[1]
        status, refused = self.apply(got["plan"], "all", sheets=ALL)
        self.assertEqual(status, 400)
        self.assertIn("not allowed", refused["message"])

    def test_a_workbook_with_none_of_the_ticked_sheets_says_so(self):
        wb = load_workbook(str(self.path))
        del wb["Use cases"]
        wb.save(str(self.path))
        status, got = self.sheets_check(["Use cases"])
        self.assertEqual(status, 200)
        self.assertTrue(any("none of the sheets you chose (Use cases)" in p for p in got["problems"]), got["problems"])


class WhichSheets(Base):
    def sheets(self, **extra):
        return self.post(op="sheets", project="ABC", name="a.xlsx", data=encoded(self.path), **extra)

    def test_the_sheets_the_workbook_has_are_named_in_the_pages_order_and_nothing_waits_or_is_written(self):
        was = self.temp_folders()
        before = self.steps()
        got = self.sheets()
        self.assertEqual((got[0], got[1]["sheets"]), (200, ALL))
        self.assertEqual(got[1]["rows"], {"Actions": 2, "Risks and issues": 0, "Decisions": 0, "Milestones": 1, "Use cases": 1})
        self.assertEqual((excel_route.PLANS, self.steps(), self.temp_folders()), ({}, before, was))

    def test_the_rows_are_the_rows_under_the_header_that_hold_something(self):
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        ws.cell(ws.max_row + 3, 2).value = "   "                        # a blank-looking row is not a row
        ws.cell(ws.max_row + 1, 2).value = "Book the demo"             # a row after a gap is
        wb.save(str(self.path))
        self.assertEqual(self.sheets()[1]["rows"]["Actions"], 3)

    def test_a_sheet_the_workbook_lacks_is_not_named_and_a_history_sheet_is_never_offered(self):
        wb = load_workbook(str(self.path))
        del wb["Decisions"]
        wb.create_sheet("History")
        wb.save(str(self.path))
        self.assertEqual(self.sheets()[1]["sheets"], ["Actions", "Risks and issues", "Milestones", "Use cases"])

    def test_an_old_name_for_the_risks_sheet_is_the_same_sheet(self):
        wb = load_workbook(str(self.path))
        wb["Risks and issues"].title = "RAID"
        wb.save(str(self.path))
        self.assertIn("Risks and issues", self.sheets()[1]["sheets"])

    def test_a_file_that_is_not_a_workbook_is_refused_in_words(self):
        status, got = self.post(op="sheets", project="ABC", name="a.xlsx", data=__import__("base64").b64encode(b"not a workbook").decode())
        self.assertEqual(status, 400)
        self.assertIn("can't be read as an Excel workbook", got["message"])

    def test_the_request_takes_no_other_field(self):
        self.assertEqual(self.sheets(accept="all")[0], 400)

    def test_the_page_order_is_the_imports_five_sheets(self):
        self.assertEqual(sorted(excel_route.SHEET_ORDER), sorted(excel.SHEET_OF.values()))


class ExportUnchanged(Base):
    def test_export_still_writes_every_sheet(self):
        names = load_workbook(str(self.path)).sheetnames
        for sheet in ALL:
            self.assertIn(sheet, names)
        self.assertEqual(sorted(excel.SHEET_OF.values()), sorted(ALL))
        import inspect
        self.assertNotIn("sheets", inspect.signature(excel.export_project).parameters)      # an export takes no choice of sheets


if __name__ == "__main__":
    unittest.main()


class EveryCombination(Base):
    """Each way of ticking: all, each single sheet, none, and a sheet the file does not have. An unticked sheet writes nothing, archives
    nothing, and its rule-breaking rows do not block the import."""
    TABLES = {"Actions": "actions", "Risks and issues": "raid", "Decisions": "decisions", "Milestones": "milestones", "Use cases": "use_cases"}

    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", "tester") as st:
            self.raid = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Key person leaves", "raised": "2026-10-01", "source": "demo"})
            self.dec = st.create("decisions", {"project": "ABC", "decision": "Use the shared drive", "date": "2026-10-02", "source": "demo"})
        self.path.unlink()                                       # a fresh export that holds the risk and the decision too
        made = excel.export_project(self.store, "ABC", self.path, self.tmp / "state2.json", on=excel_route_on())
        record = excel.load_state(self.tmp / "state2.json", made)
        excel.save_state(__import__("pathlib").Path(self.store.path).parent / excel.STATE_FILE, excel.id_key("ABC", record["export_id"]), record)
        self.ids = {"Actions": self.a1, "Risks and issues": self.raid, "Decisions": self.dec, "Milestones": self.demo.milestone, "Use cases": self.demo.use_case}

    def snapshot(self):
        return {t: sorted((r["id"], r["archived"], repr(sorted((k, repr(v)) for k, v in r.items() if "updated" not in k and "modified" not in k))) for r in self.store.read(t, project="ABC"))
                for t in self.TABLES.values()}

    def combos(self):
        yield ALL
        for n in ALL:
            yield [n]
        for n in ALL:
            yield [m for m in ALL if m != n]

    def run_with(self, ticked):
        before = self.snapshot()
        status, got = self.post(op="check", project="ABC", name="a.xlsx", data=encoded(self.path), sheets=ticked)
        return before, status, got

    def test_rows_missing_from_every_sheet_are_archived_only_in_the_ticked_ones(self):
        for sheet, item in self.ids.items():
            wb = load_workbook(str(self.path))
            ws = wb[sheet]
            ws.delete_rows(next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == item))
            wb.save(str(self.path))
        excel_route.PLANS.clear()
        every = self.run_with(ALL)[2]
        can = {i["table"] for i in every["items"] if i["kind"] == "removed"}          # the tables whose missing rows are proposed for archiving
        self.assertGreaterEqual(len(can), 3, can)
        for ticked in self.combos():
            with self.subTest(ticked=ticked):
                excel_route.PLANS.clear()
                before, status, got = self.run_with(ticked)
                self.assertEqual(status, 200, got)
                self.assertEqual({i["table"] for i in got["items"] if i["kind"] == "removed"}, can & {self.TABLES[n] for n in ticked})
                if got["items"]:
                    status, done = self.apply(got["plan"], [i["n"] for i in got["items"]])
                    self.assertEqual(status, 200, done)
                after = self.snapshot()
                for sheet, table in self.TABLES.items():
                    if sheet not in ticked or table not in can:
                        self.assertEqual(after[table], before[table], f"{sheet} must not change")
                    else:
                        self.assertNotEqual(after[table], before[table], f"{sheet} was ticked, so its missing row is archived")
                if got["items"]:
                    self.assertEqual(self.post(op="undo", project="ABC", apply_id=done["apply_id"])[0], 200)

    def test_a_row_that_breaks_a_rule_blocks_only_when_its_sheet_is_ticked(self):
        for sheet, item in self.ids.items():
            self.edit(sheet, item, Status="Not a status")
        for ticked in self.combos():
            with self.subTest(ticked=ticked):
                excel_route.PLANS.clear()
                before, status, got = self.run_with(ticked)
                self.assertEqual(status, 200, got)
                self.assertEqual(self.snapshot(), before, "a check writes nothing")
                named = " ".join(r["name"] for r in got["refused"])
                named = " ".join(r["name"] for r in got["refused"])
                for sheet, item in self.ids.items():
                    self.assertEqual(f"{item}:" in named, sheet in ticked, f"{sheet}: refused only when ticked ({named})")

    def test_unticked_broken_rows_do_not_block_the_ticked_ones(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        self.edit("Milestones", self.demo.milestone, Status="Not a status")
        self.edit("Use cases", self.demo.use_case, Status="Not a status")
        before, status, got = self.run_with(["Actions"])
        self.assertEqual((status, got["refused"], got["counts"]["changed"]), (200, [], 1))
        status, done = self.apply(got["plan"], "all")
        self.assertEqual(status, 200, done)
        after = self.snapshot()
        self.assertEqual({t: after[t] for t in after if t != "actions"}, {t: before[t] for t in before if t != "actions"})
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan, version two")

    def test_none_ticked_and_a_sheet_the_file_lacks(self):
        before, status, got = self.run_with([])
        self.assertEqual(status, 400)
        wb = load_workbook(str(self.path))
        del wb["Decisions"]
        wb.save(str(self.path))
        for ticked in (["Decisions"], ["Actions", "Decisions"]):
            before, status, got = self.run_with(ticked)
            self.assertEqual(status, 200, got)
            self.assertEqual([i for i in got["items"] if i["table"] == "decisions"], [], "a sheet the file lacks proposes nothing, so nothing is archived")
            self.assertEqual(self.snapshot(), before)


def excel_route_on():
    from test_excel_route import ON
    return ON
