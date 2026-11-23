"""Row 1390 slice 8: the Report headline section is drawn on the Report sheet (excel_blocks, excel_cover.lines), words only.
Fictional data only.

Run: python3 dev/run_tests.py test_excel_report_headline_1390s8
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


def setUpModule():
    global _OLD
    _OLD, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


def sec(content=None, title="", hidden=0, kind="reportheadline"):
    return {"id": "r", "type": kind, "title": title, "body": "", "hidden": hidden, "content": content}


FULL = {"health": "at_risk", "headline": "Go live moves one week", "sentence": "The vendor test slipped to Friday."}
DOT = "·"


def draw(*sections):
    return cover.lines({"name": "Harbour Lights upgrade"}, list(sections), [], "01-06-2030 20:30", None)


def words(lines):
    return [(x["kind"], x["text"]) for x in lines]


class TheBlock(unittest.TestCase):
    def test_heading_then_health_and_headline_then_the_sentence(self):
        self.assertEqual(words(excel_blocks.block(sec(FULL))),
                         [("heading", "Report headline"), ("text", f"At risk {DOT} Go live moves one week"),
                          ("text", "The vendor test slipped to Friday.")])

    def test_each_health_has_its_words_and_the_sections_own_title_wins(self):
        for key, word in (("on_track", "On track"), ("at_risk", "At risk"), ("off_track", "Off track")):
            got = excel_blocks.block(sec({"health": key, "headline": "H", "sentence": ""}, title="Where we are"))
            self.assertEqual(words(got), [("heading", "Where we are"), ("text", f"{word} {DOT} H")])

    def test_a_part_with_nothing_is_left_out(self):
        self.assertEqual(words(excel_blocks.block(sec({"health": "", "headline": "H", "sentence": ""})))[1:], [("text", "H")])
        self.assertEqual(words(excel_blocks.block(sec({"health": "on_track", "headline": " ", "sentence": "S"})))[1:],
                         [("text", "On track"), ("text", "S")])

    def test_nothing_to_say_is_no_lines_not_even_the_heading(self):
        for c in (None, {}, {"health": "", "headline": "", "sentence": ""}, 5, "x", {"health": 7, "headline": 3, "sentence": []}):
            self.assertEqual(excel_blocks.block(sec(c)), [], c)

    def test_an_unknown_health_is_not_a_word(self):
        self.assertEqual(words(excel_blocks.block(sec({"health": "nonsense", "headline": "H"})))[1:], [("text", "H")])

    def test_another_type_is_not_drawn_here(self):
        self.assertEqual(excel_blocks.block(sec(FULL, kind="callout")), [])


class OnTheReport(unittest.TestCase):
    def test_it_sits_in_the_dashboard_order_between_its_neighbours(self):
        got = words(draw({"type": "text", "title": "Before", "body": "<p>One</p>", "hidden": 0}, sec(FULL),
                         {"type": "text", "title": "After", "body": "<p>Two</p>", "hidden": 0}))
        self.assertEqual([t for k, t in got if k == "heading"], ["Before", "Report headline", "After"])
        self.assertIn(("text", f"At risk {DOT} Go live moves one week"), got)

    def test_a_hidden_one_is_not_drawn(self):
        self.assertNotIn("Report headline", [t for k, t in words(draw(sec(FULL, hidden=1))) if k == "heading"])

    def test_a_long_headline_is_cut_under_the_cell_limit(self):
        got = draw(sec({"headline": "x" * 40000}))
        self.assertTrue(all(len(x["text"]) <= cover.LIMIT for x in got))
        self.assertTrue(any(x["text"].endswith(cover.MORE) for x in got))


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
                    "('ABC','h','reportheadline','',?,0,?,1)", (json.dumps(body), hidden))
        con.commit()
        con.close()
        path = self.dir / "w.xlsx"
        excel.export_project(self.demo.store, "ABC", path, self.dir / "state.json", on="2030-06-01")
        ws = load_workbook(path)["Report"]
        return ws, [c.value for row in ws.iter_rows() for c in row if c.value is not None]

    def test_the_words_are_on_the_sheet(self):
        _, cells = self.export(dict(FULL, v=1))
        self.assertIn(f"At risk {DOT} Go live moves one week", cells)
        self.assertIn("The vendor test slipped to Friday.", cells)

    def test_a_hidden_section_is_not_on_the_sheet(self):
        _, cells = self.export(dict(FULL, v=1, headline="CANARY-HIDDEN"), hidden=1)
        self.assertNotIn("CANARY-HIDDEN", "\n".join(map(str, cells)))

    def test_words_that_look_like_a_formula_stay_text(self):
        ws, cells = self.export({"v": 1, "headline": "=1+1", "sentence": "@SUM(1)"})
        found = [c for row in ws.iter_rows() for c in row if isinstance(c.value, str) and ("=1+1" in c.value or "@SUM" in c.value)]
        self.assertEqual(len(found), 2)
        for c in found:
            self.assertEqual((c.data_type, c.quotePrefix), ("s", True), c.value)      # a string cell, never a formula


class HelpSentence(unittest.TestCase):
    """The B-2 Help sentence about the hidden History sheet is pinned word for word (read 23-11: no test held it)."""

    SENTENCE = ("**History** lists the changes made to the items; it is hidden: right-click any sheet tab and choose Unhide.")

    def test_the_report_and_history_sentence_is_in_the_help(self):
        raw = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8")
        text = json.dumps(json.loads(raw), ensure_ascii=False)
        self.assertIn(json.dumps(self.SENTENCE, ensure_ascii=False)[1:-1], text)


if __name__ == "__main__":
    unittest.main()
