"""Item 1390, slice 1: a workbook exported BEFORE the headings followed the page still imports, cell for cell.

The old file is made here, by writing the older headings over a fresh export: Description, Client-visible, Source, Updated,
Date, Options, Order, % complete, Client wording (the heading before row 1466), Shown state, and the two Milestones columns State and State set by you, which the export no
longer writes. The import reads the older names as the new ones, and no longer sets a milestone's state from a cell.

Run: python3 dev/run_tests.py test_excel_old_headings_1390
"""
import unittest
from datetime import date

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from openpyxl import load_workbook

from clark import excel
from clark import excel_import as xi
from clark.store import Invalid
from test_excel_roundtrip import RoundTrip, setUpModule, tearDownModule  # noqa: F401  (the hooks keep a brand logo out of every test)

OLD = {
    "Actions": {"Title": "Description", "Client visible": "Client-visible", "Added from": "Source", "Last updated": "Updated"},
    "Risks & Issues": {"Title": "Description", "Client visible": "Client-visible", "Added from": "Source", "Last updated": "Updated"},
    "Decisions": {"Decided on": "Date", "Options considered": "Options", "Client visible": "Client-visible", "Added from": "Source",
                  "Last updated": "Updated"},
    "Milestones": {"Sort order": "Order", "Progress %": "% complete", "State": "Shown state", "Client visible": "Client-visible",
                   "Added from": "Source", "Last updated": "Updated"},
    "Use cases": {"Sort order": "Order", "On the dashboard": "Client-visible", "Added from": "Source", "Last updated": "Updated"},
}


for _names in OLD.values():
    _names["Client Message"] = "Client wording"       # row 1466: the heading before Client Message; every sheet that has the column
OLD["Use cases"].pop("Client Message")                  # a use case has no Client Message column


def make_old(path):
    """Write the older headings over the export, and put back the two Milestones columns the older export had (State: the stored
    state, State set by you), filled with a state that differs from the shown one."""
    wb = load_workbook(str(path))
    for sheet, names in OLD.items():
        for c in wb[sheet][1]:
            if c.value in names:
                c.value = names[c.value]
    ws = wb["Milestones"]
    col = ws.max_column
    ws.cell(1, col + 1, "State")
    ws.cell(1, col + 2, "State set by you")
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value:
            ws.cell(r, col + 1, "Slipped")
            ws.cell(r, col + 2, "Yes")
    wb.save(str(path))
    wb.close()


