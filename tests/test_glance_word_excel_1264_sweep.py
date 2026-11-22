"""Row 1264, slice 7, the full mutation sweep: every changed expression of glance_print.py, the glancetemplate section of docx_build.py and
write_glance_sheet of excel_client.py was mutated (flip, drop, negate, off-by-one, swap); each test here kills one or more of the mutants
the first 36 tests let live. Exact XML and exact cells, so a size, a bold, a colour, a width or a row number cannot move unseen.

Run: python3 dev/run_tests.py test_glance_word_excel_1264_sweep
"""
import copy
import io
import json
import re
import unittest
import zipfile
from unittest import mock

from _paths import ROOT   # noqa: F401

import _publish_fixture as fx
from openpyxl import Workbook, load_workbook
from clark import docx_build, docx_graphics, excel, excel_client, glance_print, publish
from clark.section_kinds import base, glancetemplate
from test_glance_word_excel_1264 import BESPOKE, body, select
from test_tpl_glance_counts_1264 import AS_AT, rows

TOK = docx_build.TOKENS
GREY = f'<w:color w:val="{TOK["grey-700"]}"/>'
NONE_OF = {"builtin": {n: {"hidden": True} for n in ("overdue", "risks", "decisions")}}


def doc_xml(pub):
    return zipfile.ZipFile(io.BytesIO(docx_build.build(pub))).read("word/document.xml").decode("utf-8")


def cells_of(xml):
    return re.findall(r"<w:tc>.*?</w:tc>", xml, re.S)


def cell_with(xml, word):
    return next(c for c in cells_of(xml) if f">{word}<" in c)


def wb_of(pub, palette=None):
    return load_workbook(io.BytesIO(excel_client.workbook_bytes(pub, palette)))


def glance_sec(pub):
    return next(s for s in pub["sections"] if s["type"] == "glancetemplate")


def read(content, pub=None):
    return glance_print.read(pub or select(), {"type": "glancetemplate", "content": content})


def count(tile, rag="g", **kw):
    return {"tile": tile, "title": tile.title(), "value": 1, "detail": "d", "rag": rag, **kw}


