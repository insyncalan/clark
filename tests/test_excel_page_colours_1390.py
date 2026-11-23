"""Row 1390 AP5 page colours. Reads the real built workbook with openpyxl, fictional rows only.

Run: python3 dev/run_tests.py test_excel_page_colours_1390
"""
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook

import test_excel as te
from test_excel import setUpModule, tearDownModule  # noqa: F401  (no brand logo on this computer)


class PageColours(unittest.TestCase):
    def setUp(self):
        self.d = te.Demo()
        self.addCleanup(self.d.close)
        self.d.demo.plant_builtin_sections()
        self.d.export()

    def test_priority_and_status_colours_follow_the_page(self):
        """DoD2/AP2: the sheets use the page's tone pairs (fill, text) named in the ticket, in the value tables and in the built workbook."""
        from clark import excel_colours as ec
        pairs = {"maroon": ("6B1D2A", "FFFFFF"), "red": ("F4DEDB", "B3392F"), "amber": ("FBF0D2", "8A5A12"),
                 "green": ("DFF1EA", "2F6E57"), "blue": ("E1EBFA", "2456A8"), "grey": ("E8EBEF", "4F5865")}
        for name, want in pairs.items():
            self.assertEqual(ec.hexes(name), want, name)
        self.assertEqual(ec.LATE_TEXT, "B3392F")      # an open or delayed row past due has its date in red
        self.assertEqual(ec.PRIORITY, {"Urgent": "maroon", "High": "red", "Medium": "amber", "Low": "green"})
        self.assertEqual(ec.ACTION_PRIORITY, {"Urgent": "maroon", "High": "red", "Medium": "grey", "Low": "grey"})
        self.assertEqual(ec.ACTION_STATUS, {"Open": "blue", "Delayed": "amber", "Closed": "grey", "Cancelled": "grey"})
        self.assertEqual(ec.RAID_STATUS, {"Closed": "grey", "Cancelled": "grey"})      # Open takes the row's Priority colour
        self.assertEqual(ec.OPEN_BY_PRIORITY, ec.PRIORITY)
        self.assertEqual(ec.DECISION_STATUS, {"Pending": "blue", "Made": "green", "Withdrawn": "grey"})
        for field in ("impact", "likelihood"):
            self.assertEqual(ec.BY_FIELD[("raid", field)], {"High": "red", "Medium": "amber", "Low": "green"})
        self.assertEqual(ec.LATE[("actions", "due_date")], ("status", {"Open", "Delayed"}))
        wb = load_workbook(self.d.path)      # and the workbook carries them as conditional-format fills and fonts
        want_fills = {pairs[n][0] for n in pairs}
        for name in ("Actions", "Risks & Issues", "Decisions"):
            rules = [r for rng in wb[name].conditional_formatting for r in rng.rules]
            self.assertTrue(rules, name)
            fills = {r.dxf.fill.bgColor.rgb[-6:] for r in rules if r.dxf and r.dxf.fill and r.dxf.fill.bgColor.rgb}
            self.assertTrue(fills, name)
            self.assertLessEqual(fills, want_fills, name)
            fonts = {r.dxf.font.color.rgb[-6:] for r in rules if r.dxf and r.dxf.font and r.dxf.font.color and r.dxf.font.color.rgb}
            self.assertTrue(fonts, name)
            self.assertLessEqual(fonts, {pairs[n][1] for n in pairs}, name)
            if name != "Decisions":      # the sheets with a Priority column carry the Urgent rule: maroon fill, white text
                urgent = [r for r in rules if r.dxf and r.dxf.fill and r.dxf.fill.bgColor.rgb
                          and r.dxf.fill.bgColor.rgb[-6:] == "6B1D2A"]
                self.assertTrue(urgent, name)
                self.assertTrue(all(r.dxf.font.color.rgb[-6:] == "FFFFFF" for r in urgent), name)


if __name__ == "__main__":
    unittest.main()
