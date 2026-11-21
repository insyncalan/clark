"""Row 1390, past-due ruling (a): in the Excel export an open or delayed item past its date has its DATE in red text and its Status
cell keeps the status colour. No rule paints a Status cell red for being late. Read back with openpyxl, fictional rows.

Run: python3 dev/run_tests.py test_excel_pastdue_1390
"""
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook

from clark import excel
from clark import excel_colours as colours
import test_excel_format as f

RED_TEXT = "B3392F"
OPEN_STATES = {"Actions": ("Delayed", "Open"), "Risks & Issues": ("Open",), "Decisions": ("Pending",)}
DATE_OF = {"Actions": "Due", "Risks & Issues": "Due", "Decisions": "Needed by"}


class PastDue(unittest.TestCase):
    def setUp(self):
        case = f.Formatting("test_no_formula_in_any_cell")      # only its build helpers are used
        case.setUp()
        self.addCleanup(case.tearDown)
        self.wb = load_workbook(case.build(case.everything()))

    def test_the_late_status_rule_is_gone(self):
        self.assertFalse(hasattr(excel, "add_late_status_rule"))

    def test_no_status_cell_rule_is_a_formula_or_red(self):
        red_fill = colours.hexes("red")[0]
        for sheet in OPEN_STATES:
            ws = self.wb[sheet]
            head = {c.value: c.column_letter for c in ws[1]}
            rules = [r for col, r in f.rules_of(ws) if col == head["Status"]]
            with self.subTest(sheet=sheet):
                self.assertTrue(rules)
                for r in rules:
                    self.assertEqual(r.type, "cellIs")
                    self.assertFalse(r.stopIfTrue)
                    self.assertNotEqual(f.rgb(r.dxf.fill.bgColor) if r.dxf.fill else None, red_fill)

    def test_an_actions_status_words_keep_their_status_colour(self):
        ws = self.wb["Actions"]
        status = {c.value: c.column_letter for c in ws[1]}["Status"]
        for word, name in colours.ACTION_STATUS.items():
            with self.subTest(word=word):
                self.assertEqual(f.look_of(ws, status, word), colours.hexes(name))

    def test_only_the_date_turns_red_and_only_for_open_or_delayed(self):
        for sheet, states in OPEN_STATES.items():
            ws = self.wb[sheet]
            head = {c.value: c.column_letter for c in ws[1]}
            d, st = head[DATE_OF[sheet]], head["Status"]
            late = [r for col, r in f.rules_of(ws) if col == d and r.type == "expression"]
            with self.subTest(sheet=sheet):
                self.assertEqual(len(late), 1)
                opens = ",".join(f'${st}2="{s}"' for s in states)
                self.assertEqual(late[0].formula, [f"AND(ISNUMBER(${d}2),${d}2<TODAY(),OR({opens}))"])
                self.assertEqual(f.rgb(late[0].dxf.font.color), RED_TEXT)
                self.assertIsNone(late[0].dxf.fill)
                for closed in ("Closed", "Cancelled", "Made", "Withdrawn"):
                    self.assertNotIn(f'"{closed}"', late[0].formula[0])


if __name__ == "__main__":
    unittest.main()
