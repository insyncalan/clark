"""Row 1272: the client Excel writes a callout section as its own sheet: the lines `callout_lines` gives, read back from the xlsx.

Run: python3 dev/run_tests.py test_excel_callout_sheet_1272
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


def rows(ws):
    return [(ws.cell(r, 1).value, ws.cell(r, 1).font.b) for r in range(4, ws.max_row + 1)]


class CalloutSheet(unittest.TestCase):
    def test_lines_in_order_heading_bold(self):
        self.assertEqual(rows(book({})["Callout"]), [("ZQ-Pick one", True), ("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False),
                                                   ("ZQ-para", False), ("ZQ-two", False)])

    def test_heading_off_has_no_heading_row(self):
        self.assertEqual(rows(book({"heading": False})["Callout"])[0], ("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False))

    def test_plain_and_no_icon_say_nothing_extra(self):
        self.assertEqual(rows(book({"colour": "plain", "icon": "none"})["Callout"])[1], ("Category: ZQ-Choice.", False))

    def test_two_callouts_two_sheets(self):
        wb = book({"title": "ZQ-A"}, {"title": "ZQ-B"})
        self.assertEqual([n for n in wb.sheetnames if n.startswith("Callout")].__len__(), 2)

    def test_empty_callout_has_no_sheet(self):
        self.assertNotIn("Callout", book({"title": "", "paras": []}).sheetnames)

    def test_writer_makes_no_sheet_for_a_callout_with_no_line(self):
        from openpyxl import Workbook
        wb = Workbook()
        pub = publish.select(fx.inputs())
        self.assertIsNone(excel_client.write_callout_sheet(wb, pub, {"type": "callout", "content": {"v": 1, "title": "", "paras": []}}))
        self.assertEqual(len(wb.sheetnames), 1)

    def test_sheet_is_locked_text(self):
        ws = book({})["Callout"]
        self.assertTrue(ws.protection.sheet)
        self.assertTrue(ws.cell(4, 1).protection.locked)

    def test_no_callout_no_sheet(self):
        self.assertFalse([n for n in load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(fx.inputs())))).sheetnames if n.startswith("Callout")])


if __name__ == "__main__":
    unittest.main()
