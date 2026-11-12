"""Row 1107: the Excel export and import carry a use case's direct milestone links (the Linked milestones column of the Use cases sheet).
A workbook round trip keeps them; an edit adds or ends links (rows kept); a bad cell is refused in plain words. Fictional data only.
Run: python3 dev/run_tests.py test_uc_milestones_excel
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from openpyxl import load_workbook
from _demo import DemoStore, USER
from clark import excel
from clark import excel_import as xi
from clark import store as sm

ON = "2030-06-01"


class Carry(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s, self.uc, self.ms = self.demo.store, self.demo.use_case, self.demo.milestone
        with self.s.step("dashboard", USER) as st:
            self.ms2 = st.create("milestones", {"project": "ABC", "name": "Go live, then some", "baseline_date": "2030-06-01", "source": "demo"})
            self.uc2 = st.create("use_cases", {"project": "ABC", "title": "Payments", "status": "On track", "source": "demo"})
            sm.link_use_case_milestone(st.con, self.uc, self.ms, USER)
            sm.link_use_case_milestone(st.con, self.uc, self.ms2, USER)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-uc-ms-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path, self.state = self.dir / "ABC work items.xlsx", self.dir / "state.json"
        excel.export_project(self.s, "ABC", self.path, self.state, on=ON)

    def sheet(self):
        ws = load_workbook(str(self.path))["Use cases"]
        head = {c.value: c.column for c in ws[1]}
        return ws, head

    def edit(self, row_id, value):
        wb = load_workbook(str(self.path))
        ws = wb["Use cases"]
        head = {c.value: c.column for c in ws[1]}
        r = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == row_id)
        ws.cell(r, head["Linked milestones"]).value = value
        wb.save(str(self.path))

    def read(self):
        return xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)

    def apply(self, plan):
        plan.accept_all()
        res = xi.apply_import(self.s, plan, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        return res

    def test_the_export_writes_one_id_and_name_per_line_and_an_unchanged_workbook_imports_as_no_change(self):
        ws, head = self.sheet()
        cells = {ws.cell(r, head["ID"]).value: ws.cell(r, head["Linked milestones"]).value for r in range(2, ws.max_row + 1)}
        self.assertEqual(cells[self.uc], f"{self.ms}: Pilot live\n{self.ms2}: Go live, then some")
        self.assertIsNone(cells[self.uc2])
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))

    def test_adding_and_removing_a_line_adds_and_ends_links_and_keeps_the_ended_row(self):
        self.edit(self.uc, f"{self.ms}: Pilot live")                       # the second line is gone
        self.edit(self.uc2, f"{self.ms2}: renamed in the workbook\n{self.ms}")    # the name is only a label; a bare id is fine
        p = self.read()
        self.assertEqual(p.problems, [])
        self.assertEqual({c.id: (c.before, c.after) for c in p.changes},
                         {self.uc: ({"milestones": f"{self.ms}, {self.ms2}"}, {"milestones": self.ms}),
                          self.uc2: ({"milestones": None}, {"milestones": f"{self.ms}, {self.ms2}"})})
        self.assertIn("Linked milestones", p.changes[0].describe())
        self.apply(p)
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc), [self.ms])
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc2), sorted([self.ms, self.ms2]))
        ended = [r for r in sm.use_case_milestone_history(self.s.con, self.uc) if r["removed_at"]]
        self.assertEqual([r["milestone"] for r in ended], [self.ms2])
        self.assertEqual(ended[0]["removed_by"], USER)

    def test_a_cleared_cell_ends_every_link_and_a_new_use_case_row_is_made_with_its_links(self):
        self.edit(self.uc, None)
        wb = load_workbook(str(self.path))
        ws = wb["Use cases"]
        head = {c.value: c.column for c in ws[1]}
        r = ws.max_row + 1
        for label, v in (("Use case", "Reporting"), ("Status", "On track"), ("Linked milestones", f"{self.ms2}: Go live")):
            ws.cell(r, head[label]).value = v
        wb.save(str(self.path))
        self.apply(self.read())
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc), [])
        self.assertEqual(len(sm.use_case_milestone_history(self.s.con, self.uc)), 2)
        new = next(r["id"] for r in self.s.read("use_cases", project="ABC") if r["title"] == "Reporting")
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, new), [self.ms2])

    def test_a_cell_that_is_not_a_milestone_id_or_names_another_project_is_refused_and_nothing_changes(self):
        self.edit(self.uc2, "Pilot live")
        p = self.read()
        self.assertEqual(p.changes, [])
        self.assertTrue(any("Linked milestones must be milestone IDs" in str(x) for x in p.problems), [str(x) for x in p.problems])
        self.edit(self.uc2, self.uc)                      # the id of a use case is not a milestone's
        self.assertTrue(any("must be milestone IDs" in str(x) for x in self.read().problems))
        self.edit(self.uc2, "ABC-M-099")
        (c,) = self.read().changes
        self.assertIn("There is no milestone", c.problem)
        plan = self.read()
        plan.accept_all()
        res = xi.apply_import(self.s, plan, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc2), [])

    def test_a_workbook_without_the_column_leaves_the_links_alone(self):
        wb = load_workbook(str(self.path))
        ws = wb["Use cases"]
        head = {c.value: c.column for c in ws[1]}
        ws.delete_cols(head["Linked milestones"])
        wb.save(str(self.path))
        self.assertEqual(self.read().changes, [])
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc), sorted([self.ms, self.ms2]))


if __name__ == "__main__":
    unittest.main()
