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

    def test_a_list_with_no_columns_chosen_has_the_default_columns_with_priority(self):
        # row 1268: WORK_DEFAULT is Type, ID, Item, Owner, Due, Priority (a list that names none gets these)
        got = cells(docx_build.build(with_list(["PUB-A-001"], columns=())))
        self.assertEqual(got[:6], ["Type", "ID", "Item", "Owner", "Due", "Priority"])
        self.assertEqual(got[6:13], ["Action", "PUB-A-001", "ZQ-KEEP-MESSAGE-1", "Latest update: ZQ-KEEP-UPDATE-1", "Site manager", "06-11-2026", "Medium"])      # row 1307: the update line sits in the Item cell
        for word in ("Workstream", "Milestone", "Status"):
            self.assertNotIn(word, got)

    def test_a_milestone_id_prints_the_milestones_name(self):
        got = cells(docx_build.build(with_list(["PUB-A-001"], columns=("id", "milestone"))))
        self.assertEqual(got, ["ID", "Item", "Milestone", "PUB-A-001", "ZQ-KEEP-MESSAGE-1", "Latest update: ZQ-KEEP-UPDATE-1", "Pilot live ZQ-KEEP-MILESTONE-1"])
        self.assertNotIn("PUB-M-001", got)

    def test_the_item_column_sits_after_type_and_id_and_before_the_rest(self):
        got = cells(docx_build.build(with_list(["PUB-A-001"], columns=("milestone", "workstream", "priority", "status", "due", "owner", "id", "type"))))
        self.assertEqual(got[:8], ["Type", "ID", "Item", "Owner", "Due", "Status", "Priority", "Workstream"])
        self.assertEqual(got[8], "Milestone")

    def test_the_workstream_cell_prints_the_workstream(self):
        got = cells(docx_build.build(with_list(["PUB-A-001"], columns=("id", "workstream"))))
        self.assertEqual(got, ["ID", "Item", "Workstream", "PUB-A-001", "ZQ-KEEP-MESSAGE-1", "Latest update: ZQ-KEEP-UPDATE-1", "Delivery"])

    def test_an_action_with_an_update_shows_its_latest_update_line(self):      # row 1307
        got = cells(docx_build.build(with_list(["PUB-A-001"])))
        self.assertIn("Latest update: ZQ-KEEP-UPDATE-1", got)

    def test_an_action_without_an_update_has_no_update_line(self):      # row 1307
        got = cells(docx_build.build(with_list(["PUB-A-002"])))
        self.assertFalse([w for w in got if w.startswith("Latest update")])

    def test_a_risk_or_a_decision_row_has_no_update_line(self):      # row 1307
        p = with_list(["PUB-001", "PUB-D-001"])
        for t in ("raid", "decisions"):
            for r in p["data"][t]:
                r["latest_update"] = "<p>ZQ-NOT-SHOWN</p>"
        got = cells(docx_build.build(p))
        self.assertFalse([w for w in got if "Latest update" in w or "ZQ-NOT-SHOWN" in w])

    def list_table(self, p):
        return next(b["rows"] for b in blocks(docx_build.build(p)) if b["kind"] == "table" and b["rows"][0][0] == "ID" and b["rows"][0][1] == "Item")

    def test_the_header_row_is_the_on_screen_words(self):
        # the Work items list's own words (templates/workItemsList.js WORDS.columns, WorkItemsList.jsx): ID, Item (the title), Owner, Due, Status, Priority
        self.assertEqual(self.list_table(with_list(["PUB-A-001"], columns=("id", "owner", "priority", "due", "status")))[0], ["ID", "Item", "Owner", "Due", "Status", "Priority"])

    def test_a_late_row_has_the_date_alone_no_days_late(self):      # row 1543 AP4b: no N days late in the client copy (was "06-11-2026 55 days late")
        p = with_list(["PUB-A-002"], columns=("id", "owner", "priority", "due", "status"))
        p["as_at"] = "2026-12-31"
        due = self.list_table(p)[1][3]
        self.assertEqual(due, "06-11-2026")
        self.assertNotIn("(overdue)", every_text(docx_build.build(p)))

    def test_a_row_not_late_has_the_date_alone(self):
        self.assertEqual(self.list_table(with_list(["PUB-A-002"], columns=("id", "owner", "priority", "due", "status")))[1][3], "06-11-2026")

    def decision_due(self, status, needed_by, as_at, date="2026-10-09"):
        p = with_list(["PUB-D-001"], columns=("id", "due"))
        p["as_at"] = as_at
        d = next(r for r in p["data"]["decisions"] if r["id"] == "PUB-D-001")
        d.update(status=status, needed_by=needed_by, date=date)
        return self.list_table(p)[1][2]

    def test_a_row_due_yesterday_has_the_date_alone(self):      # review ruling: a passed date gets no relative word, Yesterday included
        p = with_list(["PUB-A-002"], columns=("id", "due"))
        p["as_at"] = "2026-11-07"                       # PUB-A-002 is due 2026-11-06
        self.assertEqual(self.list_table(p)[1][2], "06-11-2026")
        p["as_at"] = "2026-11-08"
        self.assertEqual(self.list_table(p)[1][2], "06-11-2026")      # row 1543 AP4b: was "06-11-2026 2 days late"

    def test_a_pending_decision_due_yesterday_has_the_date_alone(self):      # review ruling: no Yesterday on a passed date
        self.assertEqual(self.decision_due("Pending", "2026-11-06", "2026-11-07"), "06-11-2026")

    def test_a_pending_decision_late_by_days_has_the_date_alone(self):      # row 1543 AP4b: was "06-11-2026 4 days late"
        self.assertEqual(self.decision_due("Pending", "2026-11-06", "2026-11-10"), "06-11-2026")

    def test_a_pending_decision_not_yet_late_has_the_date_alone(self):
        self.assertEqual(self.decision_due("Pending", "2026-11-06", "2026-11-06"), "06-11-2026")

    def test_a_non_pending_decision_with_a_past_needed_by_gets_no_late_words(self):
        for status in ("Made", "Superseded", "Withdrawn"):
            got = self.decision_due(status, "2026-11-06", "2026-11-10", date="2026-10-09")
            self.assertEqual(got, "09-10-2026", status)

    def any_table(self, p):
        return next(b["rows"] for b in blocks(docx_build.build(p)) if b["kind"] == "table" and "Item" in b["rows"][0])

    def test_the_type_cell_holds_the_rows_kind(self):      # row 1268
        rows = self.any_table(with_list(["PUB-A-001", "PUB-001"], columns=("type", "id")))
        self.assertEqual(rows[0][0], "Type")
        self.assertEqual(rows[1][0], "Action")
        self.assertEqual(rows[2][0], "Risk")

    def test_a_decision_row_has_decision_in_its_type_cell(self):      # row 1268
        rows = self.any_table(with_list(["PUB-D-001"], columns=("type", "id")))
        self.assertEqual(rows[1][0], "Decision")

    def test_the_item_column_keeps_its_minimum_width_when_every_column_is_chosen(self):      # row 1268
        import re
        import zipfile
        cols = ("type", "id", "owner", "due", "status", "priority", "workstream", "milestone")
        xml = zipfile.ZipFile(io.BytesIO(docx_build.build(with_list(["PUB-A-001"], columns=cols)))).read("word/document.xml").decode()
        xml = xml[xml.index("Open work"):]
        grid = [int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"', xml[xml.index("<w:tbl>"):])[:9]]
        self.assertGreater(grid[2], 1500, "the Item column keeps its 2000 minimum before the table is scaled to the page")

    def test_the_priority_column_is_wide_enough_for_its_word(self):
        import re
        import zipfile
        xml = zipfile.ZipFile(io.BytesIO(docx_build.build(with_list(["PUB-A-001"], columns=("id", "priority"))))).read("word/document.xml").decode()
        xml = xml[xml.index("Open work"):]
        grid = [int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"', xml[xml.index("<w:tbl>"):])[:3]]
        self.assertEqual(grid[0], 1200)
        self.assertEqual(grid[2], 950)

    def test_a_row_of_a_section_left_off_is_counted_only_when_a_list_names_it(self):
        kept = docx_build._kept(with_list(["PUB-A-001"]), {"workitems"})
        self.assertEqual([r["id"] for r in kept["rows"]], ["PUB-A-001"])
        shown = docx_build._kept(with_list(["PUB-A-001"], built_in=True), {"workitems", "actions", "raid", "decisions"})
        self.assertIn("PUB-A-002", [r["id"] for r in shown["rows"]])

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
