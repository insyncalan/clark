"""Item 727: every sheet of the export is protected with no password; the ID, the Project and the columns clark works out are
locked, the rest of a data sheet (and its blank rows for new items) is not. The import never reads the protection.

Run: python3 dev/run_tests.py test_excel_protection
"""
import re
import shutil
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import USER, DemoStore
from openpyxl import load_workbook

from clark import excel
from clark import excel_cover
from clark import excel_import as xi
from clark import page

ON = "2030-06-01"
_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")


def setUpModule():
    global _OLD
    _OLD, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


LOCKED_LABELS = {
    "Actions": {"ID", "Project", "Source", "Updated"},
    "Risks & Issues": {"ID", "Project", "Priority", "Source", "Updated"},
    "Decisions": {"ID", "Project", "Source", "Updated"},
    "Milestones": {"ID", "Project", "Original", "Shown state", "Open work items", "Source", "Updated"},
    "Use cases": {"ID", "Project", "Open work items", "Source", "Updated"},
}
DATA = tuple(LOCKED_LABELS)


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-protect-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        with self.demo.store.step("dashboard", USER) as st:
            self.a1 = st.create("actions", {"project": "ABC", "description": "Draft the plan", "raised": "2030-01-10",
                                            "owner": "Sample Owner", "source": "demo"})
        self.path, self.state = self.dir / "w.xlsx", self.dir / "s.json"
        excel.export_project(self.demo.store, "ABC", self.path, self.state, on=ON)
        self.wb = load_workbook(str(self.path))


class Protected(Base):
    def test_every_sheet_is_protected_with_no_password(self):
        self.assertEqual(self.wb.sheetnames[0], "Cover")
        for ws in self.wb.worksheets:
            p = ws.protection
            self.assertTrue(p.sheet, ws.title)
            self.assertFalse(p.password, ws.title)
            self.assertFalse(p.hashValue, ws.title)
        with zipfile.ZipFile(self.path) as z:
            for n in z.namelist():
                if n.startswith("xl/worksheets/sheet"):
                    xml = z.read(n).decode()
                    tag = re.search(r"<sheetProtection[^>]*>", xml)
                    self.assertTrue(tag, n)
                    self.assertIn('sheet="1"', tag.group(0))
                    for attr in ("password", "hashValue", "saltValue", "algorithmName"):
                        self.assertNotIn(attr, tag.group(0))

    def test_cover_history_and_lists_are_fully_locked(self):
        for name in ("Cover", "History", "Lists"):
            ws = self.wb[name]
            for row in ws.iter_rows():
                for c in row:
                    self.assertTrue(c.protection.locked, f"{name} {c.coordinate}")
        self.assertEqual(self.wb["Lists"].sheet_state, "hidden")

    def test_the_exact_locked_columns_on_each_data_sheet(self):
        for name in DATA:
            ws = self.wb[name]
            last = ws.max_row
            self.assertGreater(last, 500, "the blank formatted rows are there")
            labels = [c.value for c in ws[1]]
            self.assertEqual({lab for lab in labels if lab in LOCKED_LABELS[name]}, LOCKED_LABELS[name])
            for col, label in enumerate(labels, start=1):
                locked = label in LOCKED_LABELS[name]
                self.assertTrue(ws.cell(1, col).protection.locked, f"{name} header {label}")
                for r in (2, 3, 4, last):
                    self.assertEqual(ws.cell(r, col).protection.locked, locked, f"{name} {label} row {r}")

    def test_every_locked_column_has_the_grey_fill_on_its_data_rows_and_no_other_does(self):
        """Item 1157: the Project and the worked-out columns are grey too, not only the sheet's own locked set."""
        grey = excel.colours.TOKENS["grey-100"]
        seen = 0
        for name in DATA:
            ws = self.wb[name]
            for col, label in enumerate([c.value for c in ws[1]], start=1):
                for r in range(2, ws.max_row + 1):
                    c = ws.cell(r, col)
                    if c.value is None:
                        continue
                    shade = c.fill.fgColor.rgb[-6:] if c.fill.fill_type == "solid" else None
                    self.assertEqual(shade == grey, label in LOCKED_LABELS[name], f"{name} {label} row {r}")
                    seen += 1
        self.assertGreater(seen, 10)

    def test_the_id_of_a_blank_row_stays_locked_and_the_rest_are_editable(self):
        ws = self.wb["Actions"]
        blank = 3                        # one action: row 2 is its data, row 3 the first blank row
        self.assertIsNone(ws.cell(blank, 1).value)
        self.assertTrue(ws.cell(blank, 1).protection.locked)
        labels = [c.value for c in ws[1]]
        for label in ("Description", "Owner", "Priority", "Due", "Status", "Client wording", "Milestone", "Use case", "Labels"):
            self.assertFalse(ws.cell(blank, labels.index(label) + 1).protection.locked, label)

    def test_the_commitment_column_is_editable_and_keeps_its_drop_down_on_a_protected_sheet(self):
        ws = self.wb["Use cases"]
        self.assertTrue(ws.protection.sheet)
        labels = [c.value for c in ws[1]]
        col = labels.index("Commitment") + 1
        letter = ws.cell(1, col).column_letter
        for r in (2, 3, ws.max_row):
            self.assertFalse(ws.cell(r, col).protection.locked, f"Commitment row {r}")
        rules = [dv for dv in ws.data_validations.dataValidation if f"{letter}2" in str(dv.sqref)]
        self.assertTrue(rules, "the drop-down is still on the Commitment column")
        self.assertIn("Planned 2027", rules[0].formula1)

    def test_a_column_that_is_not_locked_is_editable_by_design(self):
        self.assertEqual(excel.locked_fields({"id"}), {"id", "project", "original_date", "shown_state", "open_items"})
        self.assertNotIn("commitment", excel.locked_fields({"id", "source"}))

    def test_the_allowed_actions(self):
        for ws in self.wb.worksheets:
            p = ws.protection          # in openpyxl True means the action is NOT allowed
            for flag in ("autoFilter", "formatCells", "formatColumns", "formatRows", "insertRows",
                         "selectLockedCells", "selectUnlockedCells"):
                self.assertFalse(getattr(p, flag), f"{ws.title} {flag}")
            for flag in ("sort", "deleteRows", "deleteColumns", "insertColumns", "pivotTables"):
                self.assertTrue(getattr(p, flag), f"{ws.title} {flag}")

    def test_the_workbook_structure_is_not_protected(self):
        self.assertFalse(self.wb.security.lockStructure)
        self.assertFalse(self.wb.security.lockWindows)

    def test_drop_downs_filters_panes_and_rules_stay(self):
        ws = self.wb["Actions"]
        rules = ws.data_validations.dataValidation
        self.assertIn("list", {dv.type for dv in rules})
        self.assertTrue(any("Lists!" in (dv.formula1 or "") for dv in rules))
        self.assertTrue(ws.auto_filter.ref)
        self.assertTrue(ws.freeze_panes)
        self.assertTrue(ws.conditional_formatting)

    def test_the_cover_line(self):
        want = ("Some cells are locked so they are not changed by mistake, such as the ID column and the columns clark works out. "
                "To change them, choose Review, then Unprotect Sheet. There is no password. "
                "Excel will not sort a protected sheet; unprotect it first.")
        self.assertEqual(excel_cover.LOCKED_CELLS, want)
        texts = [c.value for row in self.wb["Cover"].iter_rows() for c in row if c.value]
        self.assertIn("Locked cells", texts)
        self.assertEqual(texts.count(want), 1)


