"""#1366 slice (c): the index reads PDF and Excel (vendored pypdf through pdf_reader, vendored openpyxl). Made-up files only.
Pictures, PowerPoint, HTML and OCR are not in this slice."""
import io
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from test_ask_pdf_passages import FAKE_PYPDF, pdf
from clark import pdf_reader


def xlsx(sheets):
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


class Types(Base):
    def setUp(self):
        super().setUp()
        v = self.d / "vendor"
        (v / "pypdf").mkdir(parents=True)
        (v / "pypdf" / "__init__.py").write_text(FAKE_PYPDF, encoding="utf-8")
        p = mock.patch.object(pdf_reader, "VENDOR", v)
        p.start()
        self.addCleanup(p.stop)

    def test_pdf_pages_are_found_with_their_page_number(self):
        self.put("plan.pdf", pdf(["zqpdfone first", "zqpdftwo second"]), binary=True)
        self.build()
        got = self.found("zqpdftwo")
        self.assertEqual(len(got), 1)
        self.assertIn("plan.pdf, page 2", got[0][0])
        self.assertEqual(ix.status(self.data, "P1", [self.box])["indexed"], 1)

    def test_a_scanned_pdf_is_left_out_with_a_plain_reason(self):
        self.put("scan.pdf", pdf([None, None]), binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["indexed"], s["type"]), (0, 1))
        out = ix.mod().files_left_out(self.data, "P1", 200)
        self.assertEqual([n for n, _ in out["files"]], ["saved/scan.pdf"])

    def test_excel_cells_are_found_with_sheet_name(self):
        self.put("budget.xlsx", xlsx({"Plan": [["item", "owner"], ["zqxlone", "Ana"]], "Late": [["zqxltwo", 42]]}), binary=True)
        self.build()
        a, b = self.found("zqxlone"), self.found("zqxltwo")
        self.assertEqual((len(a), len(b)), (1, 1))
        self.assertIn("Plan", a[0][0])
        self.assertIn("Late", b[0][0])
        self.assertIn("zqxlone", a[0][1])

    def test_excel_formulas_give_their_stored_values_not_the_formula(self):
        self.put("f.xlsx", xlsx({"S": [[1, 2, "=A1+B1"], ["zqxlname"]]}), binary=True)
        self.build()
        self.assertTrue(self.found("zqxlname"))
        self.assertFalse(self.found("A1"))

    def test_a_damaged_excel_file_is_left_out_not_an_error(self):
        self.put("bad.xlsx", b"PK\x03\x04 not really", binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual(s["indexed"], 0)
        self.assertEqual(sum(s[k] for k in ("type", "safety")), 1)

    def test_a_secret_in_a_cell_keeps_the_whole_file_out(self):
        self.put("k.xlsx", xlsx({"S": [["zqxlkey"], ["password = " + "hunter2" * 3]]}), binary=True)
        self.build()
        self.assertFalse(self.found("zqxlkey"))
        self.assertEqual(ix.status(self.data, "P1", [self.box])["safety"], 1)

    def test_pdf_and_excel_follow_a_refresh(self):
        p = self.put("a.xlsx", xlsx({"S": [["zqxlold"]]}), binary=True)
        self.build()
        self.put("a.xlsx", xlsx({"S": [["zqxlnew word"]]}), binary=True)
        import os
        os.utime(p, (1, 1))
        ix.refresh(self.data, "P1", [self.box])
        self.assertFalse(self.found("zqxlold"))
        self.assertTrue(self.found("zqxlnew"))


if __name__ == "__main__":
    unittest.main()