class ReaderExact(unittest.TestCase):
    def test_every_field_of_every_kind_of_tile_exactly(self):
        got = read({"health": {"shown": False}, "order": ["decisions", 5, None, "zzz", "overdue", "risks", "bud", "mor", "ta", "tr", "tb", "tx"],
                    "counts": ["junk", 3, {"tile": "overdue", "title": "  Title O  ", "value": 4, "detail": " det O ", "rag": "r"},
                               {"tile": "risks", "title": "R", "value": 2, "detail": "d", "rag": "b"}, {"tile": "decisions", "title": "D", "detail": "dd"}],
                    "bespoke": [None, "x", {"id": "bud", "label": " L ", "figure": " F ", "tag": " T ", "note": " N ", "tone": "green"},
                                {"id": "mor", "label": 5, "figure": 6, "tag": 7, "note": 8, "tone": "neutral"},
                                {"id": "ta", "label": "a", "tone": "amber"}, {"id": "tr", "label": "r", "tone": "red"},
                                {"id": "tb", "label": "b", "tone": "blue"}, {"id": "tx", "label": "x", "tone": "zzz"}]})
        want = [("decisions", "D", "", "", "dd", None), ("overdue", "Title O", "4", "Overdue", "det O", "red"), ("risks", "R", "2", "", "d", "blue"),
                ("bud", "L", "F", "T", "N", "green"), ("mor", "", "", "", "", None), ("ta", "a", "", "", "", "amber"), ("tr", "r", "", "", "", "red"),
                ("tb", "b", "", "", "", "blue"), ("tx", "x", "", "", "", None)]
        self.assertEqual([(t["key"], t["label"], t["figure"], t["tag"], t["note"], t["colour"]) for t in got["tiles"]], want)
        self.assertIsNone(got["health_row"])

    def test_the_tag_and_colour_of_a_count_for_every_key_and_colour(self):
        tag = {("overdue", "r"): "Overdue", ("decisions", "a"): "Waiting", ("risks", "a"): "Watch", ("risks", "r"): "High"}
        any_ = {"g": "On track", "a": "At risk", "r": "Off track"}
        colour = {"g": "green", "a": "amber", "r": "red", "b": "blue", "n": None}
        for key in ("overdue", "risks", "decisions"):
            for rag in ("g", "a", "r", "b", "n", "z", None, 3):
                sec = {"health": {"shown": False}, "order": [key], "counts": [count(key, rag)]}
                if rag is None:
                    del sec["counts"][0]["rag"]
                t = read(sec)["tiles"][0]
                known = rag if rag in colour else "n"
                self.assertEqual(t["tag"], tag.get((key, known)) or any_.get(known, ""), (key, rag))
                self.assertEqual(t["colour"], colour[known], (key, rag))

    def test_the_bespoke_tones_all_five(self):
        want = {"green": "green", "amber": "amber", "red": "red", "blue": "blue", "neutral": None, "": None}
        for tone, c in want.items():
            self.assertEqual(read({"health": {"shown": False}, "order": ["x"], "bespoke": [{"id": "x", "label": "a", "tone": tone}]})["tiles"][0]["colour"], c, tone)

    def test_a_count_with_no_figure_is_an_empty_figure_and_a_value_of_zero_is_zero(self):
        c = {"health": {"shown": False}, "order": ["risks", "overdue"], "counts": [{"tile": "risks", "title": "R", "detail": "d", "rag": "g"}, count("overdue")]}
        c["counts"][1]["value"] = 0
        self.assertEqual([t["figure"] for t in read(c)["tiles"]], ["", "0"])

    def test_a_count_that_is_not_there_is_absent_and_the_default_order_fills_in(self):
        got = read({"order": ["risks"], "counts": [count("risks"), count("overdue"), count("decisions")], "bespoke": [{"id": "bud", "label": "B"}, {"id": "mor", "label": "M"}]})
        self.assertEqual([t["key"] for t in got["tiles"]], ["risks", "health", "overdue", "decisions", "bud", "mor"])
        got = read({"counts": [count("decisions")], "bespoke": [{"id": "bud", "label": "B"}]})
        self.assertEqual([t["key"] for t in got["tiles"]], ["health", "decisions", "bud"])

    def test_the_default_order_with_no_order_at_all(self):
        got = read({"counts": [count("decisions"), count("risks"), count("overdue")], "bespoke": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]})
        self.assertEqual([t["key"] for t in got["tiles"]], ["health", "overdue", "risks", "decisions", "a", "b"])
        self.assertEqual([t["key"] for t in read({})["tiles"]], ["health"])

    def test_an_order_entry_that_is_not_text_is_ignored_even_when_it_cannot_be_hashed(self):
        got = read({"order": [["x"], {}, "bud"], "bespoke": [{"id": "bud", "label": "B"}], "health": {"shown": False}})
        self.assertEqual([t["key"] for t in got["tiles"]], ["bud"])

    def test_a_count_or_bespoke_that_is_not_an_object_is_skipped_without_a_crash(self):
        got = read({"order": ["a"], "health": {"shown": False}, "counts": [["x"], "y"], "bespoke": [["x"], {"id": "a", "label": "A"}, "z"]})
        self.assertEqual([t["key"] for t in got["tiles"]], ["a"])

    def test_health_shown_only_false_hides_it_and_own_row_only_true_makes_a_row(self):
        for shown, here in ((False, False), (True, True), (None, True), (0, True), ("no", True)):
            self.assertEqual(any(t["key"] == "health" for t in read({"health": {"shown": shown}})["tiles"]), here, shown)
        self.assertTrue(any(t["key"] == "health" for t in read({"health": {}})["tiles"]))
        for own in (1, "yes", "true", None, False, 0):
            got = read({"health": {"own_row": own}})
            self.assertIsNone(got["health_row"], own)
            self.assertEqual([t["key"] for t in got["tiles"]], ["health"], own)

    def test_health_on_its_own_row_is_the_row_and_not_a_tile(self):
        got = read({"health": {"own_row": True}, "order": ["bud", "health"], "bespoke": [{"id": "bud", "label": "B"}]})
        self.assertEqual(got["health_row"]["key"], "health")
        self.assertEqual([t["key"] for t in got["tiles"]], ["bud"])
        got = read({"health": {"own_row": True, "shown": False}})
        self.assertIsNone(got["health_row"])
        self.assertEqual(got["tiles"], [])

    def test_a_health_that_is_not_an_object_is_the_default(self):
        for junk in ("x", ["y"], 3, None):
            got = read({"health": junk})
            self.assertEqual([t["key"] for t in got["tiles"]], ["health"], junk)
            self.assertIsNone(got["health_row"])
        self.assertEqual(glance_print.read(select(), {"content": ["not", "an", "object"]})["tiles"][0]["key"], "health")

    def test_the_health_tile_exactly(self):
        t = read({})["tiles"][0]
        self.assertEqual(t, {"key": "health", "label": "Project health", "figure": "At risk", "tag": "", "note": "ZQ-HEALTH-REASON", "colour": "amber"})

    def test_a_project_with_no_health_set_has_no_colour_and_still_reads(self):
        pub = select()
        pub["data"]["project"]["health"] = None
        t = read({}, pub)["tiles"][0]
        self.assertEqual((t["figure"], t["colour"]), ("Not set", None))
        pub["data"] = {}
        self.assertEqual(read({}, pub)["tiles"][0]["figure"], "Not set")

    def test_the_reasons_words_not_its_markup(self):
        pub = select()
        pub["data"]["project"]["health_reason"] = "<p>one</p><p>two</p>"
        self.assertEqual(read({}, pub)["tiles"][0]["note"], "one\ntwo")