class RoundTrip(Base):
    def read(self):
        return xi.read_workbook(self.demo.store, self.path, "ABC", state_path=self.state)

    def kinds(self):
        return [c.kind for c in self.read().changes if c.kind != "unchanged"]

    def test_an_edit_of_an_editable_cell_arrives(self):
        ws = self.wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        ws.cell(2, head["Owner"]).value = "Sam Example"
        ws.cell(2, head["Due"]).value = date(2030, 5, 20)
        self.wb.save(str(self.path))
        self.assertEqual(self.kinds(), ["changed"])

    def test_a_new_row_with_an_empty_id_is_added(self):
        ws = self.wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        ws.cell(3, head["Description"]).value = "A new item"
        self.wb.save(str(self.path))
        self.assertIn("new", self.kinds())

    def test_a_workbook_whose_protection_was_removed_still_imports(self):
        for ws in self.wb.worksheets:
            ws.protection.sheet = False
        ws = self.wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        ws.cell(2, head["Updated"]).value = "yesterday"          # a locked cell, changed by someone who unprotected the sheet
        ws.cell(2, head["Owner"]).value = "Sam Example"
        self.wb.save(str(self.path))
        self.assertIn("changed", self.kinds())

    def test_an_old_unprotected_workbook_imports(self):
        for ws in self.wb.worksheets:
            ws.protection.sheet = False
        self.wb.save(str(self.path))
        self.assertEqual(self.kinds(), [])

    def test_the_same_export_again_keeps_its_id(self):
        first = excel.export_id_of(self.path)
        excel.export_project(self.demo.store, "ABC", self.path, self.state, on=ON)
        self.assertTrue(first)
        self.assertEqual(excel.export_id_of(self.path), first)


if __name__ == "__main__":
    unittest.main()
