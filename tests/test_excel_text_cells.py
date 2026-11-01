"""#85: text that starts like a formula is a text cell, shown exactly as typed (no apostrophe), and never a formula. Fictional data only.

The cell is stored as a string (an inline string in the XML, never <f>), and, when the text starts with = + - @ TAB or a line
break, its style carries quotePrefix, which Excel shows with no apostrophe and which keeps a later edit of the cell text.
This file reads the saved XML and reads the workbook back with openpyxl. It cannot open Excel, Numbers or LibreOffice: how those
show the cell needs a human look.

Run: python3 dev/run_tests.py test_excel_text_cells
"""
import hashlib
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import USER, DemoStore
from openpyxl import Workbook, load_workbook

from clark import excel
from clark import excel_cover as cover
from clark import excel_import as xi
from clark import page

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
FIXED_ID = "0123456789ab4def8123456789abcdef"
ON = "2030-06-01"

_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")    # a brand logo on this computer never changes a test


def setUpModule():
    global _OLD_BRANDING
    _OLD_BRANDING, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD_BRANDING
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


# text that must show as typed and carry the quote prefix
GUARDED = ("=SUM(1)", "+1", "-note", "@SUM(A1)", "\tTabbed", "=", "-", "+", "@", "=1+1", '=HYPERLINK("http://x.invalid","hi")',
           "- a bullet", "-- two dashes", "=cmd|' /C calc'!A0")
# text that is plain text to Excel: no quote prefix, and no change either
PLAIN = ("plain", " =1", "  -x", "a=b", "5-3", "#N/A", "＝1+1", "＋x", "－x", "＠x", " =1", "​=1", "'quoted",
         "x ", "")


def parts(path):
    """{member name: bytes} of the saved workbook."""
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def sheet_member(path, title):
    """The XML member of the sheet called `title`."""
    files = parts(path)
    wb = ET.fromstring(files["xl/workbook.xml"])
    rels = ET.fromstring(files["xl/_rels/workbook.xml.rels"])
    sheet = next(s for s in wb.find("m:sheets", NS) if s.get("name") == title)
    rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    target = next(r.get("Target") for r in rels if r.get("Id") == rid)
    return "xl/" + target.lstrip("/").replace("xl/", "")


def xml_cell(path, title, ref):
    """(the cell's t attribute, its text, whether its style has quotePrefix, whether it holds an <f>) read from the saved XML."""
    files = parts(path)
    root = ET.fromstring(files[sheet_member(path, title)])
    c = next(c for c in root.iter("{%s}c" % NS["m"]) if c.get("r") == ref)
    xfs = ET.fromstring(files["xl/styles.xml"]).find("m:cellXfs", NS)
    xf = xfs[int(c.get("s", "0"))]
    text = "".join(t.text or "" for t in c.iter("{%s}t" % NS["m"]))
    if c.get("t") == "s":
        shared = ET.fromstring(files["xl/sharedStrings.xml"])
        text = "".join(t.text or "" for t in shared[int(c.find("m:v", NS).text)].iter("{%s}t" % NS["m"]))
    return c.get("t"), text, xf.get("quotePrefix") == "1", c.find("m:f", NS) is not None


def action(text, **more):
    return {"id": "DEMO-A-001", "project": "DEMO", "raised": "2030-01-01", "client_message": "", "client_visible": 1,
            "source": "demo", "description": text, **more}


