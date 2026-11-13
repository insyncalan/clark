"""Hunt on v1.0.7, Excel: an error cell is not text; the Gantt sheet's Status follows the page; a Gantt tab cannot take the
name of a sheet written after it; a use case's 'Shown as' is held to the app's rules on import."""
import unittest
from datetime import date

import _workbook as wbk
from _demo import USER
from clark import excel
from openpyxl import load_workbook
from test_excel_import import ImportCase


class ErrorCells(ImportCase):
    def test_an_error_cell_is_ignored_with_a_note_not_imported_as_text(self):
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        col = wbk._col(ws, "description")
        row = wbk._row_of(ws, self.a1)
        ws.cell(row, col).value = "#REF!"
        ws.cell(row, col).data_type = "e"
        wb.save(str(self.path))
        p = self.plan()
        self.assertEqual([c for c in p.changes if c.after.get("description")], [])
        self.assertTrue(any("error cell was ignored" in n and f"row {row}" in n for n in p.notes), p.notes)

    def make_error(self, *fields, unread=False):
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        row = wbk._row_of(ws, self.a1)
        cells = [ws.cell(row, wbk._col(ws, f)) for f in fields]
        if unread:
            cells = [ws.cell(row, ws.max_column + 3)]
        for c in cells:
            c.value = "#REF!"
            c.data_type = "e"
        wb.save(str(self.path))
        return row

    def test_an_error_in_the_id_cell_says_so_not_formula_and_the_item_is_not_removed(self):
        row = self.make_error("id")
        p = self.plan()
        msgs = [x.message for x in p.problems if f"row {row}" in x.message]
        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn("the ID is an error value", msgs[0])
        self.assertNotIn("formula", msgs[0])
        self.assertEqual([c.id for c in p.changes if c.kind == "removed"], [], "the item whose ID cell broke is not offered for archiving")

    def test_an_error_in_both_the_id_and_the_title_holds_the_whole_sheet_from_archiving(self):
        row = self.make_error("id", "description")
        p = self.plan()
        self.assertEqual([c for c in p.changes if c.kind == "removed" and c.table == "actions"], [])
        self.assertTrue(any(f"row {row}" in x.message and "ID and the title are error values" in x.message for x in p.problems), p.problems)

    def test_an_error_in_a_column_the_import_does_not_read_says_nothing(self):
        self.make_error(unread=True)
        p = self.plan()
        self.assertFalse(any("error cell" in n for n in p.notes), p.notes)

    def test_the_error_note_says_type_the_value_instead(self):
        row = self.make_error("description")
        p = self.plan()
        self.assertIn(f"Actions: an error cell was ignored in row {row}; type the value instead", p.notes)


class UseCaseShownAs(ImportCase):
    def shown(self, text):
        wbk.edit(self.path, "Use cases", self.demo.use_case, ref=text)
        return self.plan()

    def test_a_long_or_hidden_character_ref_is_refused(self):
        for text in ("x" * 21, "1‮1"):
            p = self.shown(text)
            self.assertEqual([c for c in p.changes if "ref" in c.after], [], text)
            self.assertTrue(any("Shown as must be plain text" in x.message for x in p.problems), p.problems)

    def test_a_ref_another_use_case_has_is_refused(self):
        with self.s.step("dashboard", USER) as st:
            st.create("use_cases", {"project": "ABC", "title": "Other", "status": "On track", "ref": "1.1", "source": "demo"})
        wbk.make_workbook(self.s, self.path)
        p = self.shown("1.1")
        self.assertEqual([c for c in p.changes if "ref" in c.after], [])
        self.assertTrue(any("already used" in x.message for x in p.problems), p.problems)

    def test_a_fresh_ref_still_imports(self):
        p = self.shown("7.5")
        self.assertEqual([c.after.get("ref") for c in p.changes], ["7.5"])


class GanttStatus(unittest.TestCase):
    def test_no_end_date_is_not_late_and_a_milestone_uses_its_start(self):
        t = "2026-11-13"
        self.assertEqual(excel.gantt_status({"type": "task", "start": "2026-01-01", "pct": 0}, t), "In progress")
        self.assertEqual(excel.gantt_status({"type": "task", "pct": 0}, t), "Not started")
        self.assertEqual(excel.gantt_status({"type": "milestone", "start": "2026-11-10", "end": "2026-12-01"}, t), "Late")
        self.assertEqual(excel.gantt_status({"type": "milestone", "start": "2026-11-20", "end": "2026-11-01"}, t), "Not started")
        self.assertEqual(excel.gantt_status({"type": "milestone", "start": "2026-11-13"}, t), "Not started")


class GanttTabName(unittest.TestCase):
    def test_a_tab_named_like_a_later_sheet_is_not_used(self):
        rows = {"gantt_lines": [{"id": "G1", "name": "a", "type": "task"}], "milestones": [{"id": "M1", "name": "m", "workstream": "W"}]}
        for tab in ("Lists", "History", "Cover", "lists"):
            wb = excel.workbook("P", rows, on=date(2026, 11, 13), gantt_tab=tab)
            self.assertEqual(len(wb.sheetnames), len(set(n.lower() for n in wb.sheetnames)), wb.sheetnames)
            self.assertFalse([n for n in wb.sheetnames if n in ("Lists1", "History1", "Cover1")], (tab, wb.sheetnames))


if __name__ == "__main__":
    unittest.main()
