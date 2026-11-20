"""Row 1383: a docx or xlsx with a DOCTYPE or entity (the billion laughs) is refused before any parser sees it.

Run: python3 dev/run_tests.py test_xml_bomb_1383      No browser; the files are made in the test.
"""
import io
import tempfile
import unittest
import warnings
import zipfile
import zlib
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from openpyxl import Workbook, load_workbook

from clark import excel, excel_picture, word_brand
from clark.docx_read import WordRefused
from test_word_brand import BUILT, template
from test_word_brand_edges import rebuilt

LAUGHS = ('<!DOCTYPE lolz [<!ENTITY a "lol"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
          '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>')


def plain_xlsx():
    out = io.BytesIO()
    wb = Workbook()
    wb.active["A1"] = "x"
    wb.save(out)
    return out.getvalue()


def with_doctype(data, member, pad=0):
    """`data` (a zip) with `member` given a prolog of `pad` bytes of comment, then the entity bomb, before its root."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for i in src.infolist():
            d = src.read(i.filename)
            if i.filename == member:
                head, _, rest = d.partition(b"?>")
                d = head + b"?>" + (b"<!--" + b"." * pad + b"-->" if pad else b"") + LAUGHS.encode() + rest
            dst.writestr(i, d)
    return out.getvalue()


class XlsxBomb(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.dir, True)

    def save(self, data, name="bomb.xlsx"):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_a_clean_workbook_passes_the_check(self):
        excel.check_workbook_size(self.save(plain_xlsx()))

    def test_a_doctype_in_the_workbook_part_is_refused_before_opening(self):
        p = self.save(with_doctype(plain_xlsx(), "xl/workbook.xml"))
        with self.assertRaises(excel.NotSafe) as e:
            excel.check_workbook_size(p)
        self.assertIn("xl/workbook.xml", str(e.exception))
        self.assertIsInstance(e.exception, excel.TooBig)         # every caller that handles TooBig handles it

    def test_read_workbook_never_reaches_the_parser(self):
        p = self.save(with_doctype(plain_xlsx(), "xl/worksheets/sheet1.xml"))
        with mock.patch.object(excel, "load_workbook") as load:
            with self.assertRaises(excel.NotSafe):
                excel.read_workbook(p)
        load.assert_not_called()

    def test_a_doctype_after_a_long_prolog_is_still_found(self):
        p = self.save(with_doctype(plain_xlsx(), "xl/workbook.xml", pad=3 * 1024 * 1024))
        with self.assertRaises(excel.NotSafe):
            excel.check_workbook_size(p)

    def test_a_doctype_split_across_the_read_pieces_is_found(self):
        z = zipfile.ZipFile(io.BytesIO(with_doctype(plain_xlsx(), "xl/workbook.xml")))
        info = z.getinfo("xl/workbook.xml")
        at = z.read(info).index(b"<!DOCTYPE") + 4          # a piece boundary inside the word
        self.assertTrue(excel._has_doctype(z, info, chunk=at))
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as w:                  # a bare DOCTYPE, no ENTITY after it to be found by a later piece
            w.writestr("a.xml", b"<?xml version='1.0'?><!DOCTYPE x><a/>")
        z2 = zipfile.ZipFile(io.BytesIO(out.getvalue()))
        i2 = z2.getinfo("a.xml")
        at = z2.read(i2).index(b"<!DOCTYPE") + 4
        self.assertTrue(excel._has_doctype(z2, i2, chunk=at))

    def test_the_export_id_reader_ignores_a_part_with_a_doctype(self):
        p = self.save(with_doctype(plain_xlsx(), "docProps/core.xml"))   # a stand-in: any part
        self.assertTrue(excel_picture.has_doctype(zipfile.ZipFile(p).read("docProps/core.xml")))
        bomb = (b'<?xml version="1.0"?>' + LAUGHS.encode() + b"<Properties/>")
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr(excel.CUSTOM_PART, bomb)
        q = self.save(out.getvalue(), "id.xlsx")
        with mock.patch.object(excel, "fromstring") as parse:
            self.assertIsNone(excel.export_id_of(q))
        parse.assert_not_called()

    def test_the_cover_part_finder_refuses_a_doctype_in_either_part(self):
        wb = (b'<workbook xmlns="' + excel_picture.NS_MAIN.encode() + b'" xmlns:r="' + excel_picture.NS_REL.encode()
              + b'"><sheets><sheet name="Cover" r:id="rId1"/></sheets></workbook>')
        files = {"xl/workbook.xml": wb, "xl/_rels/workbook.xml.rels": b"<Relationships/>"}
        self.assertIsNone(excel_picture._cover_part(files, "Cover"))      # the same parts, clean, are read
        for name in files:
            bad = dict(files, **{name: LAUGHS.encode() + files[name]})
            with self.assertRaises(excel_picture.PictureRefused):
                excel_picture._cover_part(bad, "Cover")

    def test_a_utf16_doctype_is_seen(self):
        self.assertTrue(excel_picture.has_doctype(LAUGHS.encode("utf-16")))
        self.assertTrue(excel_picture.has_doctype(b"<!  ENTITY x 'y'>"))
        self.assertTrue(excel_picture.has_doctype(b"<!doctype x>"))
        self.assertFalse(excel_picture.has_doctype(b"<a>DOCTYPE and ENTITY words</a>"))


def renamed(data, old, new):
    """`data` (a zip) with the part `old` stored as `new`, and the content-types and relationship records following it, so openpyxl
    still finds the part (it is reached by relationship, not by name)."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for i in src.infolist():
            d = src.read(i.filename)
            if i.filename in ("[Content_Types].xml", "xl/_rels/workbook.xml.rels"):
                d = d.replace(old.encode(), new.encode()).replace(old.split("xl/", 1)[1].encode(), new.split("xl/", 1)[1].encode())
            dst.writestr(new if i.filename == old else i.filename, d)
    return out.getvalue()


