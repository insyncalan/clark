"""Excel import: the workbook's client-view column is honoured on new rows. Yes comes in shown, No comes in hidden, and a blank
cell comes in shown (the same as a Word import); a row that already exists keeps its flag when the cell is blank."""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
import _workbook as wbk
from clark import excel_import as xi

SHEETS = (("Actions", "actions", "description"), ("Use cases", "use_cases", "title"))


class ClientView(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-cv-"))
        self.action = self.demo.action(description="Existing action")
        self.path = wbk.make_workbook(self.s, self.tmp / "ABC.xlsx")

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def apply(self, p):
        p.accept_all()
        res = xi.apply_import(self.s, p, USER)
        self.assertTrue(res.applied, res.message)

    def test_yes_no_and_blank_on_new_rows_staged_and_after_apply(self):
        for sheet, table, col in SHEETS:
            for i, v in enumerate(["Yes", "No", None]):
                wbk.add_row(self.path, sheet, **{col: f"New {sheet} {i}", "client_visible": v, **({"status": "On track"} if table == "use_cases" else {})})
        p = xi.read_workbook(self.s, self.path, "ABC", allow_unrecorded=True)
        for sheet, table, col in SHEETS:
            staged = {c.after[col]: c.after.get("client_visible") for c in p.changes if c.kind == "new" and c.table == table}
            # a blank cell stages no value for the flag: the column's own default (shown) applies when the row is made
            self.assertEqual(staged, {f"New {sheet} 0": 1, f"New {sheet} 1": 0, f"New {sheet} 2": None}, sheet)
        self.apply(p)
        for sheet, table, col in SHEETS:
            got = {r[col]: r["client_visible"] for r in self.s.read(table, project="ABC") if r[col].startswith("New ")}
            self.assertEqual(got, {f"New {sheet} 0": 1, f"New {sheet} 1": 0, f"New {sheet} 2": 1}, sheet)

    def test_a_blank_cell_on_an_existing_row_does_not_change_its_flag(self):
        for shown in (1, 0):
            self.demo.update("actions", self.action, {"client_visible": shown})
            self.path = wbk.make_workbook(self.s, self.tmp / f"ABC{shown}.xlsx")
            wbk.edit(self.path, "Actions", self.action, client_visible=None)
            p = xi.read_workbook(self.s, self.path, "ABC", allow_unrecorded=True)
            if p.changes:
                self.apply(p)
            self.assertEqual(self.s.read("actions", ref=self.action)["client_visible"], shown)


if __name__ == "__main__":
    unittest.main()
