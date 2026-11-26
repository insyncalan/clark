"""Row 1631 point 1: the Documents sheet of the Excel workbook. Columns Title, Kind, Link, Date, one row per document. The editor
export lists every live document; the client copy lists only the client-visible ones (publish.documents: the eye and the archive
flag decide); the import ignores the sheet; the Report's "Sections of the Dashboard that have a sheet" table links to it; Help has
the line. Fictional data only.

Run: python3 dev/run_tests.py test_excel_documents_sheet_1631
"""
import io
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import DemoStore
from openpyxl import load_workbook

from clark import excel, excel_client, page, publish
from clark import excel_import as xi

HELP = Path(_paths.ROOT) / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
HEADINGS = ["Title", "Kind", "Link", "Date"]
LINE = "A Documents sheet lists the project\u2019s documents, files and links."      # the ticket's words; Help spells every apostrophe curly


def setUpModule():
    global _OLD, _NO_BRAND
    _NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")
    _OLD, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-docs-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.n = 0
        self.con = sqlite3.connect(str(self.demo.store.path))
        self.addCleanup(self.con.close)
        self.kept = self.plant("Weekly minutes", "Minutes", "https://example.com/zq-minutes", "2030-05-30")
        self.eye = self.plant("Eye off plan", "Plan", "https://example.com/zq-eye-off", "2030-05-01")
        self.gone = self.plant("Archived slides", "Slides", "https://example.com/zq-archived", "2030-04-01", archived=1)
        self.con.execute("INSERT INTO report_hidden (project, item_id) VALUES ('ABC', ?)", (self.eye,))
        self.con.commit()
        with self.demo.store.step("dashboard", "demo") as st:      # row 1266: the default report ends with a doclinks section; the client copy fills documents only for a visible docs section
            st.create("report_sections", {"project": "ABC", "type": "docs", "title": "Supporting documents", "sort_order": 990})

    def plant(self, title, kind, url, day, archived=0):
        self.n += 1
        ref = f"ABC-L-{self.n:03d}"
        self.con.execute("INSERT INTO documents (project, id, title, kind, url, date, sort_order, archived) VALUES ('ABC',?,?,?,?,?,?,?)",
                         (ref, title, kind, url, day, self.n * 1024, archived))
        self.con.commit()
        return ref

    def editor(self):
        path = self.tmp / "editor.xlsx"
        excel.export_project(self.demo.store, "ABC", path, self.tmp / "state.json", on="2030-06-01")
        return path

    def client(self):
        inputs = publish.read_inputs(self.demo.store, "ABC", "2030-06-01")
        return load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(inputs))))


def cells(ws):
    return [[c.value for c in row] for row in ws.iter_rows(values_only=False)]


class DocumentsSheet(Fixture):
    def test_documents_sheet_lists_the_documents(self):
        """The editor export has the sheet with the four headings and one row per live document (the eye-off one too, never the archived one)."""
        ws = load_workbook(self.editor())["Documents"]
        self.assertEqual([c.value for c in ws[1]][:4], HEADINGS)
        body = [[c.value for c in row][:3] for row in ws.iter_rows(min_row=2) if row[0].value]
        self.assertEqual(sorted(r[0] for r in body), ["Eye off plan", "Weekly minutes"])
        kept = next(r for r in body if r[0] == "Weekly minutes")
        self.assertEqual(kept[1:], ["Minutes", "https://example.com/zq-minutes"])
        self.assertNotIn("Archived slides", {str(c.value) for row in ws.iter_rows() for c in row})

    def test_the_date_is_a_real_date_in_the_sheets_format(self):
        ws = load_workbook(self.editor())["Documents"]
        row = next(r for r in ws.iter_rows(min_row=2) if r[0].value == "Weekly minutes")
        self.assertEqual(row[3].number_format, excel.DATE_FORMAT)

    def test_a_hidden_document_is_absent_from_the_client_copy(self):
        wb = self.client()
        self.assertIn("Documents", wb.sheetnames)
        text = {str(c.value) for row in wb["Documents"].iter_rows() for c in row if c.value is not None}
        self.assertIn("Weekly minutes", text)
        self.assertIn("https://example.com/zq-minutes", text)
        for gone in ("Eye off plan", "https://example.com/zq-eye-off", "Archived slides", "https://example.com/zq-archived"):
            self.assertNotIn(gone, text)
        heads = [c.value for c in next(row for row in wb["Documents"].iter_rows() if row[0].value == "Title")]
        self.assertEqual(heads[:4], HEADINGS)

    def test_the_client_copy_has_no_documents_sheet_when_the_page_has_no_document(self):
        self.con.execute("UPDATE documents SET archived = 1")
        self.con.commit()
        self.assertNotIn("Documents", self.client().sheetnames)

    def test_the_report_table_links_to_the_documents_sheet(self):
        report = load_workbook(self.editor())["Report"]
        links = [c for row in report.iter_rows() for c in row if c.hyperlink is not None and "Documents" in str(c.hyperlink.location)]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].value, "Documents sheet")
        self.assertEqual(excel.sheet_links(["Report", "Documents"], None), [("Documents", "Documents")])

    def test_the_sheet_is_in_the_workbook_only_when_there_is_a_document(self):
        self.con.execute("UPDATE documents SET archived = 1")
        self.con.commit()
        wb = load_workbook(self.editor())
        self.assertNotIn("Documents", wb.sheetnames)

    def test_the_import_ignores_the_sheet(self):
        path = self.editor()
        wb = load_workbook(path)
        wb["Documents"]["A2"].value = "Changed on the sheet"
        wb.save(path)
        plan = xi.read_workbook(self.demo.store, path, "ABC", state_path=self.tmp / "state.json", allow_unrecorded=True)
        self.assertNotIn("Changed on the sheet", json.dumps(plan.__dict__, default=str))
        titles = {r["title"] for r in self.demo.store.read("documents", "ABC")}
        self.assertNotIn("Changed on the sheet", titles)

    def test_a_gantt_tab_named_documents_does_not_take_the_sheet_name(self):
        self.assertNotEqual(excel.gantt_sheet_name("Documents").lower(), "documents")

    def test_help_has_the_documents_line(self):
        self.assertIn(LINE, HELP.read_text(encoding="utf8"))
