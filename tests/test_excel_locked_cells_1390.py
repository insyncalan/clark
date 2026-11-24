"""Row 1390 AP2 locked cells. Reads the real built workbook with openpyxl, fictional rows only.

Run: python3 dev/run_tests.py test_excel_locked_cells_1390
"""
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook

from clark import excel
import test_excel as te
from test_excel import setUpModule, tearDownModule  # noqa: F401  (no brand logo on this computer)

LOCKED_GREY = "E7E7E7"


class LockedCells(unittest.TestCase):
    def setUp(self):
        self.d = te.Demo()
        self.addCleanup(self.d.close)
        self.d.demo.plant_builtin_sections()
        self.d.export()

    def test_locked_cells_are_e7e7e7_on_data_rows_only(self):
        wb = load_workbook(self.d.path)
        for name, table, _, _ in excel.SHEETS:
            ws = wb[name]
            n = len(self.d.store.read(table, "ABC"))
            self.assertGreater(n, 0, name)
            locked = 0
            for row in range(2, n + 2):
                for cell in ws[row]:
                    grey = cell.fill.fgColor.rgb[-6:] == LOCKED_GREY if cell.fill.fill_type else False
                    self.assertEqual(grey, cell.protection.locked, (name, cell.coordinate))
                    locked += grey
            self.assertGreater(locked, 0, name)
            for cell in ws[n + 2]:      # the spare row under the data is not grey
                self.assertFalse(cell.fill.fill_type and cell.fill.fgColor.rgb[-6:] == LOCKED_GREY, (name, cell.coordinate))


if __name__ == "__main__":
    unittest.main()