class WordExact(unittest.TestCase):
    def test_a_tile_cell_is_exactly_its_four_lines_in_their_sizes_bold_and_colours(self):
        cell = cell_with(doc_xml(select(body(bespoke=[BESPOKE[0]]))), "ZQ-Budget")
        text = re.search(r'<w:b/><w:color w:val="([0-9A-F]{6})"/><w:sz w:val="32"/>', cell).group(1)
        fill = TOK["tone-green-tint"]
        self.assertNotEqual(text, fill)
        st = '<w:p><w:pPr><w:pStyle w:val="TableText"/></w:pPr><w:r><w:rPr>'
        end = "</w:rPr><w:t xml:space=\"preserve\">"
        want = (f'<w:tc><w:tcPr><w:tcW w:w="2409" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="{fill}"/></w:tcPr>'
                f'{st}{GREY}<w:sz w:val="16"/><w:szCs w:val="16"/>{end}ZQ-Budget</w:t></w:r></w:p>'
                f'{st}<w:b/><w:color w:val="{text}"/><w:sz w:val="32"/><w:szCs w:val="32"/>{end}87%</w:t></w:r></w:p>'
                f'{st}<w:b/><w:sz w:val="16"/><w:szCs w:val="16"/>{end}ZQ-Steady</w:t></w:r></w:p>'
                f'{st}<w:sz w:val="16"/><w:szCs w:val="16"/>{end}ZQ-Note one</w:t></w:r></w:p></w:tc>')
        self.assertEqual(cell, want)

    def test_a_tile_with_only_a_label_is_one_line_and_a_missing_figure_tag_note_leave_no_line(self):
        pub = select(body(bespoke=[{"id": "a", "label": "ZQ-A"}, {"id": "b", "label": "ZQ-B", "tag": "ZQ-Tb"}, {"id": "c", "label": "ZQ-C", "note": "ZQ-Nc"},
                                   {"id": "d", "label": "ZQ-D", "figure": "ZQ-Fd"}], health={"shown": False}, **NONE_OF))
        xml = doc_xml(pub)
        for word, n in (("ZQ-A", 1), ("ZQ-B", 2), ("ZQ-C", 2), ("ZQ-D", 2)):
            self.assertEqual(cell_with(xml, word).count("<w:p>"), n, word)
        self.assertNotIn("<w:color", cell_with(xml, "ZQ-B").replace(GREY, ""))
        self.assertIn('<w:sz w:val="32"/>', cell_with(xml, "ZQ-D"))
        self.assertNotIn("w:fill", cell_with(xml, "ZQ-A"))

    def test_a_tone_less_tile_has_no_shading_and_a_figure_with_no_colour(self):
        cell = cell_with(doc_xml(select(body(bespoke=[{"id": "a", "label": "ZQ-A", "figure": "9", "tone": "neutral"}], health={"shown": False}, **NONE_OF))), "ZQ-A")
        self.assertNotIn("w:fill", cell)
        self.assertIn('<w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>', cell)

    def test_the_own_row_health_is_a_shaded_paragraph_a_bar_of_its_colour_and_its_reason(self):
        pub = select(body(order=["health", "bud"], health={"own_row": True}))
        xml = doc_xml(pub)
        fill, text = TOK["tone-amber-tint"], re.search(r'<w:b/><w:color w:val="([0-9A-F]{6})"/></w:rPr><w:t xml:space="preserve">At risk', xml).group(1)
        want = (f'<w:p><w:pPr><w:keepNext/><w:shd w:val="clear" w:color="auto" w:fill="{fill}"/><w:spacing w:before="60" w:after="60"/></w:pPr>'
                f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Project health: </w:t></w:r>'
                f'<w:r><w:rPr><w:b/><w:color w:val="{text}"/></w:rPr><w:t xml:space="preserve">At risk</w:t></w:r></w:p>'
                f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="0" w:after="60"/></w:pPr><w:r><w:drawing>')
        self.assertIn(want, xml)
        self.assertIn('descr="Project health: At risk"', xml)
        tail = xml[xml.index(want):]
        self.assertIn('</w:drawing></w:r></w:p><w:p><w:r><w:t xml:space="preserve">ZQ-HEALTH-REASON</w:t></w:r></w:p><w:tbl>', tail)
        media = zipfile.ZipFile(io.BytesIO(docx_build.build(pub)))
        bars = [media.read(n) for n in media.namelist() if n.startswith("word/media/")]
        self.assertIn(docx_graphics.health_bar("amber", TOK)[0], bars)
        self.assertNotIn(docx_graphics.health_bar("green", TOK)[0], bars)

    ROW = {"key": "health", "label": "Project health", "figure": "Not set", "tag": "", "note": "", "colour": None}

    def test_health_with_no_colour_on_its_own_row_has_no_bar_no_shading_and_no_reason_line(self):
        pub = select()
        with mock.patch.object(glance_print, "read", lambda p, s: {"health_row": dict(self.ROW), "tiles": []}):
            part = docx_build.section_glancetemplate(pub, docx_build._Ctx(docx_build.palette(None), pub["as_at"]), "T", glance_sec(pub))
        self.assertIn('<w:p><w:pPr><w:spacing w:before="60" w:after="60"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Project health: </w:t></w:r>'
                      '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Not set</w:t></w:r></w:p>', part)
        self.assertNotIn("drawing", part)
        self.assertNotIn("<w:tbl>", part)
        self.assertEqual(part.count("<w:p>"), 2)

    def test_a_section_with_only_the_own_row_health_is_still_written(self):
        pub = select()
        with mock.patch.object(glance_print, "read", lambda p, s: {"health_row": dict(self.ROW), "tiles": []}):
            part = docx_build.section_glancetemplate(pub, docx_build._Ctx(docx_build.palette(None), pub["as_at"]), "T", glance_sec(pub))
        self.assertIn("Project health: ", part)

    def test_a_section_with_only_tiles_is_written_and_has_no_health_row(self):
        xml = doc_xml(select(body(health={"shown": False}, **NONE_OF)))
        self.assertIn("ZQ-Budget", xml)
        self.assertNotIn("Project health", xml)

    def test_the_table_is_four_equal_columns_and_the_last_line_is_padded_with_empty_unshaded_cells(self):
        many = [{"id": f"t{i}", "label": f"ZQ-T{i}", "figure": str(i), "tone": "green"} for i in range(5)]
        xml = doc_xml(select(body(bespoke=many, health={"shown": False}, **NONE_OF)))
        tbl = next(t for t in re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S) if "ZQ-T0" in t)
        self.assertIn('<w:tblGrid><w:gridCol w:w="2409"/><w:gridCol w:w="2409"/><w:gridCol w:w="2409"/><w:gridCol w:w="2411"/></w:tblGrid>', tbl)
        rows = re.findall(r"<w:tr>.*?</w:tr>", tbl, re.S)
        self.assertEqual([len(cells_of(r)) for r in rows], [4, 4])
        for i in range(5):
            self.assertEqual(tbl.count(f">ZQ-T{i}<"), 1, i)
        empty = '<w:tc><w:tcPr><w:tcW w:w="%s" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:pStyle w:val="TableText"/></w:pPr></w:p></w:tc>'
        self.assertTrue(rows[1].endswith(empty % "2409" * 2 + empty % "2411" + "</w:tr>"))
        self.assertEqual(len(cells_of(rows[1])[1:]), 3)
        self.assertTrue(all("w:fill" not in c for c in cells_of(rows[1])[1:]))

    def test_eight_tiles_make_two_lines_of_four_with_one_paragraph_each(self):
        many = [{"id": f"t{i}", "label": f"ZQ-T{i}"} for i in range(8)]
        xml = doc_xml(select(body(bespoke=many, health={"shown": False}, **NONE_OF)))
        tbl = next(t for t in re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S) if "ZQ-T0" in t)
        rows = re.findall(r"<w:tr>.*?</w:tr>", tbl, re.S)
        self.assertEqual([len(cells_of(r)) for r in rows], [4, 4])
        self.assertEqual(tbl.count("<w:p>"), 8)

    def test_the_heading_is_the_section_titles_word(self):
        self.assertEqual(docx_build.TITLES["glancetemplate"], "At a glance")
        self.assertIn(docx_build.section_glancetemplate, docx_build.SIMPLE.values())
        self.assertIs(docx_build.SIMPLE["glancetemplate"], docx_build.section_glancetemplate)
        self.assertEqual(glance_print.PER_LINE, 4)

    def test_nothing_to_show_is_an_empty_string_and_a_row_alone_is_not(self):
        empty = {"type": "glancetemplate", "content": {"health": {"shown": False}, "order": [], "bespoke": []}}
        self.assertEqual(docx_build.section_glancetemplate(select(), mock.Mock(), "T", empty), "")


