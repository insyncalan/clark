"""Row 1264, slice 9 print: the Word report draws the glance template with the View's tiles on a line: the body's per_row (3 or 4,
4 when the body has none), and 2 when the section is half width (the published section's `beside` is 1, the page's slot-left/slot-right).
The Excel sheet has a row for each tile, so a line count changes nothing there.

Run: python3 dev/run_tests.py test_glance_word_excel_1264_print
"""
import io
import json
import unittest

from _paths import ROOT   # noqa: F401

import _publish_fixture as fx
from openpyxl import load_workbook
from clark import docx_build, docx_read, excel_client, glance_print, publish

ONLY_BESPOKE = {"health": {"shown": False}, "builtin": {n: {"hidden": True} for n in ("overdue", "risks", "decisions")}}


def tiles(n):
    return [{"id": f"t{i}", "label": f"ZQ-T{i}", "figure": str(i)} for i in range(n)]


def select(n=10, beside=0, **kw):
    i = fx.inputs()
    i["sections"] = [x for x in i["sections"] if x["type"] != "glance"]
    b = {"v": 1, "bespoke": tiles(n), **ONLY_BESPOKE, **kw}
    i["sections"].insert(0, {"project": "PUB", "id": "s-gt", "type": "glancetemplate", "title": "", "beside": beside, "hidden": 0,
                             "sort_order": 0, "body": json.dumps(b)})
    return publish.select(i)


def cells_per_row(pub):
    blocks = docx_read.read(docx_build.build(pub), "r.docx").blocks
    rows = next(b["rows"] for b in blocks if b["kind"] == "table" and "ZQ-T0" in str(b["rows"]))
    return [len(r) for r in rows]


def full_section(pub):
    return next(s for s in pub["sections"] if s["id"] == "s-gt")


class WordCellsPerRow(unittest.TestCase):
    def test_the_default_is_four_when_the_body_has_no_per_row(self):
        self.assertEqual(cells_per_row(select(10)), [4, 4, 4])

    def test_per_row_4_runs_four_and_pads_the_short_last_line(self):
        self.assertEqual(cells_per_row(select(10, per_row=4)), [4, 4, 4])

    def test_per_row_3_runs_three_and_pads_the_short_last_line(self):
        self.assertEqual(cells_per_row(select(10, per_row=3)), [3, 3, 3, 3])

    def test_per_row_3_with_an_exact_fit_has_no_padding_line(self):
        self.assertEqual(cells_per_row(select(9, per_row=3)), [3, 3, 3])

    def test_half_width_runs_two_and_pads_the_short_last_line(self):
        self.assertEqual(cells_per_row(select(5, beside=1)), [2, 2, 2])

    def test_half_width_is_two_whatever_per_row_says(self):
        self.assertEqual(cells_per_row(select(6, beside=1, per_row=3)), [2, 2, 2])
        self.assertEqual(cells_per_row(select(6, beside=1, per_row=4)), [2, 2, 2])

    def test_every_tile_is_still_in_the_report(self):
        for kw in ({}, {"per_row": 3}, {"beside": 1}):
            t = str(docx_read.read(docx_build.build(select(7, **kw)), "r.docx").blocks)
            for i in range(7):
                self.assertIn(f"ZQ-T{i}", t)


class ReaderPerLine(unittest.TestCase):
    def test_per_line_is_the_views(self):
        for kw, want in (({}, 4), ({"per_row": 3}, 3), ({"per_row": 4}, 4), ({"beside": 1}, 2), ({"beside": 1, "per_row": 3}, 2)):
            pub = select(5, **kw)
            self.assertEqual(glance_print.read(pub, full_section(pub))["per_line"], want, kw)

    def test_a_per_row_that_is_not_3_or_4_is_the_default(self):
        for bad in (2, 5, "3", None, True, 3.0):
            self.assertEqual(glance_print.read({}, {"content": {"health": {"shown": False}, "per_row": bad}})["per_line"], 4, bad)

    def test_a_section_that_is_not_an_object_still_reads(self):
        self.assertEqual(glance_print.read({"as_at": "2026-01-05", "data": {}}, {"content": "x", "beside": 0})["per_line"], 4)


class ExcelNeedsNoChange(unittest.TestCase):
    def test_one_row_for_each_tile_whatever_the_line(self):
        for kw in ({}, {"per_row": 3}, {"beside": 1}):
            wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(select(7, **kw))))
            ws = wb["At a glance"]
            self.assertEqual([ws.cell(r, 1).value for r in range(5, ws.max_row + 1)], [f"ZQ-T{i}" for i in range(7)], kw)


if __name__ == "__main__":
    unittest.main()
