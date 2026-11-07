"""Row 926: the page's import flow offers the Gantt sheet like the other sheets and reads it only when ticked, through the same route
(POST /api/excel-import ops "sheets", "check", "apply", "undo"). Fictional data only.
Run: python3 dev/run_tests.py test_gantt_excel_import_flow
"""
import io
import unittest
from pathlib import Path

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_excel_route import Base, encoded
from clark import changes, excel, excel_import
from _demo import USER
import test_gantt_excel_export as ex

LINES = 3


class Flow(Base):
    def setUp(self):
        super().setUp()
        self.change = changes.make_change(self.store.path, [], USER)
        for i, name in enumerate(("Alpha", "Dig", "Pour"), start=1):
            st, body = self.change({"project": "ABC", "kind": "gantt_lines", "op": "new", "values": {
                "type": "phase" if i == 1 else "task", "name": name, "start": f"2026-11-0{i}", "end": f"2026-11-1{i}", "show": 1}})
            self.assertEqual(st, 200, body)
        self.plain = self.path.read_bytes()
        self.export()

    def export(self):
        made = excel.export_project(self.store, "ABC", self.path, self.tmp / "state.json", on="2030-06-01")
        record = excel.load_state(self.tmp / "state.json", made)
        excel.save_state(Path(self.store.path).parent / excel.STATE_FILE, excel.id_key("ABC", record["export_id"]), record)

    def sheets(self, path=None):
        return self.post(op="sheets", project="ABC", name="ABC work items.xlsx", data=encoded(path or self.path))

    def lines(self, project="ABC"):
        return {r["id"]: r for r in self.store.read("gantt_lines", project=project)}

    def edit_gantt(self, **cells):
        wb = load_workbook(str(self.path))
        ws = wb["Gantt"]
        head = {c.value: c.column for c in ws[1]}
        for label, value in cells.items():
            ws.cell(2, head[label]).value = value
        wb.save(str(self.path))


class Listing(Flow):
    def test_the_gantt_entry_comes_after_the_five_with_its_name_and_row_count(self):
        st, got = self.sheets()
        self.assertEqual(st, 200, got)
        tables = [s["table"] for s in got["sheets"]]
        self.assertEqual(tables, list(excel_import.CHOICE_ORDER) + ["gantt_lines"])
        self.assertEqual(got["sheets"][-1], {"table": "gantt_lines", "name": "Gantt", "rows": LINES})
        self.assertEqual(excel_import.CHOICE_ORDER, ("actions", "raid", "decisions", "milestones", "use_cases"))

    def test_a_workbook_without_a_gantt_sheet_lists_exactly_what_it_did(self):
        wb = load_workbook(str(self.path))
        del wb["Gantt"]
        wb.save(str(self.path))
        old = excel_import.list_sheets(self.path, self.store)
        self.assertEqual(excel_import.list_sheets(self.path, self.store, "ABC"), old)
        self.assertEqual([s["table"] for s in old], list(excel_import.CHOICE_ORDER))
        self.assertEqual(self.sheets()[1]["sheets"], old)

    def test_the_gantt_sheet_is_named_for_the_projects_gantt_tab(self):
        st, body = self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": {"gantt_tab_name": "Plan"}})
        self.assertEqual(st, 200, body)
        self.export()
        got = self.sheets()[1]["sheets"][-1]
        self.assertEqual((got["table"], got["name"], got["rows"]), ("gantt_lines", "Plan", LINES))

    def test_the_client_workbook_gantt_sheet_is_not_offered(self):
        blob = ex.client(ex.plant())
        self.assertIn("Plan", load_workbook(io.BytesIO(blob)).sheetnames)
        p = self.tmp / "client.xlsx"
        p.write_bytes(blob)
        wb = load_workbook(str(p))
        wb["Plan"].title = "Gantt"
        wb.save(str(p))
        self.assertNotIn("gantt_lines", [s["table"] for s in excel_import.list_sheets(p, self.store, "ABC")])
        self.assertNotIn("gantt_lines", [s["table"] for s in self.sheets(p)[1]["sheets"]])


class Reading(Flow):
    def pick(self, tables):
        st, listed = self.sheets()
        self.assertEqual(st, 200, listed)
        return self.post(op="check", project="ABC", file=listed["file"], sheets=list(tables))

    def test_ticking_only_the_gantt_sheet_plans_and_applies_only_its_changes_in_one_step_with_one_undo(self):
        self.edit_gantt(Line="Alpha, renamed")
        self.edit("Actions", self.a1, Description="Not to be imported")
        before, steps = self.lines(), self.steps()
        st, got = self.pick(["gantt_lines"])
        self.assertEqual(st, 200, got)
        self.assertEqual(got["counts"], {"new": 0, "changed": 1, "removed": 0})
        st, done = self.apply(got["plan"], confirm=True)
        self.assertEqual((st, done["ok"]), (200, True), done)
        self.assertEqual(self.steps(), steps + 1)
        self.assertEqual(self.lines()["ABC-GNT-001"]["name"], "Alpha, renamed")
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan")
        st, back = self.post(op="undo", project="ABC", apply_id=done["apply_id"])
        self.assertEqual((st, back["ok"]), (200, True), back)
        self.assertEqual({k: v["name"] for k, v in self.lines().items()}, {k: v["name"] for k, v in before.items()})

    def test_ticking_a_table_does_not_read_the_gantt_sheet_even_though_the_file_has_one(self):
        self.edit_gantt(Line="Alpha, renamed")
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, two")
        st, got = self.pick(["actions"])
        self.assertEqual((st, got["counts"]), (200, {"new": 0, "changed": 1, "removed": 0}), got)
        st, done = self.apply(got["plan"], confirm=True)
        self.assertEqual(st, 200, done)
        self.assertEqual(self.lines()["ABC-GNT-001"]["name"], "Alpha")

    def test_an_unknown_sheet_name_is_refused_as_before(self):
        for bad in (["nope"], ["gantt"], [], ["gantt_lines", "gantt_lines"], "gantt_lines", ["actions", 1]):
            st, got = self.pick(bad)
            self.assertEqual((st, got["ok"]), (400, False), (bad, got))

    def test_importing_never_writes_another_projects_lines(self):
        other = {r["id"] for r in self.store.read("gantt_lines", project="XYZ")}
        self.edit_gantt(ID="XYZ-GNT-001", Line="Taken over")
        st, got = self.pick(["gantt_lines"])
        self.assertEqual((st, got["counts"]), (200, {"new": 0, "changed": 0, "removed": 0}), got)       # the row is left out and reported
        self.assertTrue(any("XYZ-GNT-001" in p for p in got["problems"]), got["problems"])
        self.assertEqual(self.lines()["ABC-GNT-001"]["name"], "Alpha")
        self.assertEqual({r["id"] for r in self.store.read("gantt_lines", project="XYZ")}, other)


if __name__ == "__main__":
    unittest.main()