class ExcelExact(unittest.TestCase):
    PAL = {"fill": "112233", "text": "445566"}

    def setUp(self):
        self.pub = select(body(order=["health", "bud", "mor"], health={"own_row": True}, **NONE_OF))
        self.ws = wb_of(self.pub, self.PAL)["At a glance"]

    def test_the_title_band_rows_one_and_two_are_filled_across_all_four_columns_in_the_palette(self):
        ws, (title, sub) = self.ws, excel_client.title_text(self.pub)
        self.assertEqual((ws["A1"].value, ws["A2"].value), (title, sub))
        for r in (1, 2):
            for c in (1, 2, 3, 4):
                self.assertEqual(ws.cell(r, c).fill.fgColor.rgb[-6:], "112233", (r, c))
            self.assertEqual(ws.cell(r, 5).fill.fill_type, None)
        self.assertEqual((ws["A1"].font.size, ws["A1"].font.bold, ws["A1"].font.color.rgb[-6:]), (16, True, "445566"))
        self.assertEqual((ws["A2"].font.size, bool(ws["A2"].font.bold), ws["A2"].font.color.rgb[-6:]), (11, False, "445566"))
        self.assertEqual(ws.row_dimensions[1].height, 26)
        self.assertIsNone(ws.row_dimensions[2].height)

    def test_the_column_heads_are_on_row_four_with_their_widths_and_nothing_else_is_a_column(self):
        ws = self.ws
        self.assertEqual(ws.max_column, 4)
        self.assertEqual([ws.cell(4, c).value for c in (1, 2, 3, 4)], ["Label", "Figure", "Tag", "Note"])
        self.assertEqual([ws.column_dimensions[l].width for l in "ABCD"], [28, 14, 16, 60])
        for c in (1, 2, 3, 4):
            self.assertEqual((ws.cell(4, c).font.bold, ws.cell(4, c).font.color.rgb[-6:], ws.cell(4, c).fill.fgColor.rgb[-6:]), (True, "445566", "112233"))
        for c in (1, 2, 3, 4):
            self.assertIsNone(ws.cell(3, c).value)

    def test_the_rows_start_on_five_in_the_four_columns_in_order_in_the_body_font_wrapped_at_the_top(self):
        ws = self.ws
        self.assertEqual([[ws.cell(r, c).value for c in (1, 2, 3, 4)] for r in (5, 6, 7)],
                         [["Project health", "At risk", None, "ZQ-HEALTH-REASON"], ["ZQ-Budget", "87%", "ZQ-Steady", "ZQ-Note one"], ["ZQ-Morale", "ZQ-High", None, None]])
        self.assertEqual(ws.max_row, 7)
        for r in (5, 6, 7):
            for c in (1, 2, 3, 4):
                cell = ws.cell(r, c)
                self.assertEqual((cell.font.name, cell.font.size, bool(cell.font.bold)), (excel_client.BODY.name, 11, False), (r, c))
                self.assertEqual((cell.alignment.wrap_text, cell.alignment.vertical), (True, "top"), (r, c))
                self.assertTrue(cell.protection.locked)

    def test_the_headline_goes_on_row_three_across_four_columns_in_the_palette(self):
        with mock.patch.object(excel_client, "headline_line", lambda p: "ZQ-LINE"):
            ws = wb_of(self.pub, self.PAL)["At a glance"]
        self.assertEqual(ws["A3"].value, "ZQ-LINE")
        for c in (1, 2, 3, 4):
            self.assertEqual(ws.cell(3, c).fill.fgColor.rgb[-6:], "112233", c)
        self.assertEqual(ws["A3"].font.color.rgb[-6:], "445566")
        self.assertEqual(ws["A4"].value, "Label")

    def test_the_sheet_is_frozen_below_the_heads_set_up_to_print_protected_and_named(self):
        ws = self.ws
        self.assertEqual(ws.freeze_panes, "A5")
        self.assertEqual((ws.page_setup.orientation, ws.page_setup.fitToWidth, ws.page_setup.fitToHeight, str(ws.page_setup.paperSize)), ("landscape", 1, 0, ws.PAPERSIZE_A4))
        self.assertTrue(ws.sheet_properties.pageSetUpPr.fitToPage)
        self.assertTrue(ws.protection.sheet)
        wb = wb_of(self.pub, self.PAL)
        dn = wb.defined_names[excel.CLIENT_COPY_NAME]
        self.assertEqual(dn.attr_text, "'At a glance'!$A$1")
        self.assertTrue(dn.hidden)

    def test_a_cell_keeps_its_words_without_the_characters_a_workbook_cannot_hold(self):
        sec = {"type": "glancetemplate", "content": {"health": {"shown": False}, "order": ["a"],
                                                      "bespoke": [{"id": "a", "label": "A\x0bB\r\nC\rD", "figure": "1\x07", "tag": "t\x1cu", "note": "n"}]}}
        ws = excel_client.write_glance_sheet(Workbook(), select(), sec)
        self.assertEqual([ws.cell(5, c).value for c in (1, 2, 3, 4)], ["A B\nC\nD", "1", "t u", "n"])

    def test_two_glance_sections_make_two_sheets_the_second_named_by_its_place_and_the_name_points_at_the_last(self):
        pub = select()
        second = copy.deepcopy(glance_sec(pub))
        second["id"] = "s-gt2"
        pub["sections"].append(second)
        wb = wb_of(pub)
        names = wb.sheetnames
        first = names.index("At a glance")
        self.assertEqual(names[first + 1], f"At a glance {first + 2}")
        self.assertEqual(len([n for n in names if n.startswith("At a glance")]), 2)
        self.assertEqual(wb.defined_names[excel.CLIENT_COPY_NAME].attr_text, f"'{names[first + 1]}'!$A$1")
        self.assertEqual(wb[names[first + 1]]["A5"].value, wb["At a glance"]["A5"].value)

    def test_the_title_band_is_text_without_forbidden_characters_and_never_a_formula(self):
        with mock.patch.object(excel_client, "title_text", lambda p: ("=A\x0bB", "+C\x07D")):
            ws = wb_of(self.pub)["At a glance"]
        self.assertEqual((ws["A1"].value, ws["A2"].value), ("=A B", "+CD"))
        for cell in (ws["A1"], ws["A2"]):
            self.assertEqual(cell.data_type, "s")
            self.assertTrue(cell.quotePrefix)

    def test_the_function_returns_its_sheet_or_nothing(self):
        pub = select()
        ws = excel_client.write_glance_sheet(Workbook(), pub, glance_sec(pub))
        self.assertEqual(ws.title, "At a glance")
        empty = {"type": "glancetemplate", "content": {"health": {"shown": False}, "order": [], "bespoke": []}}
        self.assertIsNone(excel_client.write_glance_sheet(Workbook(), pub, empty))

    def test_only_a_glance_template_section_makes_a_glance_sheet(self):
        self.assertNotIn("At a glance", wb_of(select(with_section=False)).sheetnames)


