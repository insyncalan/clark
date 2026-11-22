"""Row 1264, slice 9 print: the Word report draws the glance template with the View's tiles on a line: the body's per_row (3 or 4,
4 when the body has none), and 2 when the section is half width (the published section's `beside` is 1, the page's slot-left/slot-right).
The Excel sheet has a row for each tile, so a line count changes nothing there.

Run: python3 dev/run_tests.py test_glance_word_excel_1264_print
"""
import io
import json
import re
import unittest
import zipfile

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


def tile_table_xml(pub):
    x = zipfile.ZipFile(io.BytesIO(docx_build.build(pub))).read("word/document.xml").decode()
    i = x.find("ZQ-T0")
    return x[x.rfind("<w:tbl>", 0, i):x.find("</w:tbl>", i)]


class WordTableGrid(unittest.TestCase):
    """The table's own grid and cells, read from the file: the reader's cell count would not see a wrong grid or a clipped extra cell."""

    def test_the_grid_has_a_column_for_each_tile_on_a_line(self):
        for kw, want in (({}, 4), ({"per_row": 3}, 3), ({"beside": 1}, 2)):
            self.assertEqual(len(re.findall(r"<w:gridCol ", tile_table_xml(select(10, **kw)))), want, kw)

    def test_every_line_has_exactly_the_grid_s_cells(self):
        for kw, want in (({}, 4), ({"per_row": 3}, 3), ({"beside": 1}, 2)):
            rows = re.findall(r"<w:tr[ >].*?</w:tr>", tile_table_xml(select(10, **kw)), re.S)
            self.assertEqual([len(re.findall(r"<w:tc>", r)) for r in rows], [want] * len(rows), kw)

    def test_each_tile_is_drawn_once_in_order(self):
        for kw in ({}, {"per_row": 3}, {"beside": 1}):
            found = re.findall(r"ZQ-T\d+", tile_table_xml(select(10, **kw)))
            self.assertEqual(found, [f"ZQ-T{i}" for i in range(10)], kw)

    def test_the_padding_cells_are_empty_and_unshaded(self):
        for kw, pad in (({"per_row": 3}, 2), ({}, 2), ({"beside": 1}, 0)):
            rows = re.findall(r"<w:tr[ >].*?</w:tr>", tile_table_xml(select(10, **kw)), re.S)
            cells = re.findall(r"<w:tc>.*?</w:tc>", rows[-1], re.S)
            tail = cells[len(cells) - pad:] if pad else []
            self.assertEqual(len(tail), pad, kw)
            for c in tail:
                self.assertNotIn("<w:shd", c, kw)
                self.assertNotIn("<w:t>", c, kw)


class ReaderPerLine(unittest.TestCase):
    def test_per_line_is_the_views(self):
        for kw, want in (({}, 4), ({"per_row": 3}, 3), ({"per_row": 4}, 4), ({"beside": 1}, 2), ({"beside": 1, "per_row": 3}, 2)):
            pub = select(5, **kw)
            self.assertEqual(glance_print.read(pub, full_section(pub))["per_line"], want, kw)

    def test_a_beside_that_is_not_one_is_not_half_width(self):
        for bad in (2, 0, None, "1", False):
            self.assertEqual(glance_print.read({}, {"beside": bad, "content": {"health": {"shown": False}}})["per_line"], 4, bad)

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



