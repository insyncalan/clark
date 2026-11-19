"""Row 1390 slice 6: the header row frozen at A2, the filter, and the hidden History sheet, read back with openpyxl. Fictional data.

Run: python3 dev/run_tests.py test_excel_header_1390
"""
import unittest

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from openpyxl import load_workbook

from clark import excel
from test_excel import ON
from test_excel_format import action, raid, decision, use_case
from test_gantt_excel_export import twelve

VIEW = {"rows": [{"when_text": f"2030-01-0{n}", "who": "ann", "how": "edit", "item": f"DEMO-A-00{n}", "field": "status",
                  "from": "Open", "to": "Closed"} for n in (1, 2, 3)],
        "footnote": "Footnote.", "empty": "", "closing": "Older rows are not shown."}


def book(history=VIEW, gantt=True):
    rows = {"actions": [action(1), action(2)], "raid": [raid(1)], "decisions": [decision(1)], "use_cases": [use_case(1)],
            "milestones": []}
    if gantt:
        rows["gantt_lines"] = twelve()
    return excel.workbook("DEMO", rows, on=ON, gantt_tab="Plan", history=history)


class TheHeaderRow(unittest.TestCase):
    def setUp(self):
        self.wb = book()

    def test_every_data_sheet_freezes_at_a2_and_nothing_else_does(self):
        for name in ("Milestones", "Actions", "Risks & Issues", "Decisions", "Use cases", "Plan"):
            self.assertEqual(self.wb[name].freeze_panes, "A2", name)
        self.assertEqual(self.wb["History"].freeze_panes, "A3")          # the header is row 2 there

    def test_the_filter_covers_the_header_and_the_rows_only(self):
        self.assertEqual(self.wb["Actions"].auto_filter.ref, "A1:R3")
        self.assertEqual(self.wb["Risks & Issues"].auto_filter.ref, "A1:V2")
        self.assertEqual(self.wb["Plan"].auto_filter.ref, "A1:%s13" % self.wb["Plan"].cell(1, self.wb["Plan"].max_column).column_letter)
        self.assertEqual(self.wb["History"].auto_filter.ref, "A2:G5")      # header + 3 rows, not the note (row 1) or the closing line (row 6)

    def test_the_filter_is_allowed_on_every_protected_sheet(self):
        for name in ("Actions", "Risks & Issues", "Decisions", "Milestones", "Use cases", "Plan", "History"):
            prot = self.wb[name].protection
            self.assertTrue(prot.sheet, name)
            self.assertFalse(prot.autoFilter, name)        # False means allowed in openpyxl

    def test_history_with_no_rows_filters_the_header_alone(self):
        wb = book({"rows": [], "footnote": "F", "empty": "Nothing yet.", "closing": ""})
        self.assertEqual(wb["History"].auto_filter.ref, "A2:G2")


class TheHistorySheet(unittest.TestCase):
    def test_it_is_hidden_and_still_has_its_content(self):
        ws = book()["History"]
        self.assertEqual(ws.sheet_state, "hidden")
        self.assertEqual([c.value for c in ws[2]], ["When", "Who", "How", "Item", "Field", "From", "To"])
        self.assertEqual(ws["D3"].value, "DEMO-A-001")
        self.assertEqual(ws["A6"].value, "Older rows are not shown.")

    def test_only_history_and_lists_are_hidden(self):
        wb = book()
        hidden = sorted(ws.title for ws in wb.worksheets if ws.sheet_state != "visible")
        self.assertEqual(hidden, ["History", "Lists"])
        for name in ("Actions", "Risks & Issues", "Decisions", "Milestones", "Use cases", "Plan"):
            self.assertEqual(wb[name].sheet_state, "visible", name)

    def test_a_workbook_without_history_has_none(self):
        self.assertNotIn("History", book(history=None).sheetnames)

    def test_a_formula_start_in_history_stays_text(self):
        view = dict(VIEW, rows=[dict(VIEW["rows"][0], to="=1+1", **{"from": "@SUM(1)"})])
        ws = book(view)["History"]
        self.assertEqual((ws["F3"].data_type, ws["G3"].data_type), ("s", "s"))
        self.assertTrue(ws["G3"].value.endswith("=1+1"))

    def test_it_survives_a_save_and_reload_hidden(self):
        import io
        buf = io.BytesIO()
        book().save(buf)
        buf.seek(0)
        self.assertEqual(load_workbook(buf)["History"].sheet_state, "hidden")


if __name__ == "__main__":
    unittest.main()
