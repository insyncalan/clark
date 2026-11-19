"""Row 1390 slice 2: the export's colours and tab colours follow the page. The produced workbook is opened with openpyxl and the stated
cells, rules and tabs are asserted, and the other cells and sheets are asserted to have none.
Run: python3 dev/run_tests.py test_excel_colours_1390s2"""
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook

from clark import excel
from test_excel import ON
from test_excel_format import action, raid, decision, use_case, rules_of, look_of, rgb
from test_gantt_excel_export import twelve

WHITE, MAROON = "FFFFFF", "6B1D2A"
RED, AMBER, GREEN, BLUE, GREY = (("F4DEDB", "B3392F"), ("FBF0D2", "8A5A12"), ("DFF1EA", "2F6E57"), ("E1EBFA", "2456A8"),
                                 ("E8EBEF", "4F5865"))
URGENT = (MAROON, WHITE)

TABS = {"Actions": "2456A8", "Risks & Issues": "B3392F", "Decisions": "2F6E57", "Milestones": "8A5A12", "Use cases": "5B47D8"}


def col_of(ws, label):
    from openpyxl.utils import get_column_letter
    return get_column_letter([c.value for c in ws[1]].index(label) + 1)


class Colours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = {"actions": [action(1)], "raid": [raid(1)], "decisions": [decision(1)], "use_cases": [use_case(1)], "milestones": [],
                "gantt_lines": twelve()}
        cls.wb = excel.workbook("DEMO", rows, on=ON, gantt_tab="Plan")

    def test_actions_priority_and_status(self):
        ws, p, s = self.wb["Actions"], col_of(self.wb["Actions"], "Priority"), col_of(self.wb["Actions"], "Status")
        self.assertEqual([look_of(ws, p, v) for v in ("Urgent", "High", "Medium", "Low")], [URGENT, RED, GREY, GREY])
        self.assertEqual([look_of(ws, s, v) for v in ("Open", "Delayed", "Closed", "Cancelled")], [BLUE, AMBER, GREY, GREY])

    def test_raid_priority_status_impact_likelihood(self):
        ws = self.wb["Risks & Issues"]
        p, s, i, lk = (col_of(ws, x) for x in ("Priority", "Status", "Impact", "Likelihood"))
        self.assertEqual([look_of(ws, p, v) for v in ("Urgent", "High", "Medium", "Low")], [URGENT, RED, AMBER, GREEN])
        self.assertEqual([look_of(ws, s, v) for v in ("Open", "Closed", "Cancelled")], [None, GREY, GREY])
        for c in (i, lk):
            self.assertEqual([look_of(ws, c, v) for v in ("High", "Medium", "Low")], [RED, AMBER, GREEN])

    def test_an_open_risk_takes_its_priority_colour_by_a_rule_reading_the_priority_cell(self):
        ws = self.wb["Risks & Issues"]
        s, p = col_of(ws, "Status"), col_of(ws, "Priority")
        got = {}
        for letter, r in rules_of(ws):
            if letter == s and r.type == "expression" and "Open" in r.formula[0] and p in r.formula[0] and "TODAY" not in r.formula[0]:
                word = r.formula[0].split(f"${p}2=\"")[1].rstrip('")')
                got[word] = (rgb(r.dxf.fill.bgColor), rgb(r.dxf.font.color))
        self.assertEqual(got, {"Urgent": URGENT, "High": RED, "Medium": AMBER, "Low": GREEN})

    def test_decisions_status(self):
        ws = self.wb["Decisions"]
        s = col_of(ws, "Status")
        self.assertEqual([look_of(ws, s, v) for v in ("Pending", "Made", "Withdrawn")], [BLUE, GREEN, GREY])

    def test_unchanged_value_tables(self):
        ws = self.wb["Use cases"]
        self.assertEqual([look_of(ws, col_of(ws, "Status"), v) for v in ("On track", "Flag", "High risk", "Done")], [GREEN, AMBER, RED, GREY])

    def test_late_date_text_is_red_on_the_due_dates_only(self):
        for name, label in (("Actions", "Due"), ("Risks & Issues", "Due"), ("Decisions", "Needed by")):
            ws = self.wb[name]
            c = col_of(ws, label)
            hits = [r for letter, r in rules_of(ws) if letter == c and "TODAY" in r.formula[0] and r.dxf.fill is None
                    and rgb(r.dxf.font.color) == "B3392F"]
            self.assertEqual(len(hits), 1, name)

    def test_no_other_column_gets_a_colour_rule(self):
        want = {"Actions": {"Priority", "Status", "Due"}, "Risks & Issues": {"Priority", "Status", "Impact", "Likelihood", "Due"},
                "Decisions": {"Status", "Needed by"}}
        for name, labels in want.items():
            ws = self.wb[name]
            cols = {col_of(ws, x) for x in labels}
            self.assertEqual({letter for letter, _ in rules_of(ws)} - cols, set(), name)

    def test_tab_colours_by_sheet(self):
        for name, hexes in TABS.items():
            self.assertEqual(rgb(self.wb[name].sheet_properties.tabColor), hexes, name)
        self.assertEqual(rgb(self.wb["Plan"].sheet_properties.tabColor), "4F5865")

    def test_other_sheets_have_no_tab_colour_and_gantt_has_no_rules(self):
        for ws in self.wb.worksheets:
            if ws.title not in TABS and ws.title != "Plan":
                self.assertIsNone(ws.sheet_properties.tabColor, ws.title)
        self.assertEqual(rules_of(self.wb["Plan"]), [])

    def test_saved_and_reopened_keeps_the_tab_colours(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "x.xlsx"
            self.wb.save(p)
            back = load_workbook(p)
        for name, hexes in TABS.items():
            self.assertEqual(rgb(back[name].sheet_properties.tabColor), hexes, name)


if __name__ == "__main__":
    unittest.main()
