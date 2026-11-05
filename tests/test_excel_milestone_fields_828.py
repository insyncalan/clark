"""Row 828: the five milestone fields the peek now edits (name, owner, workstream, % complete, description) are already columns of the
Milestones sheet, and the workbook round trip carries them both ways with no new column: an edit made in the sheet is read as a change to
that milestone alone, applied in one step; an edit made in the peek is in the next export. Decision: no new column, no dropped one.

Run: python3 dev/run_tests.py test_excel_milestone_fields_828
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import USER, DemoStore
from openpyxl import load_workbook

from clark import changes, excel
from clark import excel_import as xi
from clark import page

ON = "2030-06-01"
SHEET = "Milestones"
FIELDS = {"Milestone": "name", "Owner": "owner", "Workstream": "workstream", "% complete": "percent_complete", "Description": "description"}
_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")


def setUpModule():
    global _OLD_BRANDING
    _OLD_BRANDING, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD_BRANDING
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


class RoundTrip(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.m = self.demo.milestone
        with self.s.step("dashboard", USER) as st:
            st.create("workstreams", {"project": "ABC", "name": "Delivery", "source": "demo"})
        self.dir = Path(tempfile.mkdtemp(prefix="clark-ms828-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(self.demo.close)
        self.path, self.state = self.dir / "ABC work items.xlsx", self.dir / "state.json"
        self.change = changes.make_change(self.s.path, [], USER)

    def export(self):
        excel.export_project(self.s, "ABC", self.path, self.state, on=ON)

    def sheet(self):
        ws = load_workbook(str(self.path))[SHEET]
        head = [c.value for c in ws[1]]
        row = next(r for r in ws.iter_rows(min_row=2) if r[0].value == self.m)
        return {h: row[i].value for i, h in enumerate(head)}

    def test_the_sheet_has_all_five_columns(self):
        self.export()
        self.assertTrue(set(FIELDS) <= set(self.sheet()))

    def test_an_edit_in_the_peek_is_in_the_next_export(self):
        status, body = self.change({"project": "ABC", "kind": "milestones", "op": "update", "id": self.m, "place": "peek",
                                    "changes": {"name": "Go live", "owner": "Sam Example", "workstream": "Delivery", "percent_complete": 40, "description": "Scope"}})
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.export()
        seen = self.sheet()
        self.assertEqual([seen[k] for k in FIELDS], ["Go live", "Sam Example", "Delivery", 40, "Scope"])

    def test_an_edit_in_the_sheet_is_read_as_a_change_to_that_milestone_and_applied(self):
        self.export()
        wb = load_workbook(str(self.path))
        ws = wb[SHEET]
        head = {c.value: c.column for c in ws[1]}
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == self.m)
        for label, value in (("Owner", "Sam Example"), ("% complete", 55), ("Description", "From the sheet")):
            ws.cell(row, head[label]).value = value
        wb.save(str(self.path))
        p = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)
        self.assertEqual(p.problems, [])
        (c,) = p.changes
        self.assertEqual((c.kind, c.id), ("changed", self.m))
        self.assertEqual(set(c.after), {"owner", "percent_complete", "description"})
        p.accept_all()
        self.assertTrue(xi.apply_import(self.s, p, USER).applied)
        now = self.s.read("milestones", ref=self.m)
        self.assertEqual((now["owner"], now["percent_complete"], now["description"]), ("Sam Example", 55, "From the sheet"))

    def test_an_untouched_export_has_no_difference_after_a_peek_edit(self):
        self.change({"project": "ABC", "kind": "milestones", "op": "update", "id": self.m, "place": "peek", "changes": {"owner": "Sam Example", "description": "A\nB"}})
        self.export()
        p = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)
        self.assertEqual((p.changes, p.problems), ([], []))


if __name__ == "__main__":
    unittest.main()