class Killers(unittest.TestCase):
    """The survivors the read of afcd20e6 listed."""

    def test_a_content_that_is_not_an_object_is_nothing_whatever_the_section_holds(self):
        sec = {"type": "glancetemplate", "content": "junk", "order": ["bud"], "bespoke": [{"id": "bud", "label": "ZQ"}], "health": {"shown": False}}
        got = glance_print.read(select(), sec)
        self.assertEqual([t["key"] for t in got["tiles"]], ["health"], "the section's own keys are never read as the content")
        self.assertIsNone(got["health_row"])

    def test_the_health_note_is_the_reason_as_plain_words_with_no_edge_spaces(self):
        pub = select()
        pub["data"]["project"] = {"health": "At risk", "health_reason": "<p>  Fictional <b>reason</b>  </p>"}
        got = read({}, pub)["tiles"][0]
        self.assertEqual((got["key"], got["figure"], got["note"]), ("health", "At risk", "Fictional reason"))

    def test_a_hidden_typed_tile_is_in_no_published_content_and_not_in_the_order(self):
        value = {"v": 1, "order": ["a", "b", "c", "health", "overdue", "risks", "decisions"],
                 "bespoke": [{"id": "a", "label": "A"}, {"id": "b", "label": "B", "hidden": True}, {"id": "c", "label": "C", "hidden": False}]}
        got = glancetemplate.published(value, None)["content"]
        self.assertEqual([t["id"] for t in got["bespoke"]], ["a", "c"])
        self.assertNotIn("b", got["order"])
        self.assertEqual(got["order"], ["a", "c", "health", "overdue", "risks", "decisions"])

    def test_a_dozen_typed_tiles_and_the_counts_and_health_all_print_in_word_and_in_the_sheet(self):
        many = [{"id": f"t{i}", "label": f"ZQ-T{i}"} for i in range(12)]
        pub = select(body(bespoke=many))
        words = [t["label"] for t in glance_print.read(pub, glance_sec(pub))["tiles"]]
        for i in range(12):
            self.assertIn(f"ZQ-T{i}", words)
        sheet = [ws for ws in wb_of(pub).worksheets if ws.title.startswith("At a glance")][0]
        self.assertEqual([sheet.cell(r, 1).value for r in range(5, sheet.max_row + 1)].count(None), 0)
        self.assertGreaterEqual(sheet.max_row - 4, 12)
        self.assertEqual(sum(f">ZQ-T{i}<" in doc_xml(pub) for i in range(12)), 12)

    def test_every_character_an_xlsx_cannot_hold_is_dropped_or_spaced_and_the_rest_kept(self):
        spaced = {"\x0b", "\x0c", "\x1c", "\x1d", "\x1e"}
        for code in list(range(0x20)) + [0x7f, 0x80, 0x9f, 0xa0, 0xd7ff, 0xe000, 0xfffd, 0xfffe, 0xffff, 0x10000]:
            ch = chr(code)
            want = "a b" if ch in spaced else ("ab" if (code < 0x20 and ch not in "\t\n\r") or code in (0xfffe, 0xffff) else "a" + ch + "b")
            if ch == "\r":
                want = "a\nb"
            with self.subTest(code=hex(code)):
                self.assertEqual(excel.cell_text("a" + ch + "b"), want)
        for code in (0xd800, 0xdbff, 0xdc00, 0xdfff):
            with self.subTest(code=hex(code)):
                self.assertEqual(excel.cell_text("a" + chr(code) + "b"), "ab")

    def test_a_glance_sheet_never_takes_a_name_that_is_already_used(self):
        pub = select()
        wb = Workbook()
        wb.active.title = "At a glance"
        wb.create_sheet("At a glance 3")
        ws = excel_client.write_glance_sheet(wb, pub, glance_sec(pub))
        self.assertEqual(ws.title, "At a glance 4")
        self.assertEqual(wb.sheetnames, ["At a glance", "At a glance 3", "At a glance 4"])


