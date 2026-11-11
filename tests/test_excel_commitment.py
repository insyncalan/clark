"""#709: the Commitment column of the Use cases sheet. The export writes the flag (or a blank); the import reads one of the three
words, REPORTS any other and never guesses it, LEAVES the flag as it is when the cell is empty (a different rule from the other text
cells), and still reads a workbook from before the column.

Run: python3 dev/run_tests.py test_excel_commitment
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
from clark.store import COMMITMENTS

ON = "2030-06-01"
SHEET = "Use cases"
_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")


def setUpModule():
    global _OLD_BRANDING
    _OLD_BRANDING, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD_BRANDING
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


def edit(path, item_id, **cells):
    wb = load_workbook(str(path))
    ws = wb[SHEET]
    head = {c.value: c.column for c in ws[1]}
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == item_id)
    for label, value in cells.items():
        ws.cell(row, head[label]).value = value
    wb.save(str(path))


class Commitment(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.uc = self.demo.use_case
        with self.s.step("dashboard", USER) as st:
            self.other = st.create("use_cases", {"project": "ABC", "title": "Report checks", "status": "Flag", "ref": "1.2",
                                                 "sort_order": 2, "source": "demo", "commitment": "Committed"})
        self.dir = Path(tempfile.mkdtemp(prefix="clark-commit-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(self.demo.close)
        self.path, self.state = self.dir / "ABC work items.xlsx", self.dir / "state.json"
        excel.export_project(self.s, "ABC", self.path, self.state, on=ON)

    def read(self):
        return xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)

    def flag(self, ref):
        return self.s.read("use_cases", ref=ref)["commitment"]

    def cells(self):
        ws = load_workbook(self.path)[SHEET]
        head = [c.value for c in ws[1]]
        return head, {r[0].value: r[head.index("Commitment")].value for r in ws.iter_rows(min_row=2) if r[0].value}

    def test_the_column_is_after_status_and_holds_the_flag_or_a_blank(self):
        head, cells = self.cells()
        self.assertEqual(head[head.index("Status") + 1], "Commitment")
        self.assertEqual(cells, {self.uc: None, self.other: "Committed"})

    def test_the_column_offers_exactly_the_three_words_and_allows_a_blank(self):
        ws = load_workbook(self.path)[SHEET]
        col = [c.value for c in ws[1]].index("Commitment") + 1
        letter = ws.cell(1, col).column_letter
        lists = [v for v in ws.data_validations.dataValidation if letter + "2" in str(v.sqref)]
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].formula1, '"' + ",".join(COMMITMENTS) + '"')
        self.assertTrue(lists[0].allow_blank)

    def test_an_untouched_export_has_no_difference(self):
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))

    def test_each_word_is_read_and_set_in_one_step(self):
        for word in COMMITMENTS:
            with self.subTest(word=word):
                edit(self.path, self.uc, Commitment=word)
                p = self.read()
                (c,) = p.changes
                self.assertEqual((c.kind, c.id, c.after), ("changed", self.uc, {"commitment": word}))
                p.accept_all()
                res = xi.apply_import(self.s, p, USER)
                self.assertTrue(res.applied)
                self.assertEqual(self.flag(self.uc), word)
                with self.s.step("dashboard", USER) as st:
                    st.update("use_cases", self.uc, {"commitment": None})
                excel.export_project(self.s, "ABC", self.path, self.state, on=ON)

    def test_a_word_that_is_not_one_of_the_three_is_reported_naming_the_row_and_the_words_and_not_guessed(self):
        for bad in ("committed", "Planned 2028", "Maybe", "Done", 5):
            with self.subTest(bad=bad):
                edit(self.path, self.uc, Commitment=bad)
                p = self.read()
                self.assertEqual(p.changes, [])
                (problem,) = p.problems
                self.assertEqual(problem.id, self.uc)
                self.assertIn("Use cases, row", problem.message)
                self.assertIn(self.uc, problem.message)
                self.assertIn("Commitment must be one of Planned 2026, Committed or Planned 2027, or left empty", problem.message)
                self.assertIn("the row was left out", problem.message)
                self.assertIsNone(self.flag(self.uc))

    def test_an_empty_cell_leaves_the_flag_as_it_is(self):
        edit(self.path, self.other, Commitment=None)
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))
        p.accept_all()
        xi.apply_import(self.s, p, USER)
        self.assertEqual(self.flag(self.other), "Committed")

    def test_an_empty_cell_still_lets_the_rest_of_the_row_change_and_keeps_the_flag(self):
        edit(self.path, self.other, Commitment=None, Headline="Two left")
        p = self.read()
        (c,) = p.changes
        self.assertEqual(c.after, {"headline": "Two left"})
        p.accept_all()
        xi.apply_import(self.s, p, USER)
        self.assertEqual((self.flag(self.other), self.s.read("use_cases", ref=self.other)["headline"]), ("Committed", "Two left"))

    def test_a_flag_can_be_changed_from_one_word_to_another(self):
        edit(self.path, self.other, Commitment="Planned 2027")
        p = self.read()
        (c,) = p.changes
        self.assertEqual((c.before, c.after), ({"commitment": "Committed"}, {"commitment": "Planned 2027"}))

    def test_a_new_row_may_carry_a_word_and_a_bad_word_is_reported(self):
        wb = load_workbook(self.path)
        ws = wb[SHEET]
        head = {c.value: c.column for c in ws[1]}
        row = ws.max_row + 1
        ws.cell(row, head["Use case"]).value, ws.cell(row, head["Commitment"]).value = "A typed one", "Planned 2026"
        ws.cell(row + 1, head["Use case"]).value, ws.cell(row + 1, head["Commitment"]).value = "A bad one", "Soon"
        wb.save(str(self.path))
        p = self.read()
        news = [c for c in p.changes if c.kind == "new"]
        self.assertEqual([c.after.get("commitment") for c in news], ["Planned 2026"])
        self.assertEqual(len(p.problems), 1)
        self.assertIn("(new)", p.problems[0].message)

    def test_spaces_round_a_word_are_not_part_of_it(self):
        edit(self.path, self.uc, Commitment="  Planned 2026 ")
        (c,) = self.read().changes
        self.assertEqual(c.after, {"commitment": "Planned 2026"})

    def test_a_workbook_from_before_the_column_imports_as_before_and_keeps_every_flag(self):
        wb = load_workbook(self.path)
        ws = wb[SHEET]
        col = [c.value for c in ws[1]].index("Commitment") + 1
        ws.delete_cols(col)
        wb.save(str(self.path))
        edit(self.path, self.uc, Headline="Late")
        p = self.read()
        self.assertEqual(p.problems, [])
        (c,) = p.changes
        self.assertEqual((c.id, c.after), (self.uc, {"headline": "Late"}))
        p.accept_all()
        xi.apply_import(self.s, p, USER)
        self.assertEqual(self.flag(self.other), "Committed")


if __name__ == "__main__":
    unittest.main()
