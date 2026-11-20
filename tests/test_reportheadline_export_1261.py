"""Row 1261: the Report headline in the Word report, the client Excel workbook and the published file's section entry
(docx_build.section_reportheadline, excel_client.headline_line / put_headline, publish.select). Python only: the page's own print
is the page's CSS and is not covered here.

Run: python3 dev/run_tests.py test_reportheadline_export_1261
Rows are the #39 plant with one reportheadline section put in front, passed through publish.select() as the published file's rows are.
"""
import copy
import io
import json
import re
import unittest
import zipfile

from _paths import ROOT   # noqa: F401  (puts src/ and vendor/ on the path)

import _publish_fixture as fx
from openpyxl import load_workbook
from clark import docx_build, docx_read, excel_client, excel_colours, publish

BODY = {"v": 1, "health": "at_risk", "headline": "Go live moves one week", "sentence": "The vendor test slipped to Friday."}
TONE = {"on_track": "tone-green-tint", "at_risk": "tone-amber-tint", "off_track": "tone-red-tint"}
WORD = {"on_track": "On track", "at_risk": "At risk", "off_track": "Off track"}


def inputs(body=BODY, hidden=0, with_section=True):
    i = fx.inputs()
    if with_section:
        i["sections"].insert(0, {"project": "PUB", "id": "s-rh", "type": "reportheadline", "title": "", "beside": 0, "hidden": hidden,
                                 "sort_order": 0, "body": json.dumps(body) if isinstance(body, dict) else body})
    return i


def select(**kw):
    return publish.select(inputs(**kw))


def doc_xml(data):
    return zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")


def texts(data):
    return [b.get("text", "") for b in docx_read.read(data, "report.docx").blocks]


def sheet(pub):
    return load_workbook(io.BytesIO(excel_client.workbook_bytes(pub)))


class Published(unittest.TestCase):
    def test_the_file_carries_the_three_fields_by_name(self):
        s = [x for x in select()["sections"] if x["type"] == "reportheadline"]
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["content"], {"health": "at_risk", "headline": BODY["headline"], "sentence": BODY["sentence"], "pill": True})

    def test_a_hidden_or_empty_section_is_not_in_the_file_or_the_exports(self):
        for kw in ({"hidden": 1}, {"body": ""}, {"body": {"v": 1}}):
            pub = select(**kw)
            self.assertFalse([x for x in pub["sections"] if x["type"] == "reportheadline"], kw)
            self.assertEqual(docx_build.build(pub), docx_build.build(select(with_section=False)), kw)
            self.assertEqual(excel_client.headline_line(pub), "", kw)


