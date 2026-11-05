"""Row 768: each sheet of the client workbook is protected with no password as the export's sheets are (item 727), with every cell
locked because the file is read-only.

Run: python3 dev/run_tests.py test_excel_client_protect
"""
import io
import unittest

from _paths import ROOT, SRC, TOOLS  # noqa: F401

import _publish_fixture as fx  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from clark import excel, excel_client, publish  # noqa: E402


class Protect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(fx.inputs(fx.load())))))

    def test_every_sheet_is_protected_with_no_password_and_every_cell_locked(self):
        for ws in self.wb.worksheets:
            p = ws.protection
            self.assertTrue(p.sheet, ws.title)
            self.assertFalse(p.password, ws.title)
            for flag in excel.ALLOWED_ON_PROTECTED:
                self.assertFalse(getattr(p, flag), f"{ws.title} {flag}")
            self.assertTrue(p.sort, ws.title)          # True: sorting is not allowed
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
                for cell in row:
                    self.assertTrue(cell.protection.locked, f"{ws.title} {cell.coordinate}")

    def test_the_workbook_structure_is_not_protected(self):
        self.assertFalse(self.wb.security and (self.wb.security.lockStructure or self.wb.security.lockWindows))


if __name__ == "__main__":
    unittest.main()
