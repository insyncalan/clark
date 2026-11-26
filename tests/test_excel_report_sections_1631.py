"""Row 1631 P2: the remaining Dashboard section types are drawn on the Report sheet (excel_blocks, excel_cover.lines), words only.
Fictional data only.

Run: python3 dev/run_tests.py test_excel_report_sections_1631
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import DemoStore
from openpyxl import load_workbook

from clark import excel, excel_blocks
from clark import excel_cover as cover
from clark import page

_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")
IMG = "data:image/png;base64,AAAA"


def setUpModule():
    global _OLD
    _OLD, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


def sec(kind, title="", hidden=0, content=None, **more):
    return dict({"id": kind, "type": kind, "title": title, "hidden": hidden, "content": content}, **more)


def draw(*sections):
    return cover.lines({"name": "Harbour Lights upgrade"}, list(sections), [], "01-06-2030 20:30", None)


def words(lines):
    return [(x["kind"], x["text"]) for x in lines]


def one(kind, title, content=None, **more):
    return words(excel_blocks.block(sec(kind, title, content=content, **more)))


class EachType(unittest.TestCase):
    def test_each_section_type_draws_heading_and_words_in_dashboard_order(self):
        sections = [
            sec("headline", "S headline", content={"words": "Words one"}),
            sec("quote", "S quote", content={"quotes": [{"quote": "Quote one", "by": "Sam Fict", "role": "Sponsor"}]}),
            sec("textimage", "S textimage", content={"html": "<p>Para one</p><p>Para two</p>", "caption": "Note ti", "image": IMG}),
            sec("imagecap", "S imagecap", content={"image": IMG, "caption": "Note ic"}),
            sec("gallery", "S gallery", content={"pictures": [{"image": IMG, "caption": "Note g1"}, {"image": IMG, "caption": "Note g2"}]}),
            sec("figures3", "S figures3", figures=[{"label": "Open", "value": "7", "detail": "of 9"}]),
            sec("figures4", "S figures4", figures=[{"label": "Done", "value": "3", "detail": ""}]),
            sec("table", "S table", content={"cols": ["Col A", "Col B"], "rows": [["a1", "b1"]], "caption": "Note t"}),
            sec("contacts", "S contacts", content={"people": [{"name": "Pat Fict", "role": "Lead", "email": "ann@example.org", "phone": "123"}]}),
            sec("checklist", "S checklist", v=1, items=[{"text": "Send plan", "done": 1}, {"text": "Book room", "done": 0}]),
            sec("keydates", "S keydates", v=1, items=[{"label": "Go live", "date": "2030-02-01"}]),
        ]
        got = words(draw(*sections))
        heads = [t for k, t in got if k == "heading" and t.startswith("S ")]
        self.assertEqual(heads, [s["title"] for s in sections])
        texts = [t for k, t in got if k == "text"]
        for want in ("Words one", "Quote one", "Sam Fict · Sponsor", "Para one\nPara two", "Note ti", "Note ic", "Note g1", "Note g2",
                     "Open · 7 · of 9", "Done · 3", "Col A · Col B", "a1 · b1", "Note t", "Pat Fict · Lead · ann@example.org · 123",
                     "\u2611 Send plan", "\u2610 Book room", "Go live · 01-02-2030"):
            self.assertIn(want, texts)

    def test_a_picture_says_picture_not_in_this_export(self):
        self.assertIn(("text", "picture not in this export"), one("imagecap", "P", {"image": IMG, "caption": "C"}))
        self.assertIn(("text", "picture not in this export"), one("headline", "P", {"words": "W", "image": IMG}))
        self.assertIn(("text", "picture not in this export"), one("textimage", "P", {"words": ["W"], "image": IMG}))
        self.assertNotIn("data:image", json.dumps(one("imagecap", "P", {"image": IMG, "caption": "C"})))

    def test_a_gallery_says_n_pictures_not_in_this_export_with_captions(self):
        pics = [{"image": IMG, "caption": f"Note {i}"} for i in range(3)]
        got = one("gallery", "G", {"pictures": pics})
        self.assertEqual(got, [("heading", "G"), ("text", "3 pictures not in this export"), ("text", "Note 0"), ("text", "Note 1"), ("text", "Note 2")])

    def test_a_hidden_section_is_not_drawn(self):
        got = words(draw(sec("quote", "Hidden quote", hidden=1, content={"quotes": [{"quote": "CANARY"}]})))
        self.assertNotIn("CANARY", json.dumps(got))

    def test_nothing_to_say_is_no_lines_and_wrong_shapes_are_never_an_error(self):
        for kind in excel_blocks.BLOCKS:
            for c in (None, {}, 5, "x", [], {"quotes": 3, "pictures": "x", "people": None, "rows": [1], "cols": 4}):
                self.assertEqual(excel_blocks.block(sec(kind, "T", content=c, items=c, figures=c)), [], (kind, c))

    def test_the_ticks_are_the_word_exports_glyphs_with_one_space(self):
        got = words(excel_blocks.block(sec("checklist", "C", v=1, items=[{"text": "A", "done": 1}, {"text": "B", "done": 0}])))
        self.assertEqual(got, [("heading", "C"), ("text", "\u2611 A"), ("text", "\u2610 B")])
        self.assertEqual(excel_blocks.TICKED + excel_blocks.UNTICKED, "\u2611 \u2610 ")

    def test_a_section_with_no_title_has_no_heading_line(self):
        self.assertEqual(one("quote", "", {"quotes": [{"quote": "Q"}]}), [("text", "Q")])

    def test_every_type_of_the_ticket_is_drawn(self):
        for kind in ("headline", "quote", "textimage", "imagecap", "gallery", "figures3", "figures4", "table", "contacts", "checklist", "keydates"):
            self.assertIn(kind, excel_blocks.BLOCKS)


class InTheWorkbook(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-1631-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def export(self, rows):
        con = sqlite3.connect(self.demo.store.path)
        con.execute("DELETE FROM report_sections WHERE project = 'ABC'")
        for n, (kind, title, body, hidden) in enumerate(rows, 1):
            con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES "
                        "('ABC',?,?,?,?,0,?,?)", (f"s{n}", kind, title, json.dumps(body), hidden, n))
        con.commit()
        con.close()
        path = self.dir / "w.xlsx"
        excel.export_project(self.demo.store, "ABC", path, self.dir / "state.json", on="2030-06-01")
        ws = load_workbook(path)["Report"]
        return [c.value for row in ws.iter_rows() for c in row if c.value is not None]

    def test_quote_table_and_contacts_are_on_the_sheet_and_a_hidden_one_is_not(self):
        cells = self.export([
            ("quote", "Said", {"v": 1, "quotes": [{"quote": "Fictional praise", "by": "Sam", "role": ""}]}, 0),
            ("table", "Grid", {"v": 1, "cols": ["Col A"], "rows": [["cell-one"]], "caption": ""}, 0),
            ("contacts", "Who", {"v": 1, "people": [{"name": "Pat Fict", "role": "", "email": "", "phone": ""}]}, 0),
            ("quote", "Gone", {"v": 1, "quotes": [{"quote": "CANARY-HIDDEN", "by": "", "role": ""}]}, 1)])
        text = "\n".join(map(str, cells))
        for want in ("Said", "Fictional praise", "Grid", "Col A", "cell-one", "Who", "Pat Fict"):
            self.assertIn(want, text)
        self.assertNotIn("CANARY-HIDDEN", text)


if __name__ == "__main__":
    unittest.main()
