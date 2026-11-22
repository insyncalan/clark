"""Row 1390 AP4 (Excel redesign): the header row is frozen and filtered on every data sheet. Fictional data.

Run: python3 dev/run_tests.py test_excel_freeze_filter_1390
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from clark import excel, excel_client, publish
from test_excel import ON
from test_gantt_excel_export import plant as gantt_plant
from test_excel_format import action, raid, decision, use_case

# History keeps A3 (header at row 2, rows 1-2 stay): pinned by test_excel.py test_headers_note_and_frozen_header.
# The client copy has a title block (rows 1-3) above its header (row 4): its panes freeze at A5 (Gantt C5, pinned by test_excel_client_mutwave), the filter starts at A4.
HISTORY = {"footnote": "Fictional.", "closing": "End of history.", "empty": "Nothing yet.",
           "rows": [{"when_text": "2030-01-01", "who": "Demo", "how": "Edit", "item": "A1", "field": "owner", "from": "a", "to": "b"}]}

class HeaderFrozen(unittest.TestCase):
    def test_header_frozen_and_filter_on_every_data_sheet(self):
        d = Path(tempfile.mkdtemp(prefix="clark-excel-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        rows = {"actions": [action(1)], "raid": [raid(1)], "decisions": [decision(1)], "use_cases": [use_case(1)], "milestones": [],
                "gantt_lines": [{"id": "G1", "name": "Plan the build", "type": "task"}]}
        excel.export(d / "a.xlsx", "DEMO", rows, d / "state.json", on=ON, gantt_tab="Gantt", history=HISTORY)
        wb = load_workbook(d / "a.xlsx")
        data = ["Milestones", "Actions", "Risks & Issues", "Decisions", "Use cases", "Gantt"]
        for name in data:
            ws = wb[name]
            self.assertEqual(ws.freeze_panes, "A2", name)
            self.assertTrue(ws.auto_filter.ref and ws.auto_filter.ref.startswith("A1:"), name)
            self.assertFalse(ws.protection.autoFilter, name)      # False = the filter is allowed on the protected sheet
        for name in ("Actions", "Gantt"):                         # the filter covers the one data row (the spare rows below are outside it)
            self.assertTrue(wb[name].auto_filter.ref.endswith("2"), (name, wb[name].auto_filter.ref))
        hist = wb["History"]                                      # header at row 2, so panes at A3; the filter is the header and the history rows
        self.assertEqual(hist.freeze_panes, "A3")
        self.assertEqual(hist.auto_filter.ref, "A2:G3")
        self.assertFalse(hist.protection.autoFilter)
        pub = publish.select(gantt_plant())                       # the client copy (excel_client.py)
        client = load_workbook(io.BytesIO(excel_client.workbook_bytes(pub)))
        self.assertIn("Plan", client.sheetnames)                  # the client Gantt sheet is covered
        for ws in client.worksheets:
            self.assertIn(ws.freeze_panes, ("A5", "C5"), ws.title)
            self.assertTrue(ws.auto_filter.ref and ws.auto_filter.ref.startswith("A4:"), (ws.title, ws.auto_filter.ref))
            self.assertEqual(ws.auto_filter.ref.split(":")[1], f"{get_column_letter(ws.max_column)}{ws.max_row}", ws.title)
            self.assertFalse(ws.protection.autoFilter, ws.title)


if __name__ == "__main__":
    unittest.main()
