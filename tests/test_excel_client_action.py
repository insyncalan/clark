"""Row 811: the "needed from the client" flag and the Excel round trip. The workbook has NO column for the flag (a new column is new
wording, held for the owner), so the contract pinned here is the minimal one: an export writes no such column, a workbook is read
without it, and an import that changes OTHER cells of an action or a risk leaves its flag where it was (nothing is silently dropped).

Run: python3 dev/run_tests.py test_excel_client_action
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import USER, DemoStore
from openpyxl import load_workbook

from clark import excel
from clark import excel_import as xi
from clark import page

ON = "2030-06-01"
_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")


def setUpModule():
    global _OLD_BRANDING
    _OLD_BRANDING, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD_BRANDING
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


def edit(path, sheet, item_id, **cells):
    wb = load_workbook(str(path))
    ws = wb[sheet]
    head = {c.value: c.column for c in ws[1]}
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == item_id)
    for label, value in cells.items():
        ws.cell(row, head[label]).value = value
    wb.save(str(path))


class RoundTrip(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.action = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Portal supplier late", "raised": "2026-10-01",
                                           "impact": "High", "likelihood": "Medium", "source": "demo", "client_action": 1})
            st.update("actions", self.action, {"client_action": 1})
        self.dir = Path(tempfile.mkdtemp(prefix="clark-ca-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(self.demo.close)
        self.path, self.state = self.dir / "ABC work items.xlsx", self.dir / "state.json"
        excel.export_project(self.s, "ABC", self.path, self.state, on=ON)

    def flags(self):
        return (self.s.read("actions", ref=self.action)["client_action"], self.s.read("raid", ref=self.risk)["client_action"])

    def test_the_export_has_no_column_for_the_flag_and_an_untouched_export_has_no_difference(self):
        for sheet in ("Actions", "Risks & Issues"):
            head = [c.value for c in load_workbook(self.path)[sheet][1]]
            self.assertFalse([h for h in head if h and "client" in h.lower() and h not in ("Client-visible", "Client wording")], head)
        p = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)
        self.assertEqual((p.changes, p.problems), ([], []))

    def test_an_import_that_changes_other_cells_keeps_the_flag(self):
        edit(self.path, "Actions", self.action, Priority="High")
        edit(self.path, "Risks & Issues", self.risk, Owner="Example Owner")
        p = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)
        self.assertEqual(len(p.changes), 2)
        p.accept_all()
        self.assertTrue(xi.apply_import(self.s, p, USER).applied)
        self.assertEqual(self.s.read("actions", ref=self.action)["priority"], "High")
        self.assertEqual(self.flags(), (1, 1))


if __name__ == "__main__":
    unittest.main()