class OldWorkbook(RoundTrip):
    def setUp(self):
        super().setUp()
        make_old(self.path)

    def heads(self, sheet):
        return [c.value for c in load_workbook(str(self.path))[sheet][1]]

    def test_the_file_really_has_the_old_headings(self):
        self.assertIn("Description", self.heads("Actions"))
        self.assertNotIn("Title", self.heads("Actions"))
        self.assertIn("Shown state", self.heads("Milestones"))
        self.assertIn("State set by you", self.heads("Milestones"))

    def test_an_old_workbook_untouched_imports_with_no_change_and_no_problem(self):
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))

    def test_every_renamed_column_is_read_under_its_old_name(self):
        from test_excel_roundtrip import edit
        edit(self.path, "Actions", self.a1, Description="Old file, reworded", **{"Client-visible": "No"})
        edit(self.path, "Decisions", self.d1, Status="Made", Date=date(2030, 3, 4), Options="Old options text")
        edit(self.path, "Milestones", self.m2, **{"% complete": 65, "Order": 7})
        edit(self.path, "Use cases", self.demo.use_case, **{"Client-visible": "No", "Order": 9})
        p = self.read()
        self.assertEqual(p.problems, [])
        after = {c.table: c.after for c in p.changes}
        self.assertEqual(after["actions"], {"description": "Old file, reworded", "client_visible": 0})
        self.assertEqual(after["decisions"], {"status": "Made", "date": "2030-03-04", "options": "Old options text"})
        self.assertEqual(after["milestones"], {"percent_complete": 65, "sort_order": 7})
        self.assertEqual(after["use_cases"], {"client_visible": 0, "sort_order": 9})
        p.accept_all()
        self.assertTrue(xi.apply_import(self.s, p, xi_user(), state_path=self.state).applied)
        self.assertEqual(self.s.read("actions", ref=self.a1)["description"], "Old file, reworded")
        got = self.s.read("decisions", ref=self.d1)
        self.assertEqual((got["options"], got["date"]), ("Old options text", "2030-03-04"), got)

    def test_a_workbook_headed_client_wording_still_imports_as_the_client_message(self):
        """Row 1390 C, row 1466: Client wording (the heading before Client Message) is read as the Client Message."""
        from test_excel_roundtrip import edit
        self.assertIn("Client wording", self.heads("Actions"))
        self.assertNotIn("Client Message", self.heads("Actions"))
        edit(self.path, "Actions", self.a1, **{"Client wording": "Said under the old heading"})
        p = self.read()
        self.assertEqual(p.problems, [])
        self.assertEqual({c.table: c.after for c in p.changes}["actions"], {"client_message": "Said under the old heading"})

    def test_the_old_state_columns_never_set_a_milestones_state(self):
        before = {r["id"]: (r["state"], r["state_set"]) for r in self.s.read("milestones", "ABC")}
        p = self.read()
        p.accept_all()
        xi.apply_import(self.s, p, xi_user(), state_path=self.state)
        after = {r["id"]: (r["state"], r["state_set"]) for r in self.s.read("milestones", "ABC")}
        self.assertEqual(before, after)
        self.assertEqual([c for c in p.changes if c.table == "milestones"], [])

    def test_a_sheet_with_both_the_old_and_the_new_heading_for_one_column_is_refused_whole(self):
        """Item 1390: Title and Description both on Actions mean the same column; the whole workbook is refused, nothing staged."""
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        ws.cell(1, ws.max_column + 1, "Title")
        wb.save(str(self.path))
        self.assertIn("Description", self.heads("Actions"))
        with self.assertRaises(Invalid) as cm:
            self.read()
        self.assertIn("two columns for the same thing", str(cm.exception))
        self.assertIn("Description", str(cm.exception))
        self.assertIn("Title", str(cm.exception))

    def test_the_gantt_sheet_with_both_dashboard_headings_is_refused_whole_like_the_others(self):
        """Item 1390: On dashboard (older) and On the dashboard (now) are one column; the Gantt sheet refuses the workbook as the other sheets do."""
        wb = load_workbook(str(self.path))
        if "Gantt" in wb.sheetnames:
            del wb["Gantt"]
        ws = wb.create_sheet("Gantt")
        ws.append(["ID", "Line", "On dashboard", "On the dashboard"])
        ws.append(["TBD", "A line", "Yes", "No"])
        wb.save(str(self.path))
        with self.assertRaises(Invalid) as cm:
            xi.read_workbook(self.s, self.path, "ABC", state_path=self.state, sheets=["gantt_lines"])
        self.assertIn("two columns for the same thing", str(cm.exception))
        self.assertIn("On dashboard", str(cm.exception))
        self.assertIn("On the dashboard", str(cm.exception))

    def test_the_old_state_columns_are_ignored_without_a_word(self):
        """Item 1390: State set by you (and the mock-up's State chosen, Chosen by you) is skipped silently, not listed as an unknown column."""
        p = self.read()
        self.assertEqual([n for n in p.notes if "State" in n or "ignored" in n], [], p.notes)
        for old in ("State set by you", "State chosen", "Chosen by you"):
            self.assertIn(xi._key(old), xi.OLD_STATE_COLUMNS, old)

    def test_a_new_row_typed_under_old_headings_is_added(self):
        from test_excel_roundtrip import add_row
        add_row(self.path, "Actions", Description="A new one from an old file", **{"Client-visible": "Yes"})
        (c,) = [c for c in self.read().changes if c.kind == "new"]
        self.assertEqual((c.table, c.after["description"], c.after["client_visible"]), ("actions", "A new one from an old file", 1))


class Aliases(unittest.TestCase):
    """The alias tables themselves (the Gantt sheet has its own)."""

    def test_the_gantt_sheet_reads_the_old_and_the_new_heading_for_the_flag(self):
        self.assertEqual(xi.GANTT_HEADERS["on dashboard"], "show")
        self.assertEqual(xi.GANTT_HEADERS["on the dashboard"], "show")

    def test_each_old_heading_maps_to_the_field_the_export_now_writes(self):
        for table, sheet_names in (("actions", OLD["Actions"]), ("raid", OLD["Risks & Issues"]), ("decisions", OLD["Decisions"]),
                                   ("milestones", OLD["Milestones"]), ("use_cases", OLD["Use cases"])):
            for new, old in sheet_names.items():
                header, _, ignored = xi.header_map(["ID", old], table, {"id", excel.COLUMN_OF[table][new]}, "T")
                self.assertEqual(ignored, [], (table, old))
                if excel.COLUMN_OF[table][new] not in excel.DERIVED:
                    self.assertIn(excel.COLUMN_OF[table][new], header, (table, old))

    def test_the_export_no_longer_writes_the_two_state_columns(self):
        labels = [label for label, _ in dict(((n, c) for n, t, c, _ in excel.SHEETS))["Milestones"]]
        self.assertEqual(labels.count("State"), 1)
        self.assertNotIn("State set by you", labels)
        self.assertNotIn("Shown state", labels)
        self.assertEqual(excel.COLUMN_OF["milestones"]["State"], "shown_state")


def xi_user():
    from _demo import USER
    return USER


if __name__ == "__main__":
    unittest.main()
