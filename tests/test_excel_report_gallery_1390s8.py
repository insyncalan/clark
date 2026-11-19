"""Row 1390 slice 8: the gallery section is drawn on the Report sheet as captions and a "pictures not in this export" line
(excel_gallery, excel_cover.lines). The .xlsx is opened with openpyxl. Fictional data only.

Run: python3 dev/run_tests.py test_excel_report_gallery_1390s8
"""
import base64
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import DemoStore
from openpyxl import load_workbook

from clark import excel, excel_gallery
from clark import excel_cover as cover
from clark import page

_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")
PNG = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc0f01f0005000201a5f645400000000049454e44ae426082")).decode()


def setUpModule():
    global _OLD
    _OLD, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


def pic(caption="", alt=""):
    return {"image": PNG, "caption": caption, "alt": alt}


def sec(pictures, title="", hidden=0, kind="gallery"):
    return {"id": "g", "type": kind, "title": title, "body": "", "hidden": hidden, "content": {"pictures": pictures}}


def words(lines):
    return [(x["kind"], x["text"]) for x in lines]


def draw(*sections):
    return cover.lines({"name": "Harbour Lights upgrade"}, list(sections), [], "01-06-2030 20:30", None)


class TheBlock(unittest.TestCase):
    def test_heading_captions_in_order_then_the_line(self):
        got = excel_gallery.gallery_block(sec([pic("Quay at dawn"), pic("Crane two")], title="Site photos"))
        self.assertEqual(words(got), [("heading", "Site photos"), ("text", "Quay at dawn"), ("text", "Crane two"),
                                      ("text", "2 pictures not in this export")])

    def test_one_picture_uses_the_singular_words(self):
        got = excel_gallery.gallery_block(sec([pic("Only one")]))
        self.assertEqual(words(got)[-1], ("text", "1 picture not in this export"))
        self.assertEqual(words(got)[0], ("heading", "Gallery"))

    def test_the_count_is_every_picture_including_those_with_no_caption(self):
        got = excel_gallery.gallery_block(sec([pic("A"), pic(""), pic("  "), pic("D"), pic(""), pic("F")]))
        self.assertEqual(words(got), [("heading", "Gallery"), ("text", "A"), ("text", "D"), ("text", "F"),
                                      ("text", "6 pictures not in this export")])

    def test_nothing_to_show_is_no_lines_not_even_the_heading(self):
        for pics in ([], None, "x", 5, {}, [None, 3, "a"]):
            self.assertEqual(excel_gallery.gallery_block(sec(pics)), [], pics)
        self.assertEqual(excel_gallery.gallery_block({"type": "gallery"}), [])
        self.assertEqual(excel_gallery.gallery_block({"type": "gallery", "content": 7}), [])

    def test_a_caption_of_the_wrong_type_is_no_caption_but_the_picture_counts(self):
        got = excel_gallery.gallery_block(sec([{"image": PNG, "caption": 5}, {"image": PNG}]))
        self.assertEqual(words(got), [("heading", "Gallery"), ("text", "2 pictures not in this export")])

    def test_more_than_six_are_not_counted_past_the_six_slots(self):
        self.assertEqual(words(excel_gallery.gallery_block(sec([pic()] * 9)))[-1], ("text", "6 pictures not in this export"))

    def test_a_caption_is_one_line_and_cut(self):
        got = excel_gallery.gallery_block(sec([pic("a\n  b\tc"), pic("x" * 900)]))
        self.assertEqual(got[1]["text"], "a b c")
        self.assertEqual(len(got[2]["text"]), 500)

    def test_another_type_still_draws_only_by_its_own_name(self):
        self.assertEqual(draw(sec([pic("A")], kind="callout"))[2:4], draw()[2:4])


class OnTheReport(unittest.TestCase):
    def test_it_sits_in_the_dashboard_order(self):
        got = draw({"type": "text", "title": "Before", "body": "<p>One</p>", "hidden": 0}, sec([pic("A")], title="Photos"),
                   {"type": "text", "title": "After", "body": "<p>Two</p>", "hidden": 0})
        self.assertEqual([t for k, t in words(got) if k == "heading"][:3], ["Before", "Photos", "After"])

    def test_a_hidden_one_is_not_drawn(self):
        self.assertNotIn("Gallery", [t for k, t in words(draw(sec([pic("CANARY")], hidden=1))) if k == "heading"])
        self.assertNotIn("CANARY", [t for _, t in words(draw(sec([pic("CANARY")], hidden=1)))])

    def test_a_long_title_is_cut_under_the_cell_limit(self):
        got = draw(sec([pic("A")], title="t" * 40000))
        self.assertTrue(all(len(x["text"]) <= cover.LIMIT for x in got))
        self.assertEqual(len(got[2]["text"]), 200)

    def test_the_picture_itself_is_never_in_the_lines(self):
        self.assertNotIn("base64", json.dumps(draw(sec([pic("A")]))))


class InTheWorkbook(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-s8-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def export(self, body, hidden=0):
        con = sqlite3.connect(self.demo.store.path)
        con.execute("DELETE FROM report_sections WHERE project = 'ABC'")
        con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES "
                    "('ABC','g','gallery','',?,0,?,1)", (json.dumps(body), hidden))
        con.commit()
        con.close()
        path = self.dir / "w.xlsx"
        excel.export_project(self.demo.store, "ABC", path, self.dir / "state.json", on="2030-06-01")
        ws = load_workbook(path)["Cover"]
        return ws, [c.value for row in ws.iter_rows() for c in row if c.value is not None]

    def body(self, *captions):
        return {"v": 1, "items": {str(i + 1): {"caption": c} for i, c in enumerate(captions)},
                "pictures": {str(i + 1): PNG for i in range(len(captions))}}

    def test_captions_and_the_line_are_on_the_sheet(self):
        _, cells = self.export(self.body("Quay at dawn", "Crane two"))
        self.assertIn("Quay at dawn", cells)
        self.assertIn("2 pictures not in this export", cells)

    def test_a_gallery_with_no_picture_is_not_on_the_sheet(self):
        _, cells = self.export({"v": 1, "items": {"1": {"caption": "CANARY-NOPIC"}}})
        self.assertNotIn("CANARY-NOPIC", "\n".join(map(str, cells)))

    def test_a_hidden_section_is_not_on_the_sheet(self):
        _, cells = self.export(self.body("CANARY-HIDDEN"), hidden=1)
        self.assertNotIn("CANARY-HIDDEN", "\n".join(map(str, cells)))
        self.assertNotIn("1 picture not in this export", cells)

    def test_no_picture_is_put_in_the_workbook(self):
        self.export(self.body("A"))
        import zipfile
        names = zipfile.ZipFile(self.dir / "w.xlsx").namelist()
        self.assertFalse([n for n in names if n.startswith("xl/media/") and "gallery" in n])

    def test_a_caption_that_looks_like_a_formula_stays_text(self):
        ws, _ = self.export(self.body("=1+1", "@SUM(1)", "-2+3", "+4"))
        found = [c for row in ws.iter_rows() for c in row if isinstance(c.value, str) and any(k in c.value for k in ("1+1", "SUM", "2+3", "+4"))]
        self.assertTrue(found)
        self.assertEqual(len(found), 4)
        for c in found:
            self.assertEqual(c.data_type, "s", c.value)
            self.assertTrue(c.quotePrefix, c.value)


if __name__ == "__main__":
    unittest.main()
