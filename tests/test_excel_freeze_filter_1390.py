"""Row 1390 AP4 (Excel redesign): the header row is frozen and filtered on every data sheet. Fictional data.

Run: python3 dev/run_tests.py test_excel_freeze_filter_1390
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

# History keeps A3 (header at row 2, rows 1-2 stay): pinned by test_excel.py test_headers_note_and_frozen_header.

class HeaderFrozen(unittest.TestCase):
    def test_header_frozen_and_filter_on_every_data_sheet(self):
        d = Path(tempfile.mkdtemp(prefix="clark-excel-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        rows = {"actions": [action(1)], "raid": [raid(1)], "decisions": [decision(1)], "use_cases": [use_case(1)], "milestones": []}
        excel.export(d / "a.xlsx", "DEMO", rows, d / "state.json", on=ON)
        wb = load_workbook(d / "a.xlsx")
        data = ["Milestones", "Actions", "Risks & Issues", "Decisions", "Use cases"]
        for name in data:
            ws = wb[name]
            self.assertEqual(ws.freeze_panes, "A2", name)
            self.assertTrue(ws.auto_filter.ref and ws.auto_filter.ref.startswith("A1:"), name)
            self.assertFalse(ws.protection.autoFilter, name)      # False = the filter is allowed on the protected sheet


if __name__ == "__main__":
    unittest.main()
