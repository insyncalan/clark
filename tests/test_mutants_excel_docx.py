"""Killer tests for mutants that survived an audit of excel_palette, docx_build and excel (rows 999 and 1060). Tests only.

Run: python3 dev/run_tests.py test_mutants_excel_docx
Each test names the one change to the source that it catches. Fictional data only.
"""
import unittest
from unittest import mock

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)

from clark import docx_build, excel, excel_colours, excel_palette as ep

TODAY = "2026-10-28"
TOK = excel_colours.TOKENS


def ctx():
    return docx_build._Ctx(excel_colours.TOKENS, TODAY)


def brand(**names):
    return ":root {\n" + "\n".join(f"--{k}: #{v};" for k, v in names.items()) + "\n}"


class PalettePairs(unittest.TestCase):
    def test_the_late_date_pair_is_white_on_the_red_text(self):
        """EXTRA_PAIRS: ("white", "tone-red-text", "a late date") must stay red, not amber."""
        self.assertIn(("white", "tone-red-text", "a late date"), ep.EXTRA_PAIRS)
        self.assertNotIn(("white", "tone-amber-text", "a late date"), ep.EXTRA_PAIRS)

    def test_a_pale_red_text_is_given_up_because_a_late_date_is_drawn_on_white(self):
        """A red text that reads well on its own dark tint but not on white: only the late-date pair can catch it."""
        warnings = []
        p = ep.palette(css=brand(**{"tone-red-tint": "111111", "tone-red-text": "FF8080"}), warnings=warnings)
        self.assertLess(ep.contrast_ratio("FF8080", "FFFFFF"), ep.MIN_CONTRAST)
        self.assertEqual(p.tokens["tone-red-text"], TOK["tone-red-text"])
        self.assertTrue(any("a late date" in w for w in warnings), warnings)

    def test_the_floor_is_four_and_a_half_to_one(self):
        """MIN_CONTRAST: a heading blue at about 4.06:1 on white is under the floor and gives up its token."""
        self.assertEqual(ep.MIN_CONTRAST, 4.5)
        self.assertTrue(3.0 < ep.contrast_ratio("3B82C4", "FFFFFF") < 4.5)
        warnings = []
        p = ep.palette(css=brand(**{"brand-blue": "3B82C4"}), warnings=warnings)
        self.assertEqual(p.tokens["brand-blue"], TOK["brand-blue"])
        self.assertTrue(any("under 4.5:1" in w for w in warnings), warnings)

    def test_a_blue_just_over_the_floor_is_kept(self):
        self.assertGreaterEqual(ep.contrast_ratio("2A6FB0", "FFFFFF"), 4.5)
        p = ep.palette(css=brand(**{"brand-blue": "2A6FB0"}))
        self.assertEqual(p.tokens["brand-blue"], "2A6FB0")


class WordStatusCells(unittest.TestCase):
    def test_an_issue_reads_red_amber_green_with_a_fill(self):
        """_status_cell: the kind list keeps "issue"; a dropped one would show the raw status with no fill."""
        for priority, word in (("High", "Red"), ("Medium", "Amber"), ("Low", "Green")):
            with self.subTest(priority=priority):
                body, fill = docx_build._status_cell({"status": "Open", "priority": priority}, "issue", ctx())
                self.assertIn(word, body)
                self.assertNotIn(">Open<", body)
                self.assertIsNotNone(fill)

    def test_an_issue_matches_a_risk_of_the_same_rating(self):
        row = {"status": "Open", "priority": "High"}
        self.assertEqual(docx_build._status_cell(row, "issue", ctx()), docx_build._status_cell(row, "risk", ctx()))

    def test_a_made_pill_is_blue_like_closed(self):
        """The pill word "Made" draws in the blue cell (the pill is faked: a decision never reaches this function by kind)."""
        c = ctx()
        want = docx_build.word_cell("Made", c, colour="blue")
        self.assertIsNotNone(want[1])
        for cls in ("g", "n", "b"):
            with self.subTest(cls=cls), mock.patch.object(docx_build.glance, "client_pill", return_value={"text": "Made", "class": cls}):
                self.assertEqual(docx_build._status_cell({"status": "Made"}, "action", c), want)

    def test_a_closed_pill_is_blue(self):
        body, fill = docx_build._status_cell({"status": "Closed"}, "action", ctx())
        self.assertEqual((body, fill), docx_build.word_cell("Closed", ctx(), colour="blue"))

    def test_a_late_word_is_the_red_text_not_the_amber(self):
        """word_cell(late=True): the red text hex is in the cell, the amber one is not, and there is no fill."""
        body, fill = docx_build.word_cell("1 Jan 2026 (overdue)", ctx(), late=True)
        self.assertIsNone(fill)
        self.assertIn(TOK["tone-red-text"], body)
        self.assertNotIn(TOK["tone-amber-text"], body)

    def test_a_word_that_is_not_late_has_no_red_text(self):
        body, _ = docx_build.word_cell("1 Jan 2030", ctx())
        self.assertNotIn(TOK["tone-red-text"], body)


class RichWords(unittest.TestCase):
    def test_the_rich_words_are_exactly_these_four(self):
        """RICH_WORDS: the four rich fields, spelt as the tables spell them."""
        self.assertEqual(set(excel.RICH_WORDS), {("actions", "latest_update"), ("milestones", "description"),
                                                 ("milestones", "internal_note"), ("use_cases", "standing")})

    def test_every_rich_word_is_a_real_column_of_its_sheet(self):
        cols = {t: {f for _, f in c} for _, t, c, _ in excel.SHEETS}
        for table, field in excel.RICH_WORDS:
            with self.subTest(table=table, field=field):
                self.assertIn(field, cols[table])

    def test_a_use_case_standing_is_words_in_its_cell(self):
        rows = {"use_cases": [{"id": "u1", "title": "uc", "headline": "h", "standing": "<p>fabrikam <strong>pilot</strong></p>", "status": "Planned"}]}
        ws = excel.workbook("Demo", rows, on="2030-06-01")["Use cases"]
        col = [c.value for c in ws[1]].index("Where it stands") + 1
        self.assertEqual(ws.cell(row=2, column=col).value, "fabrikam pilot")


if __name__ == "__main__":
    unittest.main()
