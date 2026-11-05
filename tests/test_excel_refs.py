"""Item 710: the Milestone and Use case cells of the Excel export read 'ID: name', the Lists sheet and the drop-downs the same,
the Milestones and Use cases sheets list their open work items, and the import reads 'ID: name' or a bare ID back by the ID.

Run: python3 dev/run_tests.py test_excel_refs
"""
import re
import unittest

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import USER
from openpyxl import load_workbook

from clark import excel
from clark import excel_import as xi
from test_excel_roundtrip import RoundTrip, edit


def cells(path, sheet, item_id):
    ws = load_workbook(str(path))[sheet]
    head = {c.value: c.column for c in ws[1]}
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == item_id)
    return {label: ws.cell(row, col).value for label, col in head.items()}


class Export(RoundTrip):
    def test_item_cells_show_id_then_name(self):
        name = next(r["name"] for r in self.s.read("milestones", "ABC") if r["id"] == self.demo.milestone)
        uc = next(r["title"] for r in self.s.read("use_cases", "ABC") if r["id"] == self.demo.use_case)
        row = cells(self.path, "Actions", self.a1)
        self.assertEqual(row["Milestone"], f"{self.demo.milestone}: {name}")
        self.assertEqual(row["Use case"], f"{self.demo.use_case}: {uc}")
        self.assertIsNone(cells(self.path, "Actions", self.a2)["Milestone"])

    def test_lists_and_dropdown_ranges_hold_the_same_text_sorted_by_id(self):
        wb = load_workbook(str(self.path))
        ws = wb["Lists"]
        head = {c.value: c.column_letter for c in ws[1]}
        col = [c.value for c in ws[head["Milestones"]][1:] if c.value]
        self.assertEqual(col, sorted(col))
        self.assertTrue(all(re.match(r"ABC-M-\d{3}: .+", v) for v in col), col)
        dv = next(d for d in wb["Actions"].data_validations.dataValidation
                  if d.type == "list" and d.formula1.startswith(f"Lists!${head['Milestones']}$"))
        self.assertTrue(dv.formula1.endswith(f"${len(col) + 1}"))
        self.assertIn(cells(self.path, "Actions", self.a1)["Milestone"], col)

    def test_a_very_long_name_is_cut_never_the_id(self):
        text = excel.ref_text("ABC-M-007", "x" * 400)
        self.assertLessEqual(len(text), excel.REF_CELL_LIMIT)
        self.assertTrue(text.startswith("ABC-M-007: x") and text.endswith("…"))
        self.assertEqual(excel.ref_text("ABC-M-007", "Short"), "ABC-M-007: Short")
        self.assertEqual(excel.ref_text("ABC-M-007", ""), "ABC-M-007")

    def test_a_very_long_milestone_name_in_a_workbook_stays_under_the_limit_and_imports_by_id(self):
        self.s.con.execute("UPDATE milestones SET name = ? WHERE id = ?", ("Long " * 200, self.demo.milestone))
        self.s.con.commit()
        self.export_again()
        cell = cells(self.path, "Actions", self.a1)["Milestone"]
        self.assertLessEqual(len(cell), excel.REF_CELL_LIMIT)
        self.assertTrue(cell.startswith(self.demo.milestone + ": Long"))

    def test_the_columns_are_wide_enough(self):
        ws = load_workbook(str(self.path))["Actions"]
        head = {c.value: c.column_letter for c in ws[1]}
        self.assertEqual(ws.column_dimensions[head["Milestone"]].width, 40)
        self.assertEqual(ws.column_dimensions[head["Use case"]].width, 40)

    def test_open_work_items_per_sheet(self):
        with self.s.step("dashboard", USER) as st:
            done = st.create("actions", {"project": "ABC", "description": "Finished one", "raised": "2030-01-01",
                                         "status": "Closed", "closed": "2030-01-02", "milestone": self.m2,
                                         "use_case": self.demo.use_case, "source": "demo"})
            risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Open risk", "impact": "Low",
                                      "likelihood": "Low", "raised": "2030-01-01", "milestone": self.m2, "source": "demo"})
            made = st.create("decisions", {"project": "ABC", "decision": "Made one", "date": "2030-01-14",
                                           "use_case": self.demo.use_case, "source": "demo"})
            pend = st.create("decisions", {"project": "ABC", "decision": "Pending one", "status": "Pending",
                                           "needed_by": "2030-07-01", "use_case": self.demo.use_case, "source": "demo"})
        self.export_again()
        self.assertEqual(cells(self.path, "Milestones", self.m2)["Open work items"], risk)
        self.assertEqual(cells(self.path, "Milestones", self.demo.milestone)["Open work items"], self.a1)
        uc = cells(self.path, "Use cases", self.demo.use_case)["Open work items"]
        self.assertEqual(uc, ", ".join(sorted([self.a1, pend])))
        self.assertNotIn(done, uc + risk)
        self.assertNotIn(made, uc)

    def test_open_work_items_is_the_last_column_derived_and_in_the_filter(self):
        self.assertIn("open_items", excel.DERIVED)
        for name in ("Milestones", "Use cases"):
            ws = load_workbook(str(self.path))[name]
            self.assertEqual(ws.cell(1, ws.max_column).value, "Open work items")
            self.assertTrue(ws.auto_filter.ref.startswith("A1:" + ws.cell(1, ws.max_column).column_letter), ws.auto_filter.ref)


