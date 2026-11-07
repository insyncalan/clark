"""Row 966: the Excel import refuses a hostile workbook while it is streamed, before openpyxl loads it whole. The fixtures are built
here (a real export with one part rewritten); nothing big is committed."""
import re
import shutil
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _demo import DemoStore
import _workbook as wbk
from clark import excel_import as xi
from clark.store import Invalid

HEAD = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:B2"/><sheetData>')
TAIL = '</sheetData></worksheet>'


class Loaded(BaseException):
    """Raised by the stand-in for openpyxl's load_workbook: the early check did not refuse."""


def part_of(path, title):
    with zipfile.ZipFile(path) as z:
        book = z.read("xl/workbook.xml").decode()
        rels = z.read("xl/_rels/workbook.xml.rels").decode()
    rid = re.search(r'<sheet\b[^>]*name="%s"[^>]*r:id="([^"]+)"' % re.escape(title), book).group(1)
    target = re.search(r'<Relationship\b[^>]*Id="%s"[^>]*Target="([^"]+)"' % rid, rels) or re.search(
        r'<Relationship\b[^>]*Target="([^"]+)"[^>]*Id="%s"' % rid, rels)
    t = target.group(1)
    return t.lstrip("/") if t.startswith("/") else "xl/" + t


def rewrite(path, member, data):
    """Replace one part of the zip with `data` (str or bytes); the rest is copied."""
    out = Path(str(path) + ".new")
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, data if info.filename == member else src.read(info.filename))
        if member not in src.namelist():
            dst.writestr(member, data)
    out.replace(path)


def letters(n):
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def rows_xml(rows, cols=2, text="x"):
    return "".join('<row r="%d">%s</row>' % (r, "".join('<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>' % (letters(c), r, text)
                                                       for c in range(1, cols + 1))) for r in range(1, rows + 1))


class Caps(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-caps-"))
        self.path = wbk.make_workbook(self.s, self.tmp / "ABC.xlsx")
        self.load = mock.patch.object(xi, "load_workbook", side_effect=Loaded)
        self.load.start()

    def tearDown(self):
        self.load.stop()
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self, **kw):
        return xi.read_workbook(self.s, self.path, "ABC", allow_unrecorded=True, **kw)

    def refused(self, **kw):
        t0 = time.process_time()
        with self.assertRaises(Invalid) as cm:
            self.plan(**kw)
        self.assertLess(time.process_time() - t0, 5)
        return str(cm.exception)

    def test_a_sheet_that_says_a1_b2_and_holds_300000_rows_is_refused_before_the_load(self):
        rewrite(self.path, part_of(self.path, "Actions"), HEAD + rows_xml(300000) + TAIL)
        text = self.refused()
        self.assertIn("The Actions sheet reaches past row 5,000", text)
        self.assertIn("Nothing was changed", text)

    def test_a_sheet_that_says_a1_b2_and_holds_too_many_cells_inside_the_reach_is_refused_before_the_load(self):
        rewrite(self.path, part_of(self.path, "Actions"), HEAD + rows_xml(4000, cols=60) + TAIL)      # 240,000 cells in 4,000 x 60
        text = self.refused()
        self.assertIn("The Actions sheet is too large (4,000 rows by 60 columns", text)

    def test_cells_far_to_the_right_are_refused_before_the_load(self):
        rewrite(self.path, part_of(self.path, "Decisions"), HEAD + '<row r="3"><c r="CW3"><v>1</v></c></row>' + TAIL)
        self.assertIn("The Decisions sheet reaches past row 5,000 or column 100", self.refused())

    def test_sheets_each_inside_the_limit_but_too_large_together_are_refused_before_the_load(self):
        for name in ("Actions", "RAID", "Decisions"):
            rewrite(self.path, part_of(self.path, name), HEAD + '<row r="1900"><c r="CV1900"><v>1</v></c></row>' + TAIL)
        self.assertIn("too large together", self.refused())

    def test_a_30_mb_text_in_the_shared_strings_is_refused_before_the_load(self):
        rewrite(self.path, "xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<si><t>%s</t></si></sst>' % ("x" * 30_000_000))
        self.assertIn("can't be read as an Excel workbook (.xlsx)", self.refused())

    def test_a_30_mb_inline_text_in_a_sheet_is_refused_before_the_load(self):
        rewrite(self.path, part_of(self.path, "Actions"), HEAD + rows_xml(1, cols=1, text="y" * 30_000_000) + TAIL)
        self.assertIn("can't be read as an Excel workbook (.xlsx)", self.refused())

    def test_a_text_over_what_excel_keeps_is_refused_but_one_under_it_goes_on_to_the_row_check(self):
        for size, refused in ((xi.MAX_CELL_TEXT + 1, True), (xi.MAX_TEXT + 1, False)):
            path = self.tmp / ("t%d.xlsx" % size)
            shutil.copy(self.path, path)
            rewrite(path, "xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<si><t>%s</t></si></sst>' % ("z" * size))
            if refused:
                with self.assertRaises(Invalid):
                    xi.check_sheets_early(path, lambda t: True)
            else:
                xi.check_sheets_early(path, lambda t: True)          # MAX_TEXT still refuses that cell's row, after the load, as before

    def test_a_hostile_sheet_the_import_does_not_read_is_left_to_the_ordinary_path(self):
        rewrite(self.path, part_of(self.path, "Actions"), HEAD + rows_xml(300000) + TAIL)
        with self.assertRaises(Loaded):
            self.plan(sheets={xi.SHEET_TABLES["decisions"]})        # only Decisions is read; Actions is not looked at

    def test_a_normal_export_passes_the_early_check_and_is_loaded(self):
        with self.assertRaises(Loaded):
            self.plan()

    def test_tags_and_texts_split_across_chunks_are_counted_the_same(self):
        rewrite(self.path, part_of(self.path, "Actions"), HEAD + rows_xml(300000) + TAIL)
        for chunk in (7, 64, 65536):
            with mock.patch.object(xi, "_SCAN_CHUNK", chunk):
                self.assertIn("reaches past row 5,000", self.refused())
        small = self.tmp / "small.xlsx"
        shutil.copy(self.path, small)
        rewrite(small, part_of(small, "Actions"), HEAD + rows_xml(30, cols=3, text="a&amp;b") + TAIL)
        for chunk in (1, 3, 7, 100, 65536):
            with mock.patch.object(xi, "_SCAN_CHUNK", chunk), zipfile.ZipFile(small) as z:
                self.assertEqual(xi._scan_member(z, part_of(small, "Actions"), "Actions"), (30, 3))


if __name__ == "__main__":
    unittest.main()