class SecondRead(unittest.TestCase):
    """The second read of the slice: sizes, the health eye alone, the label, the sheet position, the two defaults."""

    def _run_of(self, pub, word):
        runs = re.findall(r"<w:r>.*?</w:r>", doc_xml(pub), re.S)
        return [r for r in runs if word in r][0]

    def test_the_figure_is_16_points_and_label_tag_and_note_are_8(self):
        pub = select(body(bespoke=[{"id": "a", "label": "ZQLAB", "figure": "ZQFIG", "tag": "ZQTAG", "note": "ZQNOTE"}]))
        self.assertIn('w:val="32"', self._run_of(pub, "ZQFIG"))
        for w in ("ZQLAB", "ZQTAG", "ZQNOTE"):
            self.assertIn('w:val="16"', self._run_of(pub, w))

    def test_counts_alone_are_published_with_health_off_and_no_typed_tile(self):
        out = glancetemplate.published({"v": 1, "health": {"shown": False}}, base.Context(rows(), AS_AT))
        self.assertEqual([c["tile"] for c in out["content"]["counts"]], ["overdue", "risks", "decisions"])
        self.assertEqual(out["content"]["bespoke"], [])

    def test_the_health_eye_alone_prints_its_row_in_word_and_in_the_sheet(self):
        pub = select(body(bespoke=[], builtin={n: {"hidden": True} for n in ("overdue", "risks", "decisions")}))
        sec = glance_sec(pub)
        self.assertIsNotNone(sec, "the section is in the file")
        self.assertEqual([t["key"] for t in glance_print.read(pub, sec)["tiles"]], ["health"])
        self.assertIn("Project health", doc_xml(pub))
        ws = [w for w in wb_of(pub).worksheets if w.title.startswith("At a glance")][0]
        self.assertEqual(ws.cell(5, 1).value, "Project health")

    def test_nothing_to_show_at_all_is_no_section(self):
        pub = select(body(bespoke=[], health={"shown": False}, builtin={n: {"hidden": True} for n in ("overdue", "risks", "decisions")}))
        self.assertIsNone(next((x for x in pub["sections"] if x["type"] == "glancetemplate"), None))

    def test_the_health_tile_label_is_the_tile_title(self):
        pub = select()
        self.assertEqual(glance_print.read(pub, glance_sec(pub))["tiles"][0]["label"], "Project health")

    def test_the_sheet_suffix_is_the_sheets_position(self):
        pub = select()
        wb = Workbook()
        wb.active.title = "Other"
        wb.create_sheet("Other 2")
        first = excel_client.write_glance_sheet(wb, pub, glance_sec(pub))
        second = excel_client.write_glance_sheet(wb, pub, glance_sec(pub))
        self.assertEqual((first.title, second.title), ("At a glance", "At a glance 4"))


if __name__ == "__main__":
    unittest.main()
