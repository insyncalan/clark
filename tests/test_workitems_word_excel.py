"""Row 1268, slice 2: the Word report and the client workbook print what a Work items list names.

A list section (type "workitems", published as its ordered ids) is written to the Word report as one table in its own order, and
the client workbook gets the sheet of every table a list names; with no built-in section for that table the sheet holds only the
listed rows. With the built-in section shown, nothing changes.

Run: python3 dev/run_tests.py test_workitems_word_excel
Uses the #39 plant (fictional data), through publish.select().
"""
import copy
import io
import unittest

from _paths import ROOT   # noqa: F401

from openpyxl import load_workbook
from clark import docx_build, excel, excel_client

from test_docx_build import published, every_text, headings

BUILT_IN = ("actions", "raid", "decisions")


def with_list(items, title="Open work", built_in=False, caption="", columns=("id",)):
    p = copy.deepcopy(published())
    p["sections"] = [s for s in p["sections"] if built_in or s["type"] not in BUILT_IN]
    p["sections"].append({"id": "s-list", "type": "workitems", "title": title, "beside": 0, "items": items, "columns": list(columns), "caption": caption})
    return p


def cells(data):
    """The words of the one Work items table, in reading order (the table after the list's heading)."""
    import re
    import zipfile
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    xml = xml[xml.index("Open work"):]
    xml = xml[xml.index("<w:tbl>"):xml.index("</w:tbl>")]
    return re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)


class Word(unittest.TestCase):
    def test_a_list_is_written_with_its_title_and_its_rows_in_order(self):
        p = with_list(["PUB-D-001", "PUB-A-002", "PUB-001"])
        data = docx_build.build(p)
        self.assertIn("Open work", headings(data))
        text = every_text(data)
        self.assertTrue(text.index("PUB-D-001") < text.index("PUB-A-002") < text.index("PUB-001"))

    def test_only_the_named_rows_are_written(self):
        text = every_text(docx_build.build(with_list(["PUB-A-001"])))
        self.assertIn("PUB-A-001", text)
        self.assertNotIn("PUB-A-002", text)

    def test_the_caption_is_written(self):
        self.assertIn("ZQ-CAPTION", every_text(docx_build.build(with_list(["PUB-A-001"], caption="ZQ-CAPTION"))))

    def test_a_list_that_names_no_published_row_is_left_out(self):
        self.assertNotIn("Open work", headings(docx_build.build(with_list(["PUB-A-404"]))))

    def test_the_table_has_the_columns_the_list_chose_and_no_other(self):
        got = cells(docx_build.build(with_list(["PUB-A-001"], columns=("id", "owner"))))
        self.assertEqual(got[:3], ["ID", "Item", "Owner"])
        for word in ("Priority", "Workstream", "Milestone", "Status", "Due", "Type"):
            self.assertNotIn(word, got)

    def test_id_is_a_column_choice_and_leaves_with_it(self):
        self.assertIn("PUB-A-001", cells(docx_build.build(with_list(["PUB-A-001"], columns=("id", "due")))))
        got = cells(docx_build.build(with_list(["PUB-A-001"], columns=("due",))))
        self.assertNotIn("PUB-A-001", got)
        self.assertEqual(got[:2], ["Item", "Due"])

    def test_the_columns_come_in_the_pages_order(self):
        got = cells(docx_build.build(with_list(["PUB-A-001"], columns=("status", "owner", "id", "type"))))
        self.assertEqual(got[:5], ["Type", "ID", "Item", "Owner", "Status"])

    def test_the_built_in_sections_are_as_before(self):
        p = published()
        shown = headings(docx_build.build(p))
        for name in ("Actions", "Decisions", "Risks and issues"):
            self.assertIn(name, shown)
        self.assertNotIn("Work items", shown)


class Excel(unittest.TestCase):
    def sheets(self, p):
        return load_workbook(io.BytesIO(excel_client.workbook_bytes(p)))

    def test_a_list_gives_the_sheets_of_the_tables_it_names(self):
        p = with_list(["PUB-A-001", "PUB-D-001"])
        got = excel_client.sheet_tables(p)
        self.assertIn("actions", got)
        self.assertIn("decisions", got)
        self.assertNotIn("raid", got)

    def test_the_sheet_holds_only_the_listed_rows(self):
        wb = self.sheets(with_list(["PUB-A-002"]))
        ws = wb[excel.SHEET_OF["actions"]]
        ids = [ws.cell(r, 1).value for r in range(5, ws.max_row + 1)]
        self.assertEqual(ids, ["PUB-A-002"])

    def test_no_list_and_no_built_in_section_gives_no_such_sheet(self):
        p = with_list([])
        self.assertNotIn("raid", excel_client.sheet_tables(p))

    def test_a_shown_built_in_section_keeps_every_row(self):
        p = with_list(["PUB-A-001"], built_in=True)
        ws = self.sheets(p)[excel.SHEET_OF["actions"]]
        self.assertEqual([ws.cell(r, 1).value for r in range(5, ws.max_row + 1)], ["PUB-A-001", "PUB-A-002"])


if __name__ == "__main__":
    unittest.main()