class Import(RoundTrip):
    def change_for(self, p, item_id):
        return next((c for c in p.changes if c.id == item_id), None)

    def test_unchanged_id_name_cells_are_no_change(self):
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))

    def test_a_bare_id_still_imports(self):
        edit(self.path, "Actions", self.a2, Milestone=self.m2)
        self.assertEqual(self.change_for(self.read(), self.a2).after, {"milestone": self.m2})

    def test_id_colon_name_imports_as_the_id(self):
        edit(self.path, "Actions", self.a2, Milestone=f"{self.m2}: Slipped milestone",
             **{"Use case": f"{self.demo.use_case}: Whatever"})
        self.assertEqual(self.change_for(self.read(), self.a2).after, {"milestone": self.m2, "use_case": self.demo.use_case})

    def test_a_renamed_name_resolves_by_id_and_is_not_a_change(self):
        edit(self.path, "Actions", self.a1, Milestone=f"{self.demo.milestone}: An old name nobody uses now")
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))

    def test_a_name_containing_colon_space_is_fine(self):
        edit(self.path, "Actions", self.a2, Milestone=f"{self.m2}: Phase 2: go live: really")
        self.assertEqual(self.change_for(self.read(), self.a2).after, {"milestone": self.m2})
        self.assertEqual(xi.resolve_ref("milestone", " ABC-M-001: a: b "), "ABC-M-001")

    def refused(self):
        """The store's refusal of the staged change, as the plan shows it."""
        (c,) = self.read().changes
        return c.problem

    def test_unknown_id_is_refused_with_todays_sentence(self):
        for text in ("ABC-M-999", "ABC-M-999: Ghost"):
            edit(self.path, "Actions", self.a2, Milestone=text)
            self.assertIn("milestone ABC-M-999 isn't here", self.refused())
        edit(self.path, "Actions", self.a2, Milestone=None, **{"Use case": "ABC-U-999: Ghost"})
        self.assertIn("use case ABC-U-999 isn't here", self.refused())

    def test_unknown_text_reaches_the_store_unchanged(self):
        self.assertEqual(xi.resolve_ref("milestone", "Not an id: nope"), "Not an id: nope")
        self.assertEqual(xi.resolve_ref("use_case", "  ABC-U-001  "), "ABC-U-001")

    def test_open_work_items_is_ignored_without_a_note(self):
        edit(self.path, "Milestones", self.m2, **{"Open work items": "ZZZ-A-001"})
        edit(self.path, "Use cases", self.demo.use_case, **{"Open work items": "ZZZ-A-001"})
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))
        self.assertEqual([n for n in p.notes if "ignored" in n or "Open work items" in n], [])

    def test_a_dropdown_pick_applies_and_stores_the_bare_id(self):
        edit(self.path, "Actions", self.a2, Milestone=f"{self.m2}: Slipped milestone")
        p = self.read()
        p.accept_all()
        xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertEqual(next(r for r in self.s.read("actions", "ABC") if r["id"] == self.a2)["milestone"], self.m2)


if __name__ == "__main__":
    unittest.main()
