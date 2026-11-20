"""Row 1272, gap 1: the client workbook writes a callout's category, colour name and icon name as words (callout.words()), with its title
and words, on a sheet of its own. An empty callout has no sheet.

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


def row(ws):
    return [ws.cell(5, c).value for c in range(1, 6)]


class Callout(unittest.TestCase):
    def test_the_sheet_is_called_callout_and_its_heads_are_the_five_words(self):
        ws = book(select(BODY))["Callout"]
        self.assertEqual([ws.cell(4, c).value for c in range(1, 6)], ["Category", "Colour", "Icon", "Title", "Words"])

    def test_the_category_is_written(self):
        self.assertEqual(row(book(select(BODY))["Callout"])[0], "ZQ-Choice")

    def test_the_colour_is_written_as_its_name(self):
        self.assertEqual(row(book(select(BODY))["Callout"])[1], "Amber")

    def test_the_icon_is_written_as_its_name(self):
        self.assertEqual(row(book(select(BODY))["Callout"])[2], "Flag")

    def test_no_icon_writes_nothing(self):
        self.assertIn(row(book(select({**BODY, "icon": "none"}))["Callout"])[2], (None, ""))

    def test_the_title_is_written(self):
        self.assertEqual(row(book(select(BODY))["Callout"])[3], "ZQ-Pick one")

    def test_the_words_are_the_cleaned_text_of_the_editor(self):
        self.assertEqual(row(book(select(BODY))["Callout"])[4], "ZQ-words here")

    def test_without_the_editor_text_the_paragraphs_are_the_words(self):
        self.assertEqual(row(book(select({**BODY, "html": ""}))["Callout"])[4], "ZQ-para")

    def test_an_older_callout_with_a_tone_only_writes_its_tone_words(self):
        old = {"v": 1, "tone": "warning", "title": "ZQ-t", "paras": []}
        r = row(book(select(old))["Callout"])
        self.assertEqual(r[0], "Warning")
        self.assertEqual(r[1], "Red")

    def test_an_empty_callout_has_no_sheet(self):
        self.assertNotIn("Callout", book(select({"v": 1, "tone": "info", "title": "", "paras": []})).sheetnames)

    def test_two_callouts_get_two_sheets(self):
        names = [n for n in book(select(BODY, {**BODY, "title": "ZQ-two"})).sheetnames if n.startswith("Callout")]
        self.assertEqual(len(names), 2)

    def test_the_second_sheet_is_named_with_its_position(self):
        names = book(select(BODY, {**BODY, "title": "ZQ-two"})).sheetnames
        self.assertEqual([n for n in names if n.startswith("Callout")], ["Callout", f"Callout {len(names)}"])

    def test_a_section_with_no_title_and_no_words_writes_no_sheet(self):
        import openpyxl
        wb = openpyxl.Workbook()
        got = excel_client.write_callout_sheet(wb, select(BODY), {"content": {"tone": "info", "title": "", "paras": [], "html": ""}})
        self.assertIsNone(got)

    def test_a_words_cell_starting_with_an_equals_sign_stays_text(self):
        ws = book(select({**BODY, "html": "", "paras": ["=1+1"]}))["Callout"]
        self.assertEqual((ws.cell(5, 5).data_type, ws.cell(5, 5).quotePrefix), ("s", True))

    def test_the_sheet_is_locked_text(self):
        ws = book(select(BODY))["Callout"]
        self.assertTrue(ws.protection.sheet)
        self.assertTrue(ws.cell(5, 1).protection.locked)

    def test_the_same_bytes_twice(self):
        p = select(BODY)
        self.assertEqual(excel_client.workbook_bytes(p), excel_client.workbook_bytes(p))


if __name__ == "__main__":
    unittest.main()
