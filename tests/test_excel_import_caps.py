"""Row 966: the Excel import refuses a hostile workbook while it is streamed, before openpyxl loads it whole. The fixtures are built
here (a real export with one part rewritten); nothing big is committed."""
import random
import re
import shutil
import tempfile
import time
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

import base64
from _demo import USER, DemoStore
import _workbook as wbk
from clark import excel, excel_route
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


def prefixed(xml):
    """The same sheet XML with every element written with the namespace prefix x: (declared on the root)."""
    xml = re.sub(r"<(/?)([A-Za-z])", r"<\1x:\2", xml)
    return xml.replace("<x:worksheet ", '<x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ', 1)


def declare_shared_strings(path, text):
    """Give the workbook a shared-strings part that [Content_Types].xml and the workbook's rels both declare, holding one string."""
    with zipfile.ZipFile(path) as z:
        types, rels = z.read("[Content_Types].xml").decode(), z.read("xl/_rels/workbook.xml.rels").decode()
    types = types.replace("</Types>", '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.'
                          'spreadsheetml.sharedStrings+xml"/></Types>')
    rels = rels.replace("</Relationships>", '<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                        'sharedStrings" Target="sharedStrings.xml" Id="rId99"/></Relationships>')
    rewrite(path, "[Content_Types].xml", types)
    rewrite(path, "xl/_rels/workbook.xml.rels", rels)
    rewrite(path, "xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">'
            '<si><t>%s</t></si></sst>' % text)


def damage_stream(path, member):
    """Overwrite the middle of the member's compressed bytes in the zip file itself (the zip's own records stay as they were)."""
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(member)
    raw = bytearray(Path(path).read_bytes())
    start = info.header_offset + 30 + len(info.filename.encode()) + int.from_bytes(raw[info.header_offset + 28:info.header_offset + 30], "little")
    mid = start + info.compress_size // 2
    raw[mid:mid + 40] = b"\xff" * 40
    Path(path).write_bytes(bytes(raw))


def lie_about_crc(path, member):
    """Change the CRC-32 the zip's central directory declares for the member (what the member holds is untouched)."""
    raw = bytearray(Path(path).read_bytes())
    name = member.encode()
    at = raw.index(b"PK\x01\x02")
    while raw[at + 46:at + 46 + int.from_bytes(raw[at + 28:at + 30], "little")] != name:
        at = raw.index(b"PK\x01\x02", at + 4)
    raw[at + 16:at + 20] = bytes(b ^ 0xFF for b in raw[at + 16:at + 20])
    Path(path).write_bytes(bytes(raw))


def mark_member(path, member, encrypted=False, method=None):
    """Set the 'encrypted' flag, or compression method 99 (AES), on one member in the zip's own directory (the bytes are left as they are)."""
    data = bytearray(Path(path).read_bytes())
    pos = 0
    while True:
        pos = data.find(b"PK\x01\x02", pos)
        if pos < 0:
            raise AssertionError(member)
        n = int.from_bytes(data[pos + 28:pos + 30], "little")
        if bytes(data[pos + 46:pos + 46 + n]) == member.encode():
            break
        pos += 4
    if encrypted:
        data[pos + 8] |= 1
    if method is not None:
        data[pos + 10:pos + 12] = method.to_bytes(2, "little")
    Path(path).write_bytes(bytes(data))


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

    def test_a_damaged_part_is_refused_in_the_plain_words_and_not_as_a_raw_error(self):
        part = part_of(self.path, "Actions")
        for how, damage in (("a damaged deflate stream", damage_stream), ("a CRC the zip does not match", lie_about_crc)):
            path = self.tmp / "damaged.xlsx"
            shutil.copy(self.path, path)
            rewrite(path, part, HEAD + rows_xml(400, cols=3) + TAIL)
            damage(path, part)
            with zipfile.ZipFile(path) as z, self.assertRaises((zipfile.BadZipFile, zlib.error, EOFError), msg=how):
                z.read(part)                                    # the file really is damaged: a bare read raises
            with self.assertRaises(Invalid, msg=how) as cm:
                xi.check_sheets_early(path, lambda t: True)
            self.assertEqual(str(cm.exception), "damaged.xlsx can't be read as an Excel workbook (.xlsx).")
        self.path = path
        self.assertIn("can't be read as an Excel workbook (.xlsx)", self.refused())       # and through read_workbook, as the route calls it

    def test_each_error_a_zip_member_read_can_raise_is_refused_in_the_plain_words_and_not_as_a_raw_error(self):
        # Raised directly from inside the early check (the read of the sheet part), one type at a time. Before this, BadZipFile,
        # zlib.error and EOFError were reached only through real damage, ValueError through the long digit run, and OSError not at all.
        part = part_of(self.path, "Actions")
        real_open = zipfile.ZipFile.open
        for exc in (zipfile.BadZipFile("bad"), zlib.error("bad"), EOFError("bad"), OSError("bad"), ValueError("bad")):
            def opener(zf, name, *a, _exc=exc, **kw):
                if name == part:
                    raise _exc
                return real_open(zf, name, *a, **kw)
            with self.subTest(error=type(exc).__name__):
                with mock.patch.object(zipfile.ZipFile, "open", opener):
                    with self.assertRaises(Invalid) as cm:
                        xi.check_sheets_early(self.path, lambda t: True)
                self.assertEqual(str(cm.exception), "ABC.xlsx can't be read as an Excel workbook (.xlsx).")

    def test_a_damaged_workbook_xml_or_rels_is_refused_in_the_plain_words_at_both_entry_points(self):
        words = "damaged.xlsx can't be read as an Excel workbook (.xlsx)."
        for member in ("xl/workbook.xml", "xl/_rels/workbook.xml.rels"):
            path = self.tmp / "damaged.xlsx"
            shutil.copy(self.path, path)
            with zipfile.ZipFile(path) as z:
                rewrite(path, member, z.read(member) + b" " * 4000 + b"<!--" + bytes(random.Random(1).randrange(97, 123) for _ in range(6000)) + b"-->")       # big enough that the damage lands inside the deflate data
            damage_stream(path, member)
            with zipfile.ZipFile(path) as z, self.assertRaises((zipfile.BadZipFile, zlib.error, EOFError), msg=member):
                z.read(member)                                  # the file really is damaged: a bare read raises
            for entry, call in (("check_sheets_early", lambda: xi.check_sheets_early(path, lambda t: True)),
                                ("list_sheets", lambda: xi.list_sheets(path))):
                with self.subTest(member=member, entry=entry):
                    with self.assertRaises(Invalid) as cm:
                        call()
                    self.assertEqual(str(cm.exception), words)

    def test_each_error_a_zip_member_read_can_raise_in_the_sheet_list_parts_is_refused_in_the_plain_words(self):
        real_open = zipfile.ZipFile.open
        for member in ("xl/workbook.xml", "xl/_rels/workbook.xml.rels"):
            for exc in (zlib.error("bad"), EOFError("bad"), ValueError("bad")):
                def opener(zf, name, *a, _exc=exc, _m=member, **kw):
                    if name == _m:
                        raise _exc
                    return real_open(zf, name, *a, **kw)
                with self.subTest(member=member, error=type(exc).__name__):
                    with mock.patch.object(zipfile.ZipFile, "open", opener):
                        with self.assertRaises(Invalid) as cm:
                            xi.check_sheets_early(self.path, lambda t: True)
                    self.assertEqual(str(cm.exception), "ABC.xlsx can't be read as an Excel workbook (.xlsx).")

    def test_an_encrypted_or_method_99_member_is_refused_in_the_plain_words_at_both_entry_points(self):
        words = "ABC.xlsx can't be read as an Excel workbook (.xlsx)."
        for how, kw, raw in (("encrypted", {"encrypted": True}, RuntimeError), ("method 99", {"method": 99}, NotImplementedError)):
            for member in (part_of(self.path, "Actions"), "xl/sharedStrings.xml"):
                (self.tmp / "m").mkdir(exist_ok=True)
                path = self.tmp / "m" / "ABC.xlsx"
                shutil.copy(self.path, path)
                if member == "xl/sharedStrings.xml":
                    declare_shared_strings(path, "q")
                mark_member(path, member, **kw)
                with zipfile.ZipFile(path) as z, self.assertRaises(raw, msg=how):
                    z.read(member)                              # the file really is that way: a bare read raises the raw error
                for entry, call in (("check_sheets_early", lambda: xi.check_sheets_early(path, lambda t: True)),
                                    ("list_sheets", lambda: xi.list_sheets(path))):
                    if entry == "list_sheets" and member != "xl/sharedStrings.xml":
                        continue                                # list_sheets scans only the shared strings
                    with self.subTest(how=how, member=member, entry=entry):
                        with self.assertRaises(Invalid) as cm:
                            call()
                        self.assertEqual(str(cm.exception), words)

    def test_a_damaged_shared_strings_part_is_refused_in_the_plain_words(self):
        declare_shared_strings(self.path, "q" * 20000)
        lie_about_crc(self.path, "xl/sharedStrings.xml")
        self.assertIn("can't be read as an Excel workbook (.xlsx)", self.refused())

    def test_a_cell_or_row_number_with_thousands_of_digits_is_refused_in_the_plain_words_and_not_as_a_raw_error(self):
        part = part_of(self.path, "Actions")
        for how, body in (("column letters then a long row number", '<row r="1"><c r="A%s"><v>1</v></c></row>' % ("9" * 5000)),
                          ("a long row number", '<row r="%s"><c r="A1"><v>1</v></c></row>' % ("9" * 5000))):
            rewrite(self.path, part, HEAD + body + TAIL)
            self.assertEqual(self.refused(), "ABC.xlsx can't be read as an Excel workbook (.xlsx).", how)

    def test_a_hostile_sheet_the_import_does_not_read_is_left_to_the_ordinary_path(self):
        rewrite(self.path, part_of(self.path, "Actions"), HEAD + rows_xml(300000) + TAIL)
        with self.assertRaises(Loaded):
            self.plan(sheets={xi.SHEET_TABLES["decisions"]})        # only Decisions is read; Actions is not looked at

    def test_a_normal_export_passes_the_early_check_and_is_loaded(self):
        with self.assertRaises(Loaded):
            self.plan()

    def test_a_prefixed_sheet_that_holds_6000_rows_is_refused_before_the_load(self):
        rewrite(self.path, part_of(self.path, "Actions"), prefixed(HEAD + rows_xml(6000) + TAIL))
        text = self.refused()
        self.assertIn("The Actions sheet reaches past row 5,000", text)
        self.assertIn("Nothing was changed", text)

    def test_a_prefixed_cell_far_to_the_right_is_refused_and_a_normal_prefixed_workbook_passes(self):
        part = part_of(self.path, "Decisions")
        rewrite(self.path, part, prefixed(HEAD + '<row r="3"><c r="CW3"><v>1</v></c></row>' + TAIL))
        self.assertIn("The Decisions sheet reaches past row 5,000 or column 100", self.refused())
        with zipfile.ZipFile(self.path) as z:                         # a real export's own sheets, every element prefixed
            sheets = {n: z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")}
        small = self.tmp / "small-prefixed.xlsx"
        shutil.copy(self.path, small)
        for name, xml in sheets.items():
            rewrite(small, name, prefixed(xml))
        self.path = small
        with self.assertRaises(Loaded):
            self.plan()

    def test_a_sheet_of_empty_rows_past_the_row_cap_is_refused_before_the_load(self):
        part = part_of(self.path, "Actions")
        for how, row in (("<row/> with no number", "<row/>"), ("<row r=\"N\"/> numbered", None), ("an empty open and close", "<row></row>")):
            body = "".join('<row r="%d"/>' % r for r in range(1, 6002)) if row is None else row * 6001
            rewrite(self.path, part, HEAD + body + TAIL)
            text = self.refused()
            self.assertIn("The Actions sheet reaches past row 5,000", text, how)
            self.assertIn("Nothing was changed", text, how)
        rewrite(self.path, part, HEAD + "<row/>" * 4000 + TAIL)          # inside the cap, empty rows alone do not refuse
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


class RealRoute(unittest.TestCase):
    """Added beside Caps (which patches load_workbook and so never reaches the real list_sheets): sheets -> check -> apply through
    make_excel_import on a DemoStore, with nothing patched. The hostile fixture DECLARES its shared-strings part in [Content_Types].xml and
    the workbook rels, holding one string longer than Excel can keep."""
    def setUp(self):
        excel_route.PLANS.clear()
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.addCleanup(excel_route.PLANS.clear)
        self.store = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-caps-route-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.seam = excel_route.make_excel_import(self.store.path, [], USER)
        self.a1 = self.demo.action(description="Draft the cut-over plan", due_date="2030-04-15")
        self.path = self.tmp / "ABC work items.xlsx"
        made = excel.export_project(self.store, "ABC", self.path, self.tmp / "state.json", on="2030-06-01")
        record = excel.load_state(self.tmp / "state.json", made)
        excel.save_state(Path(self.store.path).parent / excel.STATE_FILE, excel.id_key("ABC", record["export_id"]), record)

    def post(self, **req):
        return self.seam(dict(req, project="ABC"))

    def data(self):
        return base64.b64encode(self.path.read_bytes()).decode("ascii")

    def edit_description(self):
        """A real change through openpyxl (the export writes its texts inline), then a shared-strings part that the package declares."""
        import openpyxl
        wb = openpyxl.load_workbook(str(self.path))
        ws = wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == self.a1)
        ws.cell(row, head["Description"]).value = "Draft the cut-over plan, version two"
        wb.save(str(self.path))
        declare_shared_strings(self.path, "a short text")

    def test_a_33000_character_shared_string_is_refused_by_the_sheets_op_in_the_plain_words(self):
        declare_shared_strings(self.path, "s" * (xi.MAX_CELL_TEXT + 1000))
        status, got = self.post(op="sheets", name=self.path.name, data=self.data())
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertEqual(got["message"], "ABC work items.xlsx can't be read as an Excel workbook (.xlsx).")
        self.assertEqual(excel_route.PLANS, {})

    def test_a_33000_character_shared_string_written_with_a_namespace_prefix_is_refused_in_the_plain_words(self):
        declare_shared_strings(self.path, "a short text")
        rewrite(self.path, "xl/sharedStrings.xml", '<x:sst xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">'
                '<x:si><x:t>%s</x:t></x:si></x:sst>' % ("s" * (xi.MAX_CELL_TEXT + 1000)))
        status, got = self.post(op="sheets", name=self.path.name, data=self.data())
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertEqual(got["message"], "ABC work items.xlsx can't be read as an Excel workbook (.xlsx).")
        self.assertEqual(excel_route.PLANS, {})

    def test_a_damaged_workbook_xml_or_rels_is_refused_by_the_sheets_and_check_ops_in_the_plain_words(self):
        good = self.path.read_bytes()
        for member in ("xl/workbook.xml", "xl/_rels/workbook.xml.rels"):
            self.path.write_bytes(good)
            with zipfile.ZipFile(self.path) as z:
                rewrite(self.path, member, z.read(member) + b" " * 4000 + b"<!--" + bytes(random.Random(1).randrange(97, 123) for _ in range(6000)) + b"-->")
            damage_stream(self.path, member)
            for op in ("sheets", "check"):
                with self.subTest(member=member, op=op):
                    status, got = self.post(op=op, name=self.path.name, data=self.data())
                    self.assertEqual((status, got["ok"]), (400, False))
                    self.assertEqual(got["message"], "ABC work items.xlsx can't be read as an Excel workbook (.xlsx).")
                    self.assertEqual(excel_route.PLANS, {})

    def test_a_normal_workbook_with_a_declared_shared_string_is_listed_checked_and_applied(self):
        self.edit_description()
        status, listed = self.post(op="sheets", name=self.path.name, data=self.data())
        self.assertEqual(status, 200, listed)
        self.assertIn("actions", [s["table"] for s in listed["sheets"]])
        status, got = self.post(op="check", file=listed["file"], sheets=[s["table"] for s in listed["sheets"]])
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual([i["kind"] for i in got["items"]], ["changed"])
        status, done = self.post(op="apply", plan=got["plan"], accept="all", confirm=True)
        self.assertEqual((status, done["ok"]), (200, True), done)
        self.assertEqual(self.store.read("actions", ref=self.a1)["description"], "Draft the cut-over plan, version two")


if __name__ == "__main__":
    unittest.main()
