"""Row 1266, AP11: the published page, the Word report and the Excel workbook of a NEW project carry the default sections and their titles
(Header, This week, Milestones, Use cases), and none of the older titles.

Run: python3 dev/run_tests.py test_new_project_outputs_1266
Fictional data only: the demo store's project ABC with its default sections; the Header and This week text sections are given a line each.
"""
import io
import unittest

from _demo import DemoStore
from _paths import SRC  # noqa: F401  (puts src/ on the path)
from openpyxl import load_workbook
from clark import docx_build, docx_read, excel_client, publish

OLD = ("Use case summary", "Supporting documents")


class NewProjectOutputs(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        ids = [r["id"] for r in self.store.data_for("ABC")["report_sections"]]
        self.demo.update("report_sections", ids[2], {"body": "<p>Header line</p>"})
        self.demo.update("report_sections", ids[3], {"body": "<p>This week line</p>"})
        self.built = publish.build(self.store, "ABC", now="2030-01-15")
        self.pub = self.built["published"]

    def test_the_published_page_has_the_new_sections_and_titles_in_order(self):
        self.assertEqual([s["title"] for s in self.pub["sections"]], ["Header", "This week", "Next week", "Milestones", "Use cases"])
        page = self.built["body"].decode("utf-8")
        for title in ("Header", "This week", "Use cases"):
            self.assertIn(title, page)
        for old in OLD:
            self.assertNotIn(old, page)

    def test_the_word_report_has_the_new_titles_as_headings_in_order(self):
        blocks = docx_read.read(docx_build.build(self.pub), "r.docx").blocks
        self.assertEqual([b["text"] for b in blocks if b["kind"] == "heading"][1:], ["Header", "This week", "Milestones", "Use cases"])
        text = "\n".join(str(b.get("text", "")) for b in blocks)
        for old in OLD:
            self.assertNotIn(old, text)

    def test_the_excel_workbook_has_the_new_titles_as_sheets(self):
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(self.pub)))
        self.assertEqual(wb.sheetnames, ["Milestones", "Use cases"])


if __name__ == "__main__":
    unittest.main()
