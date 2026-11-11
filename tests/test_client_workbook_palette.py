"""Kill the survivors in excel_client (row 999): the client workbook takes the project's brand palette per call.

Run: python3 dev/run_tests.py test_client_workbook_palette
A palette {"fill", "text"} passed to workbook_bytes must colour the title band, the sub band and the header row of every data sheet
and of the Gantt sheet; with no palette the committed pair stands. Fictional data only.
"""
import copy
import io
import unittest

import _publish_fixture as fixture
from _paths import SRC  # noqa: F401
from clark import excel_client, publish
from openpyxl import load_workbook

import test_gantt_excel_export as gx

BRAND = {"fill": "123456", "text": "FEDCBA"}


def rgb(colour):
    return str(colour.rgb)[-6:].upper()


def book(palette=None, with_gantt=True):
    inputs = gx.plant() if with_gantt else fixture.inputs()
    published = publish.select(copy.deepcopy(inputs))
    return load_workbook(io.BytesIO(excel_client.workbook_bytes(published, palette)))


def bands(ws):
    """(fill, text colour) of the title cell, the sub cell, the first header cell and a header cell far to the right."""
    last = ws.max_column
    return [(rgb(c.fill.fgColor), rgb(c.font.color)) for c in (ws["A1"], ws["A2"], ws["A4"], ws.cell(row=4, column=last), ws.cell(row=1, column=last))]


class ClientPalette(unittest.TestCase):
    def test_a_palette_colours_every_sheet_including_the_gantt(self):
        wb = book(BRAND)
        self.assertIn("Plan", wb.sheetnames)
        for ws in wb.worksheets:
            got = bands(ws)
            self.assertEqual(got[0], (BRAND["fill"], BRAND["text"]), ws.title)      # title band
            self.assertEqual(got[1], (BRAND["fill"], BRAND["text"]), ws.title)      # sub band
            self.assertEqual(got[2], (BRAND["fill"], BRAND["text"]), ws.title)      # header row
            self.assertEqual(got[3], (BRAND["fill"], BRAND["text"]), ws.title)
            self.assertEqual(got[4][0], BRAND["fill"], ws.title)                    # the band runs the full width

    def test_no_palette_is_the_committed_pair(self):
        want = (excel_client.PALETTE["fill"].lstrip("#").upper()[-6:], excel_client.PALETTE["text"].lstrip("#").upper()[-6:])
        for ws in book(None).worksheets:
            self.assertEqual(bands(ws)[:4], [want] * 4, ws.title)
        self.assertNotEqual(want, (BRAND["fill"], BRAND["text"]))

    def test_the_title_is_larger_than_the_sub_band(self):
        ws = book(BRAND)["Actions"]
        self.assertEqual(ws["A1"].font.sz, 16)
        self.assertTrue(ws["A1"].font.b)
        self.assertEqual(ws["A2"].font.sz, 11)
        self.assertFalse(ws["A2"].font.b)


if __name__ == "__main__":
    unittest.main()
