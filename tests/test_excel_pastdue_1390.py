"""Row 1390, past-due ruling (a): in the Excel export an open or delayed item past its date has its DATE in red text and its Status
cell keeps the status colour. No rule paints a Status cell red for being late. Read back with openpyxl, fictional rows.

Run: python3 dev/run_tests.py test_excel_pastdue_1390
"""
import re
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
                by_priority = {}
                for r in rules:
                    self.assertFalse(r.stopIfTrue)
                    fill = f.rgb(r.dxf.fill.bgColor) if r.dxf.fill else None
                    if r.type == "expression":
                        # Item 1390: an open Risk or Issue takes its Priority's colour (so the Urgent and High ones are red and maroon on
                        # purpose). Only these rules may: Risks & Issues, a formula of exactly AND(Status="Open", Priority="<word>"), no TODAY.
                        self.assertEqual(sheet, "Risks & Issues")
                        m = re.fullmatch(r"AND\(\$%s2=\"Open\",\$%s2=\"(\w+)\"\)" % (head["Status"], head["Priority"]), r.formula[0])
                        self.assertTrue(m, r.formula[0])
                        by_priority[m.group(1)] = fill
                    else:
                        self.assertEqual(r.type, "cellIs")
                        self.assertNotEqual(fill, red_fill)
                if sheet == "Risks & Issues":
                    self.assertEqual(by_priority, {w: colours.hexes(n)[0] for w, n in colours.OPEN_BY_PRIORITY.items()})
                else:
                    self.assertEqual(by_priority, {})

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
