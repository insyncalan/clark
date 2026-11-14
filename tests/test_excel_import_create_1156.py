"""Row 1156: a work item row names a milestone or use case clark does not have. The import lists it, asks for an answer (create it, or use an
existing one), writes nothing until every one is answered, and links the work items to what was made or picked, all as one step.

Run: python3 dev/run_tests.py test_excel_import_create_1156
"""
import unittest

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import USER

from clark import excel_import as xi
from openpyxl import load_workbook
from test_excel_roundtrip import RoundTrip, edit


def add_row(path, sheet, **cells):
    wb = load_workbook(str(path))
    ws = wb[sheet]
    head = {c.value: c.column for c in ws[1]}
    row = ws.max_row + 1
    for label, value in cells.items():
        ws.cell(row, head[label]).value = value
    wb.save(str(path))

MS, UC = "Pilot wave 2", "Reporting set-up"


def work_item(path, text="Set up the test rig", ms=MS, uc=UC, sheet="Actions"):
    cells = {"Actions": {"Description": text, "Milestone": ms, "Use case": uc},
             "Risks & Issues": {"Description": text, "Type": "Risk", "Status": "Open", "Milestone": ms, "Use case": uc},
             "Decisions": {"Decision": text, "Status": "Pending", "Use case": uc}}[sheet]    # the Decisions sheet has no Milestone column
    add_row(path, sheet, **cells)


