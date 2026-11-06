"""Row 839: a date before 1900-01-01 is dd-mm-yyyy text in the Excel files,
never a negative date serial (which Excel shows as ####).

Run: python3 dev/run_tests.py test_excel_pre1900
Reads the saved .xlsx (zip and XML) of both the editor export and the client workbook.
"""
import io
import re
import unittest
import zipfile
from datetime import date

from _paths import ROOT, SRC, TOOLS  # noqa: F401

import _publish_fixture as fx  # noqa: E402
from openpyxl import Workbook, load_workbook  # noqa: E402
from clark import excel, excel_client, publish  # noqa: E402

CASES = [("1850-01-01", "01-01-1850", None), ("0001-01-01", "01-01-0001", None), ("1899-12-31", "31-12-1899", None),
         ("1900-01-01", None, "1"), ("1900-02-28", None, "59"), ("1900-03-01", None, "61"), ("2026-11-05", None, "46331"),
         ("9999-12-31", None, "2958465")]


def cells_of(wb):
    """Each cell of A1.. as (type attribute, raw text) from the saved XML."""
    buf = io.BytesIO()
    wb.save(buf)
    z = zipfile.ZipFile(buf)
    xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    strings = re.findall(r"<si>.*?<t[^>]*>(.*?)</t>", z.read("xl/sharedStrings.xml").decode("utf-8"), re.S) if "xl/sharedStrings.xml" in z.namelist() else []
    out = {}
    for ref, attrs, body in re.findall(r'<c r="([A-Z]+\d+)"([^>]*?)(?:/>|>(.*?)</c>)', xml, re.S):
        t = re.search(r't="(\w+)"', attrs)
        v = re.search(r"<(?:v|t[^>]*)>(.*?)</(?:v|t)>", body or "", re.S)
        out[ref] = (t.group(1) if t else "n", v.group(1) if v else None)
    return out, strings


class ToCell(unittest.TestCase):
    def test_cell_types_in_the_saved_file(self):
        wb = Workbook()
        ws = wb.active
        for i, (iso, _, _) in enumerate(CASES, start=1):
            c = ws.cell(row=i, column=1, value=excel.to_cell("date", iso))
            c.number_format = excel.DATE_FORMAT
            excel.protect_text_cell(c)
        cells, _ = cells_of(wb)
        for i, (iso, text, serial) in enumerate(CASES, start=1):
            t, v = cells[f"A{i}"]
            if text:
                self.assertEqual(t, "inlineStr", iso)
                self.assertEqual(v, text, iso)
            else:
                self.assertEqual((t, v), ("n", serial), iso)

    def test_invalid_and_empty_are_unchanged(self):
        self.assertIsNone(excel.to_cell("date", None))
        self.assertEqual(excel.to_cell("date", "soon"), "soon")
        self.assertEqual(excel.to_cell("date", "=1+1"), excel.escape_text("=1+1"))

    def test_text_date_reads_back_as_the_same_day(self):
        self.assertEqual(excel.from_cell("date", excel.to_cell("date", "1850-01-01")), "1850-01-01")
        self.assertEqual(excel.from_cell("date", excel.to_cell("date", "0001-01-01")), "0001-01-01")


class ClientWorkbook(unittest.TestCase):
    def test_client_sheet_has_text_for_an_old_due_date(self):
        plant = fx.load()
        pub = publish.select(fx.inputs(plant))
        first = next(r for r in pub["data"]["actions"] if r.get("due_date"))
        first["due_date"] = "1850-01-01"
        book = load_workbook(io.BytesIO(excel_client.workbook_bytes(pub)))
        ws = book[excel.SHEET_OF["actions"]]
        col = [c for c in range(1, ws.max_column + 1) if ws.cell(4, c).value == "Due"][0]
        row = pub["data"]["actions"].index(first) + 5
        self.assertEqual(ws.cell(row, col).value, "01-01-1850")
        self.assertEqual(ws.cell(row, col).data_type, "s")

    def test_week_ending_subtitle_for_old_and_normal_dates(self):
        for iso, shown in (("1850-01-01", "01-01-1850"), ("2026-11-05", "05-11-2026")):
            pub = {"data": {"project": {"name": "P", "week_ending": iso}}, "as_at": "x"}
            self.assertEqual(excel_client.title_text(pub), ("P", "Week ending " + shown))

    def test_two_exports_are_byte_identical(self):
        plant = fx.load()
        pub = publish.select(fx.inputs(plant))
        pub["data"]["actions"][0]["due_date"] = "1850-01-01"
        self.assertEqual(excel_client.workbook_bytes(pub), excel_client.workbook_bytes(pub))


if __name__ == "__main__":
    unittest.main()
