"""Row 1390 part B: the workbook's words follow the page. One accepted heading list, the Milestones state columns gone, and an
old workbook (the old headings) still imports. The client copy is pinned in tests/test_client_export_by_source.py.

Run: python3 dev/run_tests.py test_excel_redesign_1390
"""
import unittest

from _paths import ROOT, SRC, TOOLS  # noqa: F401

from clark import excel
from clark import excel_import as xi

ACCEPTED = {
    "actions": ["ID", "Title", "Project", "Workstream", "Owner", "Priority", "Due", "Status", "Raised", "Closed", "Latest update",
                "Client visible", "Client Message", "Milestone", "Use case", "Labels", "Added from", "Last updated"],
    "decisions": ["ID", "Decision", "Project", "Status", "Priority", "Made by", "Needed by", "Decided on", "Reasoning",
                  "Options considered", "Revisit", "Replaces", "Latest update", "Client visible", "Client Message", "Use case",
                  "Labels", "Added from", "Last updated"],
}
OLD = {"Description", "Client-visible", "Source", "Updated", "Date", "Options", "Order", "% complete", "Shown state",
       "Shown as", "On dashboard", "State chosen", "Chosen by you", "State set by you"}


def labels(table):
    return [label for label, _ in next(cols for _, t, cols, _ in excel.SHEETS if t == table)]


class Headings(unittest.TestCase):
    def test_headings_are_the_accepted_ones(self):
        for table, want in ACCEPTED.items():
            self.assertEqual(labels(table), want, table)
        raid = labels("raid")
        for h in ("Title", "Client visible", "Added from", "Last updated"):
            self.assertIn(h, raid)
        ms = labels("milestones")
        for h in ("Sort order", "Progress %", "State", "Client visible", "Added from", "Last updated"):
            self.assertIn(h, ms)
        uc = labels("use_cases")
        for h in ("Reference", "Sort order", "On the dashboard", "Added from", "Last updated"):
            self.assertIn(h, uc)
        self.assertIn("On the dashboard", [label for label, _ in excel.GANTT_SHEET_COLUMNS])

    def test_no_sheet_still_carries_an_old_heading(self):
        for _, table, cols, _ in excel.SHEETS:
            old = OLD - ({"Description"} if table == "milestones" else set())      # a milestone's own Description stays
            self.assertFalse(old & {label for label, _ in cols}, table)
        self.assertFalse(OLD & {label for label, _ in excel.GANTT_SHEET_COLUMNS})

    def test_milestones_state_columns_are_gone(self):
        fields = {f for _, f in next(cols for _, t, cols, _ in excel.SHEETS if t == "milestones")}
        self.assertNotIn("state", fields)
        self.assertNotIn("state_set", fields)
        self.assertNotIn("state_set", excel.YES_NO)
        self.assertIn("shown_state", excel.DERIVED)               # the one State column is worked out, never read back
        cols = set(excel.COLUMN_OF["milestones"].values())
        for heading in ("State", "Shown state", "State chosen", "State set by you", "Chosen by you"):
            header, _named, _ignored = xi.header_map([heading], "milestones", cols, "Milestones")
            self.assertEqual(header, {}, heading)               # no state heading is read by the import


class OldWorkbook(unittest.TestCase):
    """An old workbook keeps importing: every renamed heading is still read as the same column."""
    OLD_HEADS = {"actions": {"Description": "description", "Client-visible": "client_visible", "Source": "source",
                             "Updated": "updated_at"},
                 "raid": {"Description": "description", "Client-visible": "client_visible", "Updated": "updated_at"},
                 "decisions": {"Date": "date", "Options": "options", "Client-visible": "client_visible", "Updated": "updated_at"},
                 "milestones": {"Order": "sort_order", "% complete": "percent_complete", "Client-visible": "client_visible",
                                "Updated": "updated_at"},
                 "use_cases": {"Shown as": "ref", "Order": "sort_order", "Client-visible": "client_visible", "Updated": "updated_at"}}

    def test_old_heading_workbook_still_imports(self):
        for table, heads in self.OLD_HEADS.items():
            cols = set(excel.COLUMN_OF[table].values())
            header, _named, ignored = xi.header_map(list(heads), table, cols, table)
            self.assertEqual(ignored, [], table)
            self.assertEqual(set(header), set(heads.values()), table)

    def test_the_old_gantt_heading_still_imports(self):
        self.assertEqual(xi.GANTT_HEADERS["on dashboard"], xi.GANTT_HEADERS["on the dashboard"])


if __name__ == "__main__":
    unittest.main()
