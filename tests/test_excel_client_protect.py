"""Row 768: each sheet of the client workbook is protected with no password and the same allowed actions as the export's sheets
(item 727), and a cell is locked by the export's own rule (excel.locked_fields): the ID, the Project and the columns clark works out
(Shown state, Original) stay locked; the others are the ones the export leaves editable. The workbook structure is not protected.
The file the published page embeds carries the same protection.

Run: python3 dev/run_tests.py test_excel_client_protect
"""
import base64
import io
import unittest

from _paths import ROOT, SRC, TOOLS  # noqa: F401

import _publish_fixture as fx  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from openpyxl.worksheet.protection import SheetProtection  # noqa: E402
from clark import excel, excel_client, publish  # noqa: E402


def published():
    return publish.select(fx.inputs(fx.load()))


def sheets(wb):
    return {ws.title: ws for ws in wb.worksheets}


class Protect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub = published()
        cls.wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(cls.pub)))

    def check_protected(self, wb):
        self.assertTrue(wb.worksheets)
        for ws in wb.worksheets:
            p = ws.protection
            self.assertTrue(p.sheet, ws.title)
            self.assertFalse(p.password, ws.title)
            self.assertFalse(getattr(p, "hashValue", None), ws.title)
            for flag in excel.ALLOWED_ON_PROTECTED:
                self.assertFalse(getattr(p, flag), f"{ws.title} {flag}")
            self.assertTrue(p.sort, ws.title)          # True: sorting is not allowed
            self.assertTrue(p.deleteRows, ws.title)

    def test_every_sheet_is_protected_with_no_password_and_the_export_actions(self):
        self.check_protected(self.wb)

    def test_the_actions_are_those_of_an_export_sheet(self):
        ref = SheetProtection(sheet=True)
        for name in excel.ALLOWED_ON_PROTECTED:
            setattr(ref, name, False)
        for ws in self.wb.worksheets:
            self.assertEqual(dict(ws.protection), dict(ref), ws.title)

    def test_locked_cells_follow_the_exports_rule_per_column(self):
        seen = 0
        own = {t: l for _, t, _, l in excel.SHEETS}
        for table in excel_client.sheet_tables(self.pub):
            ws = sheets(self.wb)[excel.SHEET_OF[table]]
            locked = excel.locked_fields(own[table])
            for i, (label, field, _) in enumerate(excel_client.columns(table), start=1):
                want = {"state_word": "shown_state"}.get(field, field) in locked
                for r in range(5, ws.max_row + 1):
                    self.assertEqual(ws.cell(row=r, column=i).protection.locked, want, f"{ws.title} {label} row {r}")
                    seen += 1
                for r in (1, 2, 4):           # the title band and the header row are never editable
                    self.assertTrue(ws.cell(row=r, column=i).protection.locked, f"{ws.title} {label} row {r}")
        self.assertGreater(seen, 10)

    def test_locked_cells_are_grey_and_editable_ones_are_not(self):
        """Item 1157: the shade follows the lock, on every data sheet."""
        grey = excel.colours.TOKENS["grey-100"]
        seen = 0
        for ws in self.wb.worksheets:
            for row in ws.iter_rows(min_row=5):
                for c in row:
                    shade = c.fill.fgColor.rgb[-6:] if c.fill.fill_type == "solid" else None
                    if c.protection.locked and ws.title != "Gantt":
                        self.assertEqual(shade, grey, f"{ws.title} {c.coordinate}")
                    elif not c.protection.locked:
                        self.assertNotEqual(shade, grey, f"{ws.title} {c.coordinate}")
                    seen += 1
        self.assertGreater(seen, 10)

    def test_the_id_and_the_worked_out_columns_are_locked_and_text_is_not(self):
        for ws in self.wb.worksheets:
            heads = {c.value: c.column for c in ws[4]}
            self.assertTrue(ws.cell(row=5, column=heads["ID"]).protection.locked, ws.title)
            for label in ("Original", "Shown state"):
                if label in heads:
                    self.assertTrue(ws.cell(row=5, column=heads[label]).protection.locked, f"{ws.title} {label}")
        acts = sheets(self.wb)[excel.SHEET_OF["actions"]]
        heads = {c.value: c.column for c in acts[4]}
        self.assertFalse(acts.cell(row=5, column=heads["Description"]).protection.locked)

    def test_the_workbook_structure_is_not_protected(self):
        self.assertFalse(self.wb.security and (self.wb.security.lockStructure or self.wb.security.lockWindows))

    def test_the_empty_case_sheet_is_protected(self):
        pub = published()
        pub["sections"] = []
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(pub)))
        self.assertEqual(len(wb.worksheets), 1)
        self.check_protected(wb)

    def test_the_embedded_file_carries_the_protection(self):
        got = excel_client.embed(self.pub)["client_workbook"]
        wb = load_workbook(io.BytesIO(base64.b64decode(got["base64"], validate=True)))
        self.check_protected(wb)
        acts = sheets(wb)[excel.SHEET_OF["actions"]]
        self.assertTrue(acts["A5"].protection.locked)


if __name__ == "__main__":
    unittest.main()
