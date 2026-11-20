"""Row 1272: the client Excel writes a callout section as text blocks on the Report sheet (no Callout sheet): the lines `callout_lines` gives, read back from the xlsx.

Run: python3 dev/run_tests.py test_excel_callout_lines_report_1272
Uses the plant (fictional data) with callout sections put in front, through publish.select().
"""
import io
import json
import unittest

from _paths import ROOT   # noqa: F401

import _publish_fixture as fx
from openpyxl import load_workbook
from clark import excel_client, publish

BASE = {"v": 1, "tone": "decision", "title": "ZQ-Pick one", "paras": ["ZQ-para", "ZQ-two"], "category": "ZQ-Choice", "colour": "amber", "icon": "flag"}


def book(*bodies):
    i = fx.inputs()
    for n, b in enumerate(bodies):
        i["sections"].insert(0, {"project": "PUB", "id": f"s-co{n}", "type": "callout", "title": "", "beside": 0, "hidden": 0,
                                 "sort_order": 0, "body": json.dumps({**BASE, **b})})
    return load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(i))))


def report(wb):
    return wb[wb.sheetnames[0]]


def rows(ws):
    """The callout text rows: from the first cell in column A holding a ZQ- word or the category line, to the end."""
    out = [(ws.cell(r, 1).value, ws.cell(r, 1).font.b) for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value]
    first = next(i for i, (t, _) in enumerate(out) if t.startswith("ZQ-") or t.startswith("Category:"))
    return out[first:]


class CalloutLinesOnReport(unittest.TestCase):
    def test_no_callout_sheet_at_all(self):
        wb = book({}, {"title": "ZQ-B"})
        self.assertEqual([n for n in wb.sheetnames if n.startswith("Callout")], [])

    def test_lines_in_order_heading_bold_on_the_report_sheet(self):
        self.assertEqual(rows(report(book({}))), [("ZQ-Pick one", True), ("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False),
                                                  ("ZQ-para", False), ("ZQ-two", False)])

    def test_heading_off_has_no_heading_row(self):
        self.assertEqual(rows(report(book({"heading": False})))[0], ("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False))

    def test_plain_and_no_icon_say_nothing_extra(self):
        self.assertEqual(rows(report(book({"colour": "plain", "icon": "none"})))[1], ("Category: ZQ-Choice.", False))

    def test_two_callouts_follow_each_other_in_section_order(self):
        got = [t for t, _ in rows(report(book({"title": "ZQ-A", "paras": ["ZQ-a1"]}, {"title": "ZQ-B", "paras": ["ZQ-b1"]})))]
        self.assertEqual([t for t in got if t in ("ZQ-A", "ZQ-a1", "ZQ-B", "ZQ-b1")], ["ZQ-A", "ZQ-a1", "ZQ-B", "ZQ-b1"])

    def test_empty_callout_writes_nothing(self):
        plain = book({"title": "", "paras": [], "category": "", "colour": "plain", "icon": "none"})
        self.assertEqual(report(plain).max_row, report(book()).max_row)

    def test_writer_writes_no_row_for_a_callout_with_no_line(self):
        from openpyxl import Workbook
        ws = Workbook().active
        self.assertEqual(excel_client.write_callout_text(ws, {"type": "callout", "content": {"v": 1, "title": "", "paras": []}}), 0)
        self.assertEqual(ws.max_row, 1)

    def test_text_is_locked_and_sheet_protected(self):
        ws = report(book({}))
        self.assertTrue(ws.protection.sheet)
        r = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "ZQ-Pick one")
        self.assertTrue(ws.cell(r, 1).protection.locked)

    def test_words_that_start_with_an_equals_sign_stay_text(self):
        ws = report(book({"paras": ["=ZQ-sum"]}))
        r = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "=ZQ-sum")
        self.assertEqual(ws.cell(r, 1).data_type, "s")
        self.assertTrue(ws.cell(r, 1).quotePrefix)

    def test_one_empty_row_before_the_first_block(self):
        ws = report(book({}))
        r = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "ZQ-Pick one")
        self.assertIsNone(ws.cell(r - 1, 1).value)
        self.assertIsNotNone(ws.cell(r - 2, 1).value)


if __name__ == "__main__":
    unittest.main()