class Word(unittest.TestCase):
    def test_pill_headline_sentence_in_that_order_and_each_once(self):
        t = texts(docx_build.build(select()))
        at = [t.index(w) for w in ("At risk", BODY["headline"], BODY["sentence"])]
        self.assertEqual(at, sorted(at))
        for w in ("At risk", BODY["headline"], BODY["sentence"]):
            self.assertEqual(t.count(w), 1, w)

    def test_it_comes_where_the_page_puts_it_before_the_other_sections(self):
        t = texts(docx_build.build(select()))
        self.assertLess(t.index(BODY["headline"]), t.index("Current state"))

    def test_the_pill_is_shaded_in_the_health_colour_for_each_health(self):
        for h, word in WORD.items():
            xml = doc_xml(docx_build.build(select(body={**BODY, "health": h})))
            fill = docx_build.palette()[TONE[h]] if TONE[h] in docx_build.palette() else docx_build.TOKENS[TONE[h]]
            para = re.search(r"<w:p>(?:(?!</w:p>).)*?" + word + r"(?:(?!</w:p>).)*?</w:p>", xml, re.S)
            self.assertIsNotNone(para, h)
            self.assertIn(f'w:fill="{fill}"', para.group(0), h)
            others = [docx_build.TOKENS[t] for k, t in TONE.items() if k != h]
            self.assertFalse(any(f'w:fill="{o}"' in para.group(0) for o in others), h)

    def test_the_headline_is_bold_and_the_sentence_is_not(self):
        xml = doc_xml(docx_build.build(select()))
        def runs(text):
            return re.search(r"<w:r><w:rPr>((?:(?!</w:rPr>).)*)</w:rPr><w:t[^>]*>" + re.escape(text), xml).group(1)
        self.assertIn("<w:b/>", runs(BODY["headline"]))
        self.assertNotIn("<w:b/>", runs(BODY["sentence"]))

    def test_no_health_means_no_pill_and_no_not_set_words(self):
        data = docx_build.build(select(body={"v": 1, "headline": "Only words"}))
        self.assertIn("Only words", texts(data))
        self.assertNotIn("Not set", "\n".join(texts(data)))
        for w in WORD.values():
            self.assertNotIn(w, texts(data))

    def test_health_alone_is_still_a_block(self):
        self.assertIn("Off track", texts(docx_build.build(select(body={"v": 1, "health": "off_track"}))))

    def test_it_has_no_heading_of_its_own(self):
        heads = lambda d: [b["text"] for b in docx_read.read(d, "r.docx").blocks if b["kind"] == "heading"]
        self.assertEqual(heads(docx_build.build(select())), heads(docx_build.build(select(with_section=False))))

    def test_a_hand_made_empty_content_adds_nothing(self):
        pub = select()
        for s in pub["sections"]:
            if s["type"] == "reportheadline":
                s["content"] = {"health": "", "headline": " ", "sentence": ""}
        self.assertEqual(docx_build.build(pub), docx_build.build(select(with_section=False)))

    def test_markup_and_odd_values_stay_text(self):
        pub = select()
        for s in pub["sections"]:
            if s["type"] == "reportheadline":
                s["content"] = {"health": ["x"], "headline": "<w:p>&amp;</w:p>", "sentence": {"a": 1}}
        data = docx_build.build(pub)
        self.assertIn("<w:p>&amp;</w:p>", texts(data))
        self.assertNotIn("<w:p>&amp;</w:p>", doc_xml(data))
        self.assertNotIn("{'a'", doc_xml(data))

    def test_the_same_rows_give_the_same_bytes(self):
        self.assertEqual(docx_build.build(select()), docx_build.build(select()))


class Excel(unittest.TestCase):
    LINE = "At risk · Go live moves one week · The vendor test slipped to Friday."

    def test_every_sheet_has_the_line_on_row_3_and_its_heads_still_on_row_4(self):
        wb = sheet(select())
        plain = sheet(select(with_section=False))
        self.assertGreaterEqual(len(wb.worksheets), 2)
        for ws, ref in zip(wb.worksheets, plain.worksheets):
            self.assertEqual(ws["A3"].value, self.LINE, ws.title)
            self.assertIsNone(ref["A3"].value)
            self.assertEqual([c.value for c in ws[4]], [c.value for c in ref[4]], ws.title)
            self.assertEqual(ws.max_row, ref.max_row, ws.title)

    def test_the_line_is_locked_text_in_the_title_band_fill(self):
        ws = sheet(select()).worksheets[0]
        self.assertTrue(ws["A3"].protection.locked)
        self.assertEqual(ws["A3"].fill.fgColor.rgb, ws["A1"].fill.fgColor.rgb)

    def test_parts_are_left_out_when_not_there(self):
        self.assertEqual(excel_client.headline_line(select(body={"v": 1, "headline": "Only words"})), "Only words")
        self.assertEqual(excel_client.headline_line(select(body={"v": 1, "health": "on_track"})), "On track")

    def test_odd_values_in_the_content_are_ignored_not_raised(self):
        pub = select()
        for s in pub["sections"]:
            if s["type"] == "reportheadline":
                s["content"] = {"health": ["x"], "headline": {"a": 1}, "sentence": "Kept"}
        self.assertEqual(excel_client.headline_line(pub), "Kept")
        excel_client.workbook_bytes(pub)

    def test_a_formula_is_text_not_a_formula(self):
        ws = sheet(select(body={"v": 1, "headline": "=1+1"})).worksheets[0]
        self.assertNotEqual(ws["A3"].data_type, "f")

    def test_the_same_rows_give_the_same_bytes(self):
        self.assertEqual(excel_client.workbook_bytes(select()), excel_client.workbook_bytes(select()))

    def test_no_line_without_the_section(self):
        for ws in sheet(select(with_section=False)).worksheets:
            self.assertIsNone(ws["A3"].value)


if __name__ == "__main__":
    unittest.main()