class DataSheets(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-text-cells-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path, self.state = self.dir / "DEMO.xlsx", self.dir / "state.json"

    def export(self, text, **more):
        self.path.unlink() if self.path.exists() else None
        excel.export(self.path, "DEMO", {"actions": [action(text, **more)]}, self.state, on=ON)

    def test_guarded_text_is_a_string_cell_with_the_quote_prefix_and_never_a_formula(self):
        for text in GUARDED:
            with self.subTest(text=text):
                self.export(text)
                t, shown, prefix, has_formula = xml_cell(self.path, "Actions", "B2")
                self.assertEqual(t, "inlineStr")                    # a string, not <f> and not a number
                self.assertEqual(shown, text, "the saved text is exactly what was typed: no apostrophe")
                self.assertTrue(prefix, "the style carries quotePrefix")
                self.assertFalse(has_formula)
                c = load_workbook(self.path)["Actions"]["B2"]
                self.assertEqual((c.value, c.data_type, c.quotePrefix), (text, "s", True))
                self.assertEqual(excel.read_workbook(self.path)["actions"][0]["description"], text)
                self.assertNotIn(b"<f>", b"".join(v for n, v in parts(self.path).items() if "worksheets/sheet" in n))
                self.assertNotIn(b"<f ", b"".join(v for n, v in parts(self.path).items() if "worksheets/sheet" in n))

    def test_the_xml_of_a_formula_looking_cell(self):
        self.export("=SUM(1)")
        sheet = parts(self.path)[sheet_member(self.path, "Actions")].decode("utf-8")
        self.assertRegex(sheet, r'<c r="B2" s="\d+" t="inlineStr"><is><t>=SUM\(1\)</t></is></c>')

    def test_other_text_is_a_string_cell_without_the_quote_prefix(self):
        for text in PLAIN:
            if not text:
                continue
            with self.subTest(text=text):
                self.export(text)
                t, shown, prefix, has_formula = xml_cell(self.path, "Actions", "B2")
                self.assertEqual((t, shown, prefix, has_formula), ("inlineStr", text, False, False))
                self.assertEqual(excel.read_workbook(self.path)["actions"][0]["description"], text)

    def test_a_carriage_return_or_line_feed_first_is_a_string_with_the_quote_prefix(self):
        for lead in ("\r", "\n", "\r\n"):
            with self.subTest(lead=repr(lead)):
                self.export(lead + "=1+1")
                t, shown, prefix, has_formula = xml_cell(self.path, "Actions", "B2")
                self.assertEqual((t, shown.lstrip("\n"), prefix, has_formula), ("inlineStr", "=1+1", True, False))
                self.assertEqual(excel.read_workbook(self.path)["actions"][0]["description"], "\n=1+1")    # a CR is stored as a line feed

    def test_full_width_look_alikes_are_left_alone(self):
        self.export("＝1+1")
        c = load_workbook(self.path)["Actions"]["B2"]
        self.assertEqual((c.value, c.data_type, c.quotePrefix), ("＝1+1", "s", False))

    def test_very_long_text_is_kept_whole(self):
        for text in ("=" + "x" * 30000, "-" + "y" * 9000):
            with self.subTest(length=len(text)):
                self.export(text)
                t, shown, prefix, has_formula = xml_cell(self.path, "Actions", "B2")
                self.assertEqual((t, shown, prefix, has_formula), ("inlineStr", text, True, False))
                self.assertEqual(excel.read_workbook(self.path)["actions"][0]["description"], text)

    def test_the_style_keeps_the_font_and_the_wrap(self):
        self.export("=SUM(1)")
        plain = load_workbook(self.path)["Actions"]["B2"]
        self.export("SUM(1)")
        other = load_workbook(self.path)["Actions"]["B2"]
        self.assertEqual((plain.font.name, plain.alignment.wrap_text, plain.alignment.vertical),
                         (other.font.name, other.alignment.wrap_text, other.alignment.vertical))

    def test_every_text_column_is_protected(self):
        self.export("-x", owner="=y", client_message="@z")
        ws = load_workbook(self.path)["Actions"]
        head = {c.value: c.column for c in ws[1]}
        for label, want in (("Description", "-x"), ("Owner", "=y"), ("Client wording", "@z")):
            c = ws.cell(row=2, column=head[label])
            self.assertEqual((c.value, c.data_type, c.quotePrefix), (want, "s", True), label)

    def test_the_lists_sheet_is_protected_too(self):
        self.export("x", workstream="=Build")
        ws = load_workbook(self.path)["Lists"]
        cells = [c for row in ws.iter_rows(min_row=2) for c in row if c.value == "=Build"]
        self.assertTrue(cells)
        for c in cells:
            self.assertEqual((c.data_type, c.quotePrefix), ("s", True))

    def test_the_same_rows_and_day_give_the_same_bytes_with_guarded_text(self):
        rows = {"actions": [action(text) for text in GUARDED[:4]]}
        for i, row in enumerate(rows["actions"], start=1):
            row["id"] = f"DEMO-A-{i:03d}"
        out = []
        for real in (datetime(2031, 1, 1, 9, 0, 1), datetime(2032, 5, 6, 7, 8, 9)):
            with mock.patch.object(excel, "clock", lambda real=real: real), \
                    mock.patch.object(excel, "new_export_id", lambda: FIXED_ID), \
                    mock.patch("time.time", lambda real=real: real.timestamp()), \
                    mock.patch("time.localtime", lambda t=None, real=real: real.timetuple()):
                path = self.dir / f"{len(out)}.xlsx"
                excel.export(path, "DEMO", rows, self.dir / f"state{len(out)}.json", on=ON)
                out.append(path.read_bytes())
        self.assertEqual(out[0], out[1])

    def test_the_record_holds_the_hash_of_the_file_written(self):
        self.export("=SUM(1)")
        record = excel.load_state(self.state, self.path, "DEMO")
        self.assertEqual(record["hash"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(record["rows"]["actions"]["DEMO-A-001"]["description"], "=SUM(1)")     # the record holds the text as typed


class OneCell(unittest.TestCase):
    def test_protect_text_cell_makes_a_string_of_what_openpyxl_would_make_a_formula(self):
        ws = Workbook().active
        c = ws["A1"]
        c.value = "=1+1"
        self.assertEqual(c.data_type, "f")                  # what openpyxl does by itself
        excel.protect_text_cell(c)
        self.assertEqual((c.value, c.data_type, c.quotePrefix), ("=1+1", "s", True))

    def test_numbers_and_blanks_are_left_alone(self):
        ws = Workbook().active
        ws["A1"], ws["A2"] = -5, None
        for c in (ws["A1"], ws["A2"]):
            excel.protect_text_cell(c)
        self.assertEqual((ws["A1"].data_type, ws["A1"].quotePrefix), ("n", False))
        self.assertFalse(ws["A2"].quotePrefix)

    def test_text_goes_in_as_typed_and_comes_back_for_every_text(self):
        for text in GUARDED + PLAIN + ("'=1", "''=1", "''", "'", "'\t=1", "'-x", "'''-x"):
            with self.subTest(text=text):
                cell = excel.to_cell("description", text)
                if text.startswith(("=", "+", "-", "@", "\t")):
                    self.assertEqual(cell, text, "no apostrophe in front")
                self.assertEqual(excel.from_cell("description", cell) if cell else None, text or None)

    def test_a_file_from_the_first_release_still_reads_back(self):
        # that release wrote =1+1 as '=1+1; the import still takes the apostrophe off
        for old, text in (("'=1+1", "=1+1"), ("'-note", "-note"), ("'@x", "@x"), ("''=1", "'=1"), ("'quoted", "'quoted")):
            self.assertEqual(excel.from_cell("description", old), text)
            self.assertEqual(xi.from_cell("description", old, "TEXT")[0], text)


class TheCover(unittest.TestCase):
    def test_cover_text_that_starts_like_a_formula_is_a_string_with_the_quote_prefix(self):
        for lead in ("=", "+", "-", "@"):
            with self.subTest(lead=lead):
                project = {"name": lead + "Name", "current_state": "<p>" + lead + "Now.</p>"}
                sections = [{"type": "current", "title": lead + "Section"}]
                wb = Workbook()
                path = Path(tempfile.mkdtemp(prefix="clark-text-cells-")) / "cover.xlsx"
                self.addCleanup(shutil.rmtree, path.parent, True)
                ws = excel.write_cover(wb, cover.lines(project, sections, [], datetime(2030, 6, 1, 9, 0)))
                wb.save(path)
                seen = {c.value: c for row in load_workbook(path)["Cover"].iter_rows() for c in row if c.value}
                for want in (lead + "Name", lead + "Section", lead + "Now."):
                    self.assertIn(want, seen)
                    self.assertEqual((seen[want].data_type, seen[want].quotePrefix), ("s", True), want)
                self.assertNotIn(b"<f>", b"".join(v for n, v in parts(path).items() if "worksheets/sheet" in n))
                self.assertGreater(ws.max_row, 1)


class RoundTrip(unittest.TestCase):
    """Export, then import: the text is the same, no change is found, and a real formula typed by a person is still refused."""
    TEXTS = GUARDED + ("'=1", "''x", " =1", "＝1+1", "=" + "z" * 9000)

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-text-cells-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        with self.demo.store.step("dashboard", USER) as st:
            self.ids = [st.create("actions", {"project": "ABC", "description": text, "raised": "2026-10-01", "source": "demo"})
                        for text in self.TEXTS]
        self.path, self.state = self.dir / "ABC work items.xlsx", self.dir / "state.json"
        excel.export_project(self.demo.store, "ABC", self.path, self.state, on=ON)

    def plan(self):
        return xi.read_workbook(self.demo.store, self.path, "ABC", state_path=self.state)

    def test_an_unchanged_export_imports_as_no_change(self):
        plan = self.plan()
        self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [])
        self.assertEqual(plan.problems, [])

    def test_the_text_in_the_file_is_the_text_in_the_store(self):
        ws = load_workbook(self.path)["Actions"]
        head = {c.value: c.column for c in ws[1]}
        by_id = {ws.cell(row=r, column=head["ID"]).value: ws.cell(row=r, column=head["Description"]) for r in range(2, ws.max_row + 1)}
        for item_id, text in zip(self.ids, self.TEXTS):
            self.assertEqual(by_id[item_id].value, excel.to_cell("description", text))
            self.assertEqual(by_id[item_id].data_type, "s")

    def test_a_real_formula_typed_by_a_person_is_refused(self):
        wb = load_workbook(self.path)
        ws = wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        plain = ws.cell(row=2, column=head["Owner"])
        guarded = ws.cell(row=3, column=head["Owner"])           # next to a cell that has the quote prefix on its text
        plain.value = "=1+1"
        guarded.value = "=2+2"
        self.assertEqual((plain.data_type, guarded.data_type), ("f", "f"))
        wb.save(self.path)
        plan = self.plan()
        self.assertTrue(any("formula cell was ignored" in n for n in plan.notes), plan.notes)
        self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [], "a formula is never read as a value")

    def test_an_ordinary_edit_next_to_guarded_text_imports_with_the_text_intact(self):
        wb = load_workbook(self.path)
        ws = wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        ws.cell(row=2, column=head["Owner"]).value = "Sam Example"
        wb.save(self.path)
        plan = self.plan()
        changed = [c for c in plan.changes if c.kind != "unchanged"]
        self.assertEqual(len(changed), 1)
        plan.accept_all()
        xi.apply_import(self.demo.store, plan, USER, state_path=self.state)
        got = {r["id"]: r["description"] for r in self.demo.store.read("actions", "ABC") if r["id"] in self.ids}
        self.assertEqual([got[i] for i in self.ids], list(self.TEXTS))


if __name__ == "__main__":
    unittest.main()
