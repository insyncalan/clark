"""Row 1390 AP4/AP5 (Excel redesign): each data sheet's tab has its colour from the token table, and the History filter
covers the header row even when there are no changes. Fictional data, read back from the built workbook.

Run: python3 dev/run_tests.py test_excel_tabs_history_1390
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from openpyxl import load_workbook

from clark import excel
from test_excel import ON
from test_excel_format import action, raid, decision, use_case

# The light-theme tokens written in the brand tokens (src/clark/brand/tokens.css) and the page: tone text colours and the brand blue.
# Actions blue, Risks & Issues red, Decisions green, Milestones amber, Use cases the brand blue, Gantt grey (the ticket's tab-colour list).
TAB_COLOURS = {"Actions": "2456A8", "Risks & Issues": "B3392F", "Decisions": "2F6E57", "Milestones": "8A5A12",
               "Use cases": "5B47D8", "Gantt": "4F5865"}


def build(history):
    d = Path(tempfile.mkdtemp(prefix="clark-excel-"))
    rows = {"actions": [action(1)], "raid": [raid(1)], "decisions": [decision(1)], "use_cases": [use_case(1)], "milestones": [],
            "gantt_lines": [{"id": "G1", "name": "Plan the build", "type": "task"}]}
    excel.export(d / "a.xlsx", "DEMO", rows, d / "state.json", on=ON, gantt_tab="Gantt", history=history)
    return d, load_workbook(d / "a.xlsx")


class TabsAndHistory(unittest.TestCase):
    def test_every_sheet_tab_has_its_colour_from_the_token_table(self):
        d, wb = build({"footnote": "Fictional.", "closing": "End of history.", "empty": "Nothing yet.", "rows": []})
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        for name, want in TAB_COLOURS.items():
            self.assertIn(name, wb.sheetnames)
            colour = wb[name].sheet_properties.tabColor
            self.assertIsNotNone(colour, name)
            self.assertEqual(colour.rgb[-6:].upper(), want, name)
        self.assertEqual(len({wb[n].sheet_properties.tabColor.rgb for n in TAB_COLOURS}), len(TAB_COLOURS))      # six different colours

    def test_the_history_filter_covers_the_header_row_when_there_are_no_changes(self):
        d, wb = build({"footnote": "Fictional.", "closing": "", "empty": "Nothing yet.", "rows": []})
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        hist = wb["History"]
        self.assertEqual(hist.cell(row=2, column=1).value, "When")      # row 2 is the header
        self.assertEqual(hist.auto_filter.ref, "A2:G2")      # header only: no history rows, and the "Nothing yet." line (row 3) is outside
        self.assertEqual(hist["A3"].value, "Nothing yet.")


if __name__ == "__main__":
    unittest.main()
