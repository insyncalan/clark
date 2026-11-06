"""Row 768: the client workbook's dates sit at the left of their column (so they do not run into the next column's text), and every
date column is wide enough for the longest date.

Run: python3 dev/run_tests.py test_excel_client_layout
"""
import io
import unittest
import zipfile
import xml.etree.ElementTree as ET

from _paths import ROOT, SRC, TOOLS  # noqa: F401

import _publish_fixture as fx  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from clark import excel, excel_client, publish  # noqa: E402

LONGEST_DATE = len("30-12-2026")


class Layout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plant = fx.load()
        cls.wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(fx.inputs(plant)))))

    def date_columns(self):
        for ws in self.wb.worksheets:
            for c in range(1, ws.max_column + 1):
                if ws.cell(4, c).value and any(ws.cell(r, c).number_format == excel.DATE_FORMAT for r in range(5, ws.max_row + 1)):
                    yield ws, c

    def test_there_are_date_columns_to_check(self):
        self.assertGreaterEqual(len(list(self.date_columns())), 4)

    def test_dates_are_left_aligned_and_a_date_format(self):
        for ws, c in self.date_columns():
            for r in range(5, ws.max_row + 1):
                cell = ws.cell(r, c)
                if cell.value is not None:
                    self.assertEqual(cell.alignment.horizontal, "left", f"{ws.title} {cell.coordinate}")
                    self.assertEqual(cell.number_format, "dd-mm-yyyy")

    def test_date_columns_hold_the_longest_date_with_a_gap(self):
        for ws, c in self.date_columns():
            self.assertGreaterEqual(ws.column_dimensions[get_column_letter(c)].width, LONGEST_DATE + 2, f"{ws.title} {ws.cell(4, c).value}")


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sheet_xmls(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return [ET.fromstring(z.read(n)) for n in sorted(z.namelist()) if n.startswith("xl/worksheets/sheet")]


class PrintSetup(unittest.TestCase):
    """Row 911: every sheet of the client workbook prints A4, landscape, one page wide (as the editor workbook, row 801)."""

    def check(self, data, count=None):
        sheets = sheet_xmls(data)
        self.assertTrue(sheets)
        if count is not None:
            self.assertEqual(len(sheets), count)
        for root in sheets:
            setup = root.find("m:pageSetup", NS)
            self.assertEqual((setup.get("orientation"), setup.get("paperSize"), setup.get("fitToWidth"), setup.get("fitToHeight")),
                             ("landscape", "9", "1", "0"))
            self.assertEqual(root.find("m:sheetPr/m:pageSetUpPr", NS).get("fitToPage"), "1")

    def test_every_sheet_of_the_client_workbook(self):
        pub = publish.select(fx.inputs(fx.load()))
        self.check(excel_client.workbook_bytes(pub), len(excel_client.sheet_tables(pub)))

    def test_the_nothing_to_show_page(self):
        pub = publish.select(fx.inputs(fx.load()))
        pub["sections"] = []
        self.check(excel_client.workbook_bytes(pub), 1)


if __name__ == "__main__":
    unittest.main()