SHEET = "xl/worksheets/sheet1.xml"


class OddlyNamedPart(unittest.TestCase):
    """The check follows what openpyxl will parse, which is any part the workbook points at, not only a name ending .xml or .rels."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.dir, True)

    def save(self, data):
        p = self.dir / "odd.xlsx"
        p.write_bytes(data)
        return p

    def test_the_renamed_clean_workbook_really_opens_and_passes(self):
        for new in ("xl/worksheets/sheet1.dat", "xl/worksheets/sheet1"):
            p = self.save(renamed(plain_xlsx(), SHEET, new))
            self.assertEqual(load_workbook(p)["Sheet"]["A1"].value, "x")   # the rename is real
            excel.check_workbook_size(p)                                                                          # no false refusal

    def test_a_doctype_in_a_part_named_dat_or_with_no_extension_is_refused(self):
        for new in ("xl/worksheets/sheet1.dat", "xl/worksheets/sheet1", "xl/worksheets/sheet1.XML.bak"):
            p = self.save(with_doctype(renamed(plain_xlsx(), SHEET, new), new))
            with self.assertRaises(excel.NotSafe, msg=new) as e:
                excel.check_workbook_size(p)
            self.assertIn(new, str(e.exception))

    def test_a_long_prolog_in_an_oddly_named_part_is_still_found(self):
        new = "xl/worksheets/sheet1.dat"
        p = self.save(with_doctype(renamed(plain_xlsx(), SHEET, new), new, pad=3 * 1024 * 1024))
        with self.assertRaises(excel.NotSafe):
            excel.check_workbook_size(p)

    def test_the_first_and_the_last_part_are_scanned_too(self):
        z = zipfile.ZipFile(io.BytesIO(plain_xlsx()))
        names = z.namelist()
        for member in (names[0], names[-1]):
            with self.assertRaises(excel.NotSafe, msg=member):
                excel.check_workbook_size(self.save(with_doctype(plain_xlsx(), member)))

    def test_a_damaged_oddly_named_part_is_left_to_the_later_steps(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("xl/blob.dat", b"x" * 100)
        raw = bytearray(out.getvalue())
        raw[raw.index(b"x" * 100)] ^= 0xFF                   # the stored bytes no longer match the zip's check value
        p = self.save(bytes(raw))
        excel.check_workbook_size(p)                         # not refused here: a damaged part is the later steps' to refuse

    def test_a_part_with_a_corrupt_deflate_stream_is_left_to_the_later_steps(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("xl/blob.dat", b"<a>" + b"hello world " * 400 + b"</a>")
        raw = bytearray(out.getvalue())
        start = 30 + len("xl/blob.dat")                       # the local header, then the compressed bytes
        raw[start:start + 12] = b"\xff" * 12                    # a valid zip directory, but the deflate data is garbage
        p = self.save(bytes(raw))
        with zipfile.ZipFile(p) as z:                         # the damage is the deflate kind, not a check-value mismatch
            with self.assertRaises(zlib.error):
                z.read("xl/blob.dat")
        excel.check_workbook_size(p)                          # not a crash and not a refusal: the later steps refuse it in plain words

    def test_two_parts_of_the_same_name_are_both_scanned(self):
        clean = b"<?xml version='1.0'?><a/>"
        bomb = b"<?xml version='1.0'?>" + LAUGHS.encode() + b"<a/>"
        for first, second in ((clean, bomb), (bomb, clean)):
            out = io.BytesIO()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")                # zipfile warns about a duplicate name
                with zipfile.ZipFile(out, "w") as z:
                    z.writestr("xl/dup.xml", first)
                    z.writestr("xl/dup.xml", second)
            p = self.save(out.getvalue())
            with zipfile.ZipFile(p) as z:
                self.assertEqual(len(z.infolist()), 2)
            with self.assertRaises(excel.NotSafe):             # opening by name would read one of the two, twice
                excel.check_workbook_size(p)

    def test_the_import_route_refuses_it_in_plain_words_and_creates_nothing(self):
        from _demo import DemoStore
        import _workbook as wbk
        from clark import excel_import as xi
        from clark.store import Invalid
        demo = DemoStore()
        self.addCleanup(demo.close)
        good = wbk.make_workbook(demo.store, self.dir / "ABC.xlsx")
        new = "xl/worksheets/sheet1.dat"
        bad = self.dir / "bad.xlsx"
        bad.write_bytes(with_doctype(renamed(Path(good).read_bytes(), SHEET, new), new))
        count = lambda: demo.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        before = count()
        with self.assertRaises(Invalid) as e:
            xi.read_workbook(demo.store, bad, "ABC", allow_unrecorded=True)
        self.assertIn("DOCTYPE or entity", str(e.exception))
        self.assertIn(new, str(e.exception))
        with self.assertRaises(Invalid):
            xi.list_sheets(bad)
        self.assertEqual(count(), before)


class DocxBomb(unittest.TestCase):
    def test_a_doctype_in_the_document_part_is_refused(self):
        t = rebuilt(template(), lambda n, d: d.replace(b"<w:document", LAUGHS.encode() + b"<w:document", 1) if n == "word/document.xml" else d)
        with mock.patch.object(word_brand.ET, "fromstring", side_effect=AssertionError("parsed")) as parse:
            with self.assertRaises(WordRefused):
                word_brand.wrap(t, BUILT)
        parse.assert_not_called()                                    # refused by the check, before any parse

    def test_a_doctype_in_the_content_types_part_is_refused(self):
        t = rebuilt(template(), lambda n, d: LAUGHS.encode() + d if n == "[Content_Types].xml" else d)
        with mock.patch.object(word_brand.ET, "fromstring", side_effect=AssertionError("parsed")) as parse:
            with self.assertRaises(WordRefused):
                word_brand.wrap(t, BUILT)
        parse.assert_not_called()                                    # refused by the check, before any parse


if __name__ == "__main__":
    unittest.main()