class Create(RoundTrip):
    def ask(self):
        plan = self.read()
        plan.accept_all()
        return plan

    def apply(self, plan, answers):
        plan.answers = answers
        return xi.apply_import(self.s, plan, USER, state_path=self.state)

    def ids(self, plan):
        return {u["kind"]: u["id"] for u in plan.unknowns}

    def new_action(self):
        (a,) = [r for r in self.s.read("actions", project="ABC") if r["description"] == "Set up the test rig"]
        return a

    def test_unknown_names_are_listed_and_the_plan_is_not_refused(self):
        work_item(self.path)
        plan = self.read()
        self.assertEqual([c.problem for c in plan.changes], [""])
        self.assertEqual(sorted((u["kind"], u["label"]) for u in plan.unknowns), [("milestone", MS), ("use_case", UC)])

    def test_nothing_is_written_until_every_label_is_answered(self):
        work_item(self.path)
        plan = self.ask()
        before, n = self.snapshot(), self.steps()
        ids = self.ids(plan)
        for answers in ({}, {ids["milestone"]: {"do": "new"}}):
            res = self.apply(plan, answers)
            self.assertFalse(res.applied)
            self.assertEqual(res.message, xi.NEEDS_ANSWER)
        self.assertEqual((self.snapshot(), self.steps()), (before, n))

    def test_create_makes_both_and_links_the_work_item_in_one_undoable_step(self):
        work_item(self.path)
        plan = self.ask()
        before, n = self.snapshot(), self.steps()
        res = self.apply(plan, {u["id"]: {"do": "new"} for u in plan.unknowns})
        self.assertTrue(res.applied, res.message)
        self.assertEqual(self.steps(), n + 1)
        (m,) = [r for r in self.s.read("milestones", project="ABC") if r["name"] == MS]
        (u,) = [r for r in self.s.read("use_cases", project="ABC") if r["title"] == UC]
        a = self.new_action()
        self.assertEqual((a["milestone"], a["use_case"]), (m["id"], u["id"]))
        done = self.s.undo(res.step_id, USER)
        self.assertEqual(done["skipped"], [])
        self.assertEqual(self.snapshot(), before)

    def test_a_created_milestone_and_use_case_hold_the_cleaned_label_source_project_and_status(self):
        work_item(self.path, ms="  Pilot   wave 2 ", uc=" Reporting\tset-up  ")
        plan = self.ask()
        res = self.apply(plan, {u["id"]: {"do": "new"} for u in plan.unknowns})
        self.assertTrue(res.applied, res.message)
        (m,) = [r for r in self.s.read("milestones", project="ABC") if r["name"] == MS]
        (u,) = [r for r in self.s.read("use_cases", project="ABC") if r["title"] == UC]
        self.assertEqual((m["name"], m["project"], m["status"]), (MS, "ABC", "Planned"))
        self.assertEqual((u["title"], u["project"], u["status"]), (UC, "ABC", "On track"))
        for made in (m, u):
            self.assertTrue(made["source"].startswith("Excel import, "), made["source"])
            self.assertTrue(made["source"].endswith(plan.file), made["source"])

    def test_importing_the_same_workbook_again_after_new_asks_nothing_and_makes_nothing(self):
        work_item(self.path)
        plan = self.ask()
        res = self.apply(plan, {u["id"]: {"do": "new"} for u in plan.unknowns})
        self.assertTrue(res.applied, res.message)
        before, n = self.snapshot(), self.steps()
        again = self.read()
        self.assertEqual(again.unknowns, [])
        self.assertEqual([c for c in again.changes if c.kind == "new"], [])
        again.accept_all()
        xi.apply_import(self.s, again, USER, state_path=self.state)
        self.assertEqual((self.snapshot(), self.steps()), (before, n))
        self.assertEqual(len([r for r in self.s.read("milestones", project="ABC") if r["name"] == MS]), 1)
        self.assertEqual(len([r for r in self.s.read("use_cases", project="ABC") if r["title"] == UC]), 1)
        self.assertEqual(len([r for r in self.s.read("actions", project="ABC") if r["description"] == "Set up the test rig"]), 1)

    def test_use_links_an_existing_item_and_creates_nothing(self):
        work_item(self.path)
        plan = self.ask()
        ids = self.ids(plan)
        ms, uc = len(self.s.read("milestones", project="ABC")), len(self.s.read("use_cases", project="ABC"))
        res = self.apply(plan, {ids["milestone"]: {"do": "use", "id": self.demo.milestone}, ids["use_case"]: {"do": "use", "id": self.demo.use_case}})
        self.assertTrue(res.applied, res.message)
        a = self.new_action()
        self.assertEqual((a["milestone"], a["use_case"]), (self.demo.milestone, self.demo.use_case))
        self.assertEqual((len(self.s.read("milestones", project="ABC")), len(self.s.read("use_cases", project="ABC"))), (ms, uc))

    def test_one_created_and_one_used(self):
        work_item(self.path)
        plan = self.ask()
        ids = self.ids(plan)
        res = self.apply(plan, {ids["milestone"]: {"do": "new"}, ids["use_case"]: {"do": "use", "id": self.demo.use_case}})
        self.assertTrue(res.applied, res.message)
        a = self.new_action()
        self.assertNotEqual(a["milestone"], self.demo.milestone)
        self.assertEqual(a["use_case"], self.demo.use_case)

    def test_a_near_match_is_offered(self):
        name = next(r["name"] for r in self.s.read("milestones", project="ABC") if r["id"] == self.demo.milestone)
        near = name.replace(" ", "") + "."
        self.assertNotEqual(near, name)
        work_item(self.path, ms=near, uc=None)
        (u,) = self.read().unknowns
        self.assertEqual([x["id"] for x in u["near"]], [self.demo.milestone])

    def test_one_question_covers_every_row_naming_the_same_label(self):
        work_item(self.path, "Set up the test rig", uc=None)
        work_item(self.path, "Check the test rig", ms="  pilot WAVE 2 ", uc=None)
        plan = self.ask()
        (u,) = plan.unknowns
        self.assertEqual(len(u["rows"]), 2)
        res = self.apply(plan, {u["id"]: {"do": "new"}})
        self.assertTrue(res.applied, res.message)
        made = [r for r in self.s.read("milestones", project="ABC") if r["name"] == MS]
        self.assertEqual(len(made), 1)
        linked = [r for r in self.s.read("actions", project="ABC") if r["milestone"] == made[0]["id"]]
        self.assertEqual(len(linked), 2)

    def test_a_label_the_workbook_makes_is_not_asked_and_is_linked(self):
        add_row(self.path, "Milestones", Milestone=MS)
        work_item(self.path, uc=None)
        plan = self.ask()
        self.assertEqual(plan.unknowns, [])
        res = self.apply(plan, {})
        self.assertTrue(res.applied, res.message)
        (m,) = [r for r in self.s.read("milestones", project="ABC") if r["name"] == MS]
        self.assertEqual(self.new_action()["milestone"], m["id"])

    def test_two_new_items_with_one_name_refuse_the_row_that_names_them(self):
        add_row(self.path, "Milestones", Milestone=MS)
        add_row(self.path, "Milestones", Milestone=MS)
        work_item(self.path, uc=None)
        plan = self.read()
        (c,) = [c for c in plan.changes if c.table == "actions"]
        self.assertIn("matches more than one milestone (row", c.problem)

    def test_a_rejected_row_needs_no_answer_and_makes_nothing(self):
        edit(self.path, "Decisions", self.d1, Status="Withdrawn")       # one unrelated change, accepted
        work_item(self.path)                                            # the new-action row names an unknown milestone and use case, rejected
        plan = self.read()
        self.assertEqual(len(plan.unknowns), 2)                         # so the unknowns check has something to skip
        (new,) = [c for c in plan.changes if c.table == "actions" and c.kind == "new"]
        (other,) = [c for c in plan.changes if c is not new]
        self.assertEqual(other.table, "decisions")
        plan.reject(new.n)
        plan.accept(other.n)
        ms, uc, ac = (len(self.s.read(t, project="ABC")) for t in ("milestones", "use_cases", "actions"))
        n = self.steps()
        res = self.apply(plan, {})
        self.assertTrue(res.applied, res.message)
        self.assertEqual(self.steps(), n + 1)
        self.assertEqual(tuple(len(self.s.read(t, project="ABC")) for t in ("milestones", "use_cases", "actions")), (ms, uc, ac))
        self.assertEqual([r for r in self.s.read("milestones", project="ABC") if r["name"] == MS], [])
        self.assertEqual([r for r in self.s.read("use_cases", project="ABC") if r["title"] == UC], [])

    def test_unknown_labels_on_the_risks_and_issues_sheet_are_listed(self):
        work_item(self.path, "Watch the test rig", sheet="Risks & Issues")
        plan = self.read()
        rows = [c for c in plan.changes if c.table == "raid"]
        self.assertEqual([c.problem for c in rows], [""])
        self.assertEqual(sorted((u["kind"], u["label"]) for u in plan.unknowns), [("milestone", MS), ("use_case", UC)])
        for u in plan.unknowns:
            self.assertEqual(u["rows"], [{"sheet": rows[0].sheet, "row": rows[0].row}])
            self.assertEqual(u["changes"], [rows[0].n])

    def test_an_unknown_use_case_on_the_decisions_sheet_is_listed(self):
        work_item(self.path, "Use the test rig", sheet="Decisions")
        plan = self.read()
        rows = [c for c in plan.changes if c.table == "decisions"]
        self.assertEqual([c.problem for c in rows], [""])
        self.assertEqual([(u["kind"], u["label"]) for u in plan.unknowns], [("use_case", UC)])
        self.assertEqual(plan.unknowns[0]["changes"], [rows[0].n])

    def other_project_ids(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            return (st.create("milestones", {"project": "XYZ", "name": "Other live", "baseline_date": "2030-03-01", "source": "demo"}),
                    st.create("use_cases", {"project": "XYZ", "title": "Other case", "status": "On track", "source": "demo"}))

    def test_a_use_answer_the_store_refuses_applies_nothing(self):
        """A missing id, an id of the other kind and another project's id: the store refuses each, so nothing is applied."""
        other_ms, other_uc = self.other_project_ids()
        work_item(self.path)
        plan = self.ask()
        ids = self.ids(plan)
        refused = {
            "missing": ("ABC-M-999", "ABC-U-999"),
            "wrong kind": (self.demo.use_case, self.demo.milestone),
            "another project": (other_ms, other_uc),
        }
        for label, (ms, uc) in refused.items():
            for which, answers in (("milestone", {ids["milestone"]: {"do": "use", "id": ms}, ids["use_case"]: {"do": "use", "id": self.demo.use_case}}),
                                   ("use case", {ids["milestone"]: {"do": "use", "id": self.demo.milestone}, ids["use_case"]: {"do": "use", "id": uc}})):
                with self.subTest(label, wrong=which):
                    before, n = self.snapshot(), self.steps()
                    res = self.apply(plan, answers)
                    self.assertFalse(res.applied, res.message)
                    self.assertEqual((self.snapshot(), self.steps()), (before, n))
                    self.assertEqual([r for r in self.s.read("actions", project="ABC") if r["description"] == "Set up the test rig"], [])

    def test_an_unknown_id_is_still_refused_as_before(self):
        work_item(self.path, ms="ABC-M-999", uc=None)
        plan = self.read()
        self.assertEqual(plan.unknowns, [])
        self.assertIn("isn't here", plan.changes[0].problem)


if __name__ == "__main__":
    unittest.main()
