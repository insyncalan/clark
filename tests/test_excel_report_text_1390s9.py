"""Row 1390 slice 9: the Text sections on the Report sheet (excel_text_section, excel_cover.lines). Fictional data only.

A Text section is its heading and its words as plain paragraphs; no words, no lines (heading included); no title, no empty heading;
a hidden section, a tag, a script and a formula start never reach the sheet as anything but text. The produced .xlsx is opened with
openpyxl.

Run: python3 dev/run_tests.py test_excel_report_text_1390s9
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import DemoStore
from openpyxl import Workbook, load_workbook

from clark import excel
from clark import excel_cover as cover
from clark import excel_text_section as section
from clark import page

_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")
STAMP = "01-06-2030 20:30 (UTC+04:00)"
PROJECT = {"code": "D", "name": "Harbour Lights", "current_state": ""}


def setUpModule():
    global _OLD_BRANDING
    _OLD_BRANDING, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD_BRANDING
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


def text(title, body, **more):
    return dict({"type": "text", "title": title, "body": body}, **more)


def lines(*sections):
    return [(x["kind"], x["text"]) for x in cover.lines(PROJECT, list(sections), [], STAMP)[2:-7]]


class TheLines(unittest.TestCase):
    def test_heading_then_words(self):
        self.assertEqual(lines(text("Summary", "<p>On course.</p>")), [("heading", "Summary"), ("text", "On course.")])

    def test_paragraphs_and_list_items_are_lines_and_tags_are_gone(self):
        got = lines(text("Summary", "<p>One.</p><p>Two <b>bold</b></p><ul><li>Cabling</li><li>Testing</li></ul>"))
        self.assertEqual(got, [("heading", "Summary"), ("text", "One.\nTwo bold\nCabling\nTesting")])

    def test_sections_keep_their_order(self):
        got = lines(text("B", "<p>b</p>"), text("A", "<p>a</p>"), text("C", "<p>c</p>"))
        self.assertEqual([t for k, t in got if k == "heading"], ["B", "A", "C"])

    def test_no_words_no_lines_heading_included(self):
        for body in ("", "<p> </p>", "<p></p><p>\u00a0</p>", None, "<script>alert(1)</script>"):
            with self.subTest(body=body):
                self.assertEqual(lines(text("Summary", body)), [])

    def test_no_title_is_the_words_alone_not_an_empty_heading(self):
        for title in ("", "   ", None):
            with self.subTest(title=title):
                self.assertEqual(lines(text(title, "<p>Words.</p>")), [("text", "Words.")])

    def test_the_title_is_kept_as_typed_and_cut_to_200(self):
        self.assertEqual(lines(text("  Summary  ", "<p>x</p>"))[0], ("heading", "  Summary  "))
        self.assertEqual(lines(text("\tWords", "<p>x</p>"))[0], ("heading", "\tWords"))
        self.assertEqual(len(lines(text("t" * 900, "<p>x</p>"))[0][1]), section.TITLE_LIMIT)

    def test_a_hidden_text_section_is_not_there(self):
        got = lines(text("Secret", "<p>CANARY-HIDDEN-SECTION</p>", hidden=1), text("Shown", "<p>Seen.</p>"))
        self.assertEqual(got, [("heading", "Shown"), ("text", "Seen.")])

    def test_this_week_and_next_week_are_still_one_pair(self):
        got = cover.lines(PROJECT, [text("This week", "<p>Lights tested.</p>"), text("Next week", "<p>Hand over.</p>")], [], STAMP)
        pair = [x for x in got if x["kind"] == "pair"]
        self.assertEqual([(p["left"]["text"], p["right"]["text"]) for p in pair], [("Lights tested.", "Hand over.")])
        self.assertEqual([x for x in got if x["kind"] == "heading"], [])

    def test_this_week_alone_is_an_ordinary_section(self):
        self.assertEqual(lines(text("This week", "<p>Done.</p>"), text("Next week", "<p> </p>")), [("heading", "This week"), ("text", "Done.")])

    def test_a_long_body_is_cut_under_excels_limit_with_the_mark(self):
        got = lines(text("Summary", "<p>" + "word " * 20000 + "</p>"))
        self.assertLess(len(got[1][1]), 32767)
        self.assertTrue(got[1][1].endswith(cover.MORE))

    def test_a_body_the_cleaner_refuses_is_cut_not_fatal(self):
        got = lines(text("Summary", "<p>" + "a" * 400000 + "</p>"))
        for _, words in got:
            self.assertLess(len(words), 32767)

    def test_a_section_that_is_not_a_dict_or_has_a_wrong_shape_is_nothing(self):
        for bad in (None, 5, "x", [], {"title": 7, "body": 7}, {"title": ["a"], "body": {"a": 1}}):
            with self.subTest(bad=bad):
                self.assertEqual(section.text_lines(bad, cover.plain), [])

    def test_a_title_that_is_not_text_is_no_heading_and_the_words_stay(self):
        for title in (7, ["a"], {"a": 1}, True):
            with self.subTest(title=title):
                self.assertEqual(section.text_lines({"title": title, "body": "<p>x</p>"}, cover.plain), [{"kind": "text", "text": "x"}])

    def test_the_module_takes_the_words_as_the_reader_gives_them(self):
        """Whatever reads the body, white space alone is no words, and words are passed through as given."""
        self.assertEqual(section.text_lines({"title": "T", "body": "x"}, lambda _b: "  \n "), [])
        self.assertEqual(section.text_lines({"title": "T", "body": "x"}, lambda _b: " x "),
                         [{"kind": "heading", "text": "T"}, {"kind": "text", "text": " x "}])

    def test_words_that_start_like_a_formula_are_kept_as_typed(self):
        self.assertEqual(lines(text("=Title", "<p>=1+1</p>")), [("heading", "=Title"), ("text", "=1+1")])


class FormulaStart(unittest.TestCase):
    def test_every_formula_start_is_a_string_cell_in_the_sheet(self):
        for lead in ("=", "+", "-", "@", "\t", "\r"):
            with self.subTest(lead=repr(lead)):
                secs = [text(lead + "Words", "<p>" + lead + "cmd|' /C calc'!A0</p>"), text("", "<p>" + lead + "SUM(1)</p>")]
                ws = excel.write_cover(Workbook(), cover.lines({"name": "N"}, secs, [], STAMP))
                for row in ws.iter_rows():
                    for c in row:
                        self.assertNotEqual(c.data_type, "f", c.coordinate)
                        if isinstance(c.value, str) and c.value[:1] in "=+-@":
                            self.assertEqual((c.data_type, c.quotePrefix), ("s", True), c.coordinate)
                values = [str(c.value) for row in ws.iter_rows() for c in row if c.value]
                self.assertTrue(any("SUM(1)" in v for v in values))
                self.assertTrue(any("calc" in v for v in values))


class InTheWorkbook(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-report-text-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = self.dir / "ABC work items.xlsx"
        con = sqlite3.connect(self.demo.store.path)
        con.execute("DELETE FROM report_sections WHERE project = 'ABC'")
        con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES "
                    "('ABC','a','text','Summary','<p>On course.</p><p>=HYPERLINK(\"http://x\")</p>',0,0,1), "
                    "('ABC','b','text','Secret plans','<p>CANARY-HIDDEN-SECTION</p>',0,1,2), "
                    "('ABC','c','text','Empty words','<p> </p>',0,0,3), "
                    "('ABC','d','text','Last words','<p>Done.</p><script>alert(1)</script>',0,0,4)")
        con.commit()
        con.close()
        excel.export_project(self.demo.store, "ABC", self.path, self.dir / "state.json", on="2030-06-01", exported_by="Sam Example",
                             owner="Kim Example", owner_email="kim.example@example.com")
        wb = load_workbook(self.path)
        self.ws = wb[wb.sheetnames[0]]
        self.values = [c.value for row in self.ws.iter_rows() for c in row if c.value is not None]

    def test_the_text_sections_are_on_the_first_sheet_in_order_with_their_words(self):
        want = ["\u25a0  Summary", "On course.\n=HYPERLINK(\"http://x\")", "\u25a0  Last words", "Done."]
        at = [self.values.index(w) for w in want]
        self.assertEqual(at, sorted(at))

    def test_hidden_empty_and_script_text_is_not_in_the_sheet(self):
        everything = "\n".join(map(str, self.values))
        for gone in ("CANARY-HIDDEN-SECTION", "Secret plans", "Empty words", "alert", "<"):
            self.assertNotIn(gone, everything)

    def test_a_formula_start_is_text_in_the_file(self):
        for row in self.ws.iter_rows():
            for c in row:
                self.assertNotEqual(c.data_type, "f", c.coordinate)


if __name__ == "__main__":
    unittest.main()
