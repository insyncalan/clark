"""Row 1272 (ruling: no Callout sheet): the client workbook carries each callout as text lines on the Report sheet, in the page's order:
the title (else "Callout"), "Category: x. Colour: y. Icon: z." with empty parts left out, then the words.

Run: python3 dev/run_tests.py test_excel_client_callout_1272
"""
import io
import json
import unittest

from _paths import ROOT   # noqa: F401

import _publish_fixture as fx
from openpyxl import load_workbook
from clark import excel_client, publish

BODY = {"v": 1, "tone": "decision", "title": "ZQ-Pick one", "paras": ["ZQ-para"], "html": "<p>ZQ-words <b>here</b></p>",
        "category": "ZQ-Choice", "colour": "amber", "icon": "flag"}


def select(*bodies):
    i = fx.inputs()
    for n, b in enumerate(bodies):
        i["sections"].insert(0, {"project": "PUB", "id": f"s-c{n}", "type": "callout", "title": "", "beside": 0, "hidden": 0, "sort_order": n, "body": json.dumps(b)})
    return publish.select(i)


def book(pub):
    return load_workbook(io.BytesIO(excel_client.workbook_bytes(pub)))


def lines(pub, name="Report"):
    ws = book(pub)[name]
    return [ws.cell(r, 1).value for r in range(5, ws.max_row + 1) if ws.cell(r, 1).value is not None]


class Callout(unittest.TestCase):
    def test_all_parts_give_title_the_line_and_the_words(self):
        self.assertEqual(lines(select(BODY)), ["ZQ-Pick one", "Category: ZQ-Choice. Colour: Amber. Icon: Flag.", "ZQ-words here"])

    def test_no_category_leaves_that_part_out(self):
        self.assertEqual(lines(select({**BODY, "category": ""}))[1], "Colour: Amber. Icon: Flag.")

    def test_no_colour_name_and_no_icon_leave_the_line_to_the_category(self):
        got = lines(select({**BODY, "icon": "none", "colour": "plain"}))
        self.assertEqual(got[1], "Category: ZQ-Choice. Colour: Plain.")

    def test_no_icon_leaves_the_icon_part_out(self):
        self.assertEqual(lines(select({**BODY, "icon": "none"}))[1], "Category: ZQ-Choice. Colour: Amber.")

    def test_no_part_at_all_writes_no_line(self):
        old = {"v": 1, "tone": "info", "title": "ZQ-t", "paras": ["ZQ-p"], "category": "", "colour": "plain", "icon": "none"}
        pub = select(old)
        got = lines(pub)
        self.assertEqual(got[0], "ZQ-t")
        self.assertEqual(got[-1], "ZQ-p")

    def test_no_title_the_heading_is_callout(self):
        self.assertEqual(lines(select({**BODY, "title": ""}))[0], "Callout")

    def test_without_the_editor_text_the_paragraphs_are_the_words(self):
        self.assertEqual(lines(select({**BODY, "html": ""}))[-1], "ZQ-para")

    def test_callouts_come_in_the_pages_order(self):
        pub = select(BODY, {**BODY, "title": "ZQ-two"})
        order = [s["content"]["title"] for s in pub["sections"] if s["type"] == "callout"]
        got = lines(pub)
        self.assertEqual([t for t in got if t in order], order)
        self.assertEqual(len(order), 2)

    def test_the_first_line_is_on_row_5_and_a_blank_row_separates_callouts(self):
        ws = book(select(BODY, {**BODY, "title": "ZQ-two"}))["Report"]
        col = [ws.cell(r, 1).value for r in range(5, 5 + 7)]
        self.assertEqual(col[3], None)
        self.assertEqual([col[0], col[4]], ["ZQ-Pick one", "ZQ-two"])
        self.assertEqual(ws.max_row, 5 + 6)

    def test_the_heading_is_bold_and_the_words_are_not(self):
        ws = book(select(BODY))["Report"]
        self.assertEqual([ws.cell(r, 1).font.b for r in (5, 6, 7)], [True, False, False])

    def test_the_column_is_wide(self):
        self.assertEqual(book(select(BODY))["Report"].column_dimensions["A"].width, 100)

    def test_there_is_no_callout_sheet(self):
        self.assertFalse([n for n in book(select(BODY)).sheetnames if n.startswith("Callout")])

    def test_an_empty_callout_writes_nothing(self):
        self.assertNotIn("Report", book(select({"v": 1, "tone": "info", "title": "", "paras": []})).sheetnames)

    def test_a_line_starting_with_an_equals_sign_stays_text(self):
        ws = book(select({**BODY, "html": "", "paras": ["=1+1"]}))["Report"]
        c = [ws.cell(r, 1) for r in range(5, ws.max_row + 1) if ws.cell(r, 1).value == "=1+1"][0]
        self.assertEqual((c.data_type, c.quotePrefix), ("s", True))

    def test_the_sheet_is_locked_text(self):
        ws = book(select(BODY))["Report"]
        self.assertTrue(ws.protection.sheet)
        self.assertTrue(ws.cell(5, 1).protection.locked)

    def test_the_same_bytes_twice(self):
        p = select(BODY)
        self.assertEqual(excel_client.workbook_bytes(p), excel_client.workbook_bytes(p))

    def test_a_page_without_callouts_has_no_report_sheet(self):
        self.assertNotIn("Report", book(select()).sheetnames)

    def test_the_other_sheets_are_unchanged_by_a_callout(self):
        self.assertEqual([n for n in book(select(BODY)).sheetnames if n != "Report"], book(select()).sheetnames)

    def test_the_editors_reader_ignores_a_report_sheet(self):
        import tempfile
        from pathlib import Path
        from clark import excel
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.xlsx"
            path.write_bytes(excel_client.workbook_bytes(select(BODY)))
            got = excel.read_workbook(path)
        self.assertEqual(set(got), set(excel.SHEET_OF))

    def test_the_client_copy_stays_not_importable_with_a_report_sheet(self):
        import tempfile
        from pathlib import Path
        from clark import excel
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.xlsx"
            path.write_bytes(excel_client.workbook_bytes(select(BODY)))
            self.assertIsNone(excel.export_id_of(path))


if __name__ == "__main__":
    unittest.main()
