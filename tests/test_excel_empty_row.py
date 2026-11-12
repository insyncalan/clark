"""Row 1028: an empty <row r="6000"> (no cell in it) does not move the reach of a sheet in the streamed early check
(excel_import._scan_member), so a workbook with one imports; a cell at row 6000 is still refused, and so is a flood of row tags."""
import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _demo import DemoStore
import _workbook as wbk
from clark import excel_import as xi
from clark.store import Invalid
from test_excel_import_caps import HEAD, TAIL, Loaded, part_of, rewrite

LIMIT = xi.MAX_SHEET_ROWS


def scan(xml, chunk=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/p.xml", xml)
    with zipfile.ZipFile(buf) as z:
        if chunk:
            with mock.patch.object(xi, "_SCAN_CHUNK", chunk):
                return xi._scan_member(z, "xl/p.xml", "Actions")
        return xi._scan_member(z, "xl/p.xml", "Actions")


CELL = '<row r="2"><c r="A2" t="inlineStr"><is><t>x</t></is></c></row>'


class EmptyRow(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-emptyrow-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.path = wbk.make_workbook(self.demo.store, self.tmp / "ABC.xlsx")
        p = mock.patch.object(xi, "load_workbook", side_effect=Loaded)
        p.start()
        self.addCleanup(p.stop)

    def plan(self):
        return xi.read_workbook(self.demo.store, self.path, "ABC", allow_unrecorded=True)

    def test_an_empty_row_at_6000_does_not_refuse_the_workbook(self):
        for how, row in (("self-closed", '<row r="6000"/>'), ("open and close", '<row r="6000"></row>'),
                         ("with attributes", '<row r="6000" spans="1:2" ht="15" customHeight="1"/>')):
            with self.subTest(how=how):
                rewrite(self.path, part_of(self.path, "Actions"), HEAD + CELL + row + TAIL)
                with self.assertRaises(Loaded):          # past the early check, on to the real load
                    self.plan()

    def test_a_cell_at_row_6000_is_still_refused(self):
        for how, rows in (("in a numbered row", '<row r="6000"><c r="A6000"><v>1</v></c></row>'),
                          ("cell alone in an empty-numbered row", '<row r="6000"><c><v>1</v></c></row>'),
                          ("row 6000 emptied then a cell with no r after it", '<row r="6000"/><row><c><v>1</v></c></row>')):
            with self.subTest(how=how):
                rewrite(self.path, part_of(self.path, "Actions"), HEAD + CELL + rows + TAIL)
                with self.assertRaises(Invalid) as cm:
                    self.plan()
                self.assertIn("reaches past row 5,000", str(cm.exception))


class ScanRows(unittest.TestCase):
    def test_the_reach_of_an_empty_row_is_not_counted(self):
        self.assertEqual(scan(HEAD + CELL + '<row r="6000"/>' + TAIL), (2, 1))
        self.assertEqual(scan(HEAD + '<row r="6000"/>' + TAIL), (0, 0))

    def test_a_cell_at_row_6000_raises(self):
        with self.assertRaises(Invalid):
            scan(HEAD + '<row r="6000"><c r="B6000"/></row>' + TAIL)

    def test_a_row_tag_with_no_r_or_an_empty_r(self):
        self.assertEqual(scan(HEAD + "<row/><row r=\"\"/><row><c/></row>" + TAIL), (3, 1))
        with self.assertRaises(Invalid):                 # cell with no r takes the row number of the tag it sits in
            scan(HEAD + '<row r="6000"><c><v>1</v></c></row>' + TAIL)

    def test_row_tags_cut_by_a_chunk_are_read_the_same(self):
        xml = HEAD + CELL + '<row r="6000" spans="1:2"/>' + TAIL
        bad = HEAD + CELL + '<row r="6000" spans="1:2"><c r="A6000"/></row>' + TAIL
        for chunk in (1, 2, 3, 5, 7, 16, 100, 65536):
            with self.subTest(chunk=chunk):
                self.assertEqual(scan(xml, chunk), (2, 1))
                with self.assertRaises(Invalid):
                    scan(bad, chunk)

    def test_a_flood_of_row_tags_is_still_refused(self):
        for chunk in (7, 65536):
            with self.subTest(chunk=chunk), self.assertRaises(Invalid):
                scan(HEAD + "<row/>" * (LIMIT + 1) + TAIL, chunk)
        scan(HEAD + "<row/>" * LIMIT + TAIL)

    def test_hostile_attribute_text(self):
        evil = (b'<row r="6000" note="r=&quot;1&quot; <c r=&quot;A9999&quot;>" x=\'r="7000"\'/>',
                b'<row data-r="1" xr="9" r="6000"/>',
                b'<row\tr="6000"\n/>',
                b'<row r="6000" a="' + b"<c " * 5000 + b'"/>')
        for tag in evil:
            with self.subTest(tag=tag[:40]):
                xml = HEAD.encode() + CELL.encode() + tag + TAIL.encode()
                try:
                    out = scan(xml)
                except Invalid:
                    self.fail("an empty row's attribute text moved the reach")
                self.assertEqual(out[0], 2)
        with self.assertRaises((Invalid, ValueError)):   # a 5000-digit row number: refused (ValueError is turned into the can't-be-read message by the caller, as before)
            scan(HEAD + '<row r="' + "9" * 5000 + '"><c><v>1</v></c></row>' + TAIL)


if __name__ == "__main__":
    unittest.main()