class RightSlotPerLine(unittest.TestCase):
    """READ 1856: publish.select flags only the FIRST of a side-by-side pair `beside` 1, so a glance in the right slot read 4 a line in print while the
    View draws 2 (shell.css .slot-right .tpl-gt)."""

    def pub(self, left_beside=1):
        i = fx.inputs()
        i["sections"] = [x for x in i["sections"] if x["type"] != "glance"]
        gt = {"project": "PUB", "id": "s-gt", "type": "glancetemplate", "title": "", "beside": 0, "hidden": 0, "sort_order": -1,
              "body": json.dumps({"v": 1, "bespoke": tiles(6), **ONLY_BESPOKE})}
        left = {"project": "PUB", "id": "s-left", "type": "text", "title": "L", "beside": left_beside, "hidden": 0, "sort_order": -2, "body": "<p>x</p>"}
        i["sections"][0:0] = [left, gt]
        return publish.select(i)

    def test_the_right_half_prints_two_a_line(self):
        pub = self.pub()
        self.assertEqual(glance_print.read(pub, full_section(pub))["per_line"], 2)
        self.assertEqual(cells_per_row(pub), [2, 2, 2])

    def test_the_left_half_still_two(self):
        i = fx.inputs()
        i["sections"] = [x for x in i["sections"] if x["type"] != "glance"]
        i["sections"][0:0] = [{"project": "PUB", "id": "s-gt", "type": "glancetemplate", "title": "", "beside": 1, "hidden": 0, "sort_order": -3,
                               "body": json.dumps({"v": 1, "bespoke": tiles(6), **ONLY_BESPOKE})},
                              {"project": "PUB", "id": "s-right", "type": "text", "title": "R", "beside": 0, "hidden": 0, "sort_order": -2, "body": "<p>y</p>"}]
        pub = publish.select(i)
        self.assertEqual(glance_print.read(pub, full_section(pub))["per_line"], 2)

    def test_a_glance_alone_after_a_pair_is_not_half(self):
        i = fx.inputs()
        i["sections"] = [x for x in i["sections"] if x["type"] != "glance"]
        i["sections"][0:0] = [{"project": "PUB", "id": "s-a", "type": "text", "title": "A", "beside": 1, "hidden": 0, "sort_order": -3, "body": "<p>a</p>"},
                              {"project": "PUB", "id": "s-b", "type": "text", "title": "B", "beside": 0, "hidden": 0, "sort_order": -2, "body": "<p>b</p>"},
                              {"project": "PUB", "id": "s-gt", "type": "glancetemplate", "title": "", "beside": 0, "hidden": 0, "sort_order": -1,
                               "body": json.dumps({"v": 1, "bespoke": tiles(6), **ONLY_BESPOKE})}]
        pub = publish.select(i)
        self.assertEqual(glance_print.read(pub, full_section(pub))["per_line"], 4)

    def test_the_right_half_keeps_beside_0_for_the_page(self):
        pub = self.pub()
        self.assertEqual([s["beside"] for s in pub["sections"][:2]], [1, 0])


class WordLinesAsHandedToTheTable(unittest.TestCase):
    """table() zips each row to its column count, so the printed file hides a line cut too wide or padded too long: read the rows the glance section hands it."""

    def handed(self, n, **kw):
        seen = []
        real = docx_build.table

        def spy(ctx, headers, weights, rows, borders=True):
            seen.append((weights, rows))
            return real(ctx, headers, weights, rows, borders)

        docx_build.table = spy
        try:
            docx_build.build(select(n, **kw))
        finally:
            docx_build.table = real
        weights, rows = next((w, r) for w, r in seen if r and any("ZQ-T0" in c[0] for c in r[0]))
        return weights, rows

    def check(self, n, per, **kw):
        weights, rows = self.handed(n, **kw)
        self.assertEqual(weights, [1] * per)
        self.assertEqual([len(r) for r in rows], [per] * len(rows))
        texts = [re.findall(r"ZQ-T\d+", c[0]) for r in rows for c in r]
        self.assertEqual([t[0] for t in texts if t], [f"ZQ-T{i}" for i in range(n)])
        self.assertEqual(sum(1 for t in texts if not t), len(texts) - n)

    def test_per_2_short_last_line(self):
        self.check(5, 2, beside=1)

    def test_per_3_short_last_line(self):
        self.check(10, 3, per_row=3)

    def test_per_3_two_short(self):
        self.check(11, 3, per_row=3)

    def test_per_4_short_last_line(self):
        self.check(10, 4, per_row=4)


class RightHalfReader(unittest.TestCase):
    def test_a_last_section_flagged_beside_has_no_right_half(self):
        pub = {"sections": [{"id": "a", "beside": 0}, {"id": "b", "beside": 1}]}
        self.assertFalse(glance_print._right_half(pub, {"id": "b"}))

    def test_a_section_without_an_id_is_never_the_right_half(self):
        pub = {"sections": [{"id": "a", "beside": 1}, {"beside": 0}]}
        self.assertFalse(glance_print._right_half(pub, {"beside": 0}))

    def test_the_walk_skips_the_right_half_of_a_pair(self):
        pub = {"sections": [{"id": "a", "beside": 1}, {"id": "b", "beside": 1}, {"id": "c", "beside": 0}]}
        self.assertTrue(glance_print._right_half(pub, {"id": "b"}))
        self.assertFalse(glance_print._right_half(pub, {"id": "c"}))

    def test_only_beside_1_opens_a_pair(self):
        pub = {"sections": [{"id": "a", "beside": 2}, {"id": "b", "beside": 0}]}
        self.assertFalse(glance_print._right_half(pub, {"id": "b"}))

    def test_a_row_that_is_not_a_section_is_skipped(self):
        pub = {"sections": ["x", {"id": "a", "beside": 1}, {"id": "b", "beside": 0}]}
        self.assertTrue(glance_print._right_half(pub, {"id": "b"}))

    def test_no_published_page_is_no_right_half(self):
        self.assertFalse(glance_print._right_half(None, {"id": "b"}))


if __name__ == "__main__":
    unittest.main()
