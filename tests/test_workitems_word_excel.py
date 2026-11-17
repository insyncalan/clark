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

from test_docx_build import published, every_text, headings, blocks

BUILT_IN = ("actions", "raid", "decisions")


def with_list(items, title="Open work", built_in=False, caption=""):
    p = copy.deepcopy(published())
    p["sections"] = [s for s in p["sections"] if built_in or s["type"] not in BUILT_IN]
    p["sections"].append({"id": "s-list", "type": "workitems", "title": title, "beside": 0, "items": items, "columns": ["id"], "caption": caption})
    return p


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

    def list_table(self, p):
        return next(b["rows"] for b in blocks(docx_build.build(p)) if b["kind"] == "table" and b["rows"][0][0] == "ID" and b["rows"][0][1] == "Item")

    def test_the_header_row_is_the_on_screen_words(self):
        # the Work items list's own words (templates/workItemsList.js WORDS.columns, WorkItemsList.jsx): ID, Item (the title), Owner, Due, Status, Priority
        self.assertEqual(self.list_table(with_list(["PUB-A-001"]))[0], ["ID", "Item", "Owner", "Priority", "Due", "Status"])

    def test_a_late_row_says_what_the_screen_says_not_overdue(self):
        p = with_list(["PUB-A-002"])
        p["as_at"] = "2026-12-31"
        due = self.list_table(p)[1][4]
        self.assertEqual(due, "06-11-2026 55 days late")      # workItems.js dueCell: N days late
        self.assertNotIn("(overdue)", every_text(docx_build.build(p)))

    def test_a_row_not_late_has_the_date_alone(self):
        self.assertEqual(self.list_table(with_list(["PUB-A-002"]))[1][4], "06-11-2026")

    def decision_due(self, status, needed_by, as_at, date="2026-10-09"):
        p = with_list(["PUB-D-001"])
        p["as_at"] = as_at
        d = next(r for r in p["data"]["decisions"] if r["id"] == "PUB-D-001")
        d.update(status=status, needed_by=needed_by, date=date)
        return self.list_table(p)[1][4]

    def test_a_row_due_yesterday_says_yesterday(self):
        p = with_list(["PUB-A-002"])
        p["as_at"] = "2026-11-07"                       # PUB-A-002 is due 2026-11-06
        self.assertEqual(self.list_table(p)[1][4], "06-11-2026 Yesterday")
        p["as_at"] = "2026-11-08"
        self.assertEqual(self.list_table(p)[1][4], "06-11-2026 2 days late")

    def test_a_pending_decision_due_yesterday_says_yesterday(self):
        self.assertEqual(self.decision_due("Pending", "2026-11-06", "2026-11-07"), "06-11-2026 Yesterday")

    def test_a_pending_decision_late_by_days_says_days_late(self):
        self.assertEqual(self.decision_due("Pending", "2026-11-06", "2026-11-10"), "06-11-2026 4 days late")

    def test_a_pending_decision_not_yet_late_has_the_date_alone(self):
        self.assertEqual(self.decision_due("Pending", "2026-11-06", "2026-11-06"), "06-11-2026")

    def test_a_non_pending_decision_with_a_past_needed_by_gets_no_late_words(self):
        for status in ("Made", "Superseded", "Withdrawn"):
            got = self.decision_due(status, "2026-11-06", "2026-11-10", date="2026-10-09")
            self.assertEqual(got, "09-10-2026", status)

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
