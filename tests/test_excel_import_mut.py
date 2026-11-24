"""Pins for survivors of a hand-made mutation sweep of excel_import.py: each test fails on a small change to the module and passes on
the real one (the mutant is named in each docstring). Fictional data only.

Run: python3 dev/run_tests.py test_excel_import_mut
"""
import io
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock
from datetime import date, datetime
from pathlib import Path

from _demo import USER, DemoStore
import _workbook as wbk
from test_excel_import_caps import HEAD, TAIL, part_of, rewrite
from clark import excel_import as xi
from clark.store import Invalid, columns
from openpyxl import Workbook, load_workbook
from clark import excel


class PureCells(unittest.TestCase):
    def test_a_text_cell_of_exactly_the_limit_is_read_and_one_more_is_refused(self):
        """Mutants: MAX_TEXT + 1 (a cell of 10,001 characters read), `>=` (a cell of exactly 10,000 refused)."""
        self.assertEqual(xi.from_cell("description", "x" * 10000, "TEXT"), ("x" * 10000, None))
        value, why = xi.from_cell("description", "x" * (10001), "TEXT")
        self.assertIsNone(value)
        self.assertIn("too long", why)

    def test_the_active_column_is_a_yes_no_flag(self):
        """Mutant: "active" dropped from FLAGS."""
        self.assertEqual(xi.from_cell("active", "Yes", "INTEGER"), (1, None))
        self.assertEqual(xi.from_cell("active", "no", "INTEGER"), (0, None))

    def test_a_heading_with_a_dash_names_the_column_with_an_underscore(self):
        """Mutant: _key leaves the dash."""
        self.assertEqual(xi._key(" Client-Visible "), "client_visible")
        self.assertEqual(xi._key("due \t date"), "due_date")

    def test_characters_a_workbook_cannot_hold_are_dropped_and_the_separators_become_spaces(self):
        """Mutant: cell_text drops the separators instead of making them spaces."""
        self.assertEqual(xi.cell_text("a\x0bb\x1cc"), "a b c")
        self.assertEqual(xi.cell_text("a\x01b"), "ab")
        self.assertEqual(xi.cell_text(5), 5)

    def test_trailing_blank_lines_are_not_a_difference(self):
        """Mutant: same() no longer trims the end of the whole text first."""
        self.assertTrue(xi.same("a\n\n", "a"))
        self.assertTrue(xi.same("a \nb  \n", "a\nb"))
        self.assertFalse(xi.same("a\n\nb", "a\nb"))

    def test_a_blank_cell_equals_nothing(self):
        """Mutant: same() no longer treats a cell of only blanks as empty."""
        self.assertTrue(xi.same("   ", None))
        self.assertTrue(xi.same("", "  \n "))
        self.assertFalse(xi.same("a", None))

    def test_dates_are_read_with_dots_and_the_clock_has_hard_edges(self):
        """Mutants: no dot separator; hour 24, minute 60 or second 60 accepted (or the second not checked at all)."""
        self.assertEqual(xi.read_date("31.12.2026"), "2026-12-31")
        self.assertEqual(xi.read_date("5/6/2026"), "2026-06-05")
        self.assertEqual(xi.read_date("2026-10-05 23:59:59"), "2026-10-05")
        self.assertEqual(xi.read_date("2026-10-05T00:00"), "2026-10-05")
        for bad in ("2026-10-05 24:00", "2026-10-05 10:60", "2026-10-05 10:00:60", "2026-13-05", "05-13-2026"):
            with self.assertRaises(ValueError, msg=bad):
                xi.read_date(bad)

    def test_a_reference_cell_is_the_bare_id_before_the_name(self):
        """Mutants: no ID check on the head; the head not trimmed."""
        self.assertEqual(xi.resolve_ref("milestone", "ABC-M-001 : Pilot live"), "ABC-M-001")
        self.assertEqual(xi.resolve_ref("milestone", "ABC-M-001: Pilot live"), "ABC-M-001")
        self.assertEqual(xi.resolve_ref("milestone", "Pilot: live"), "Pilot: live", "not an id before the colon: the whole text")

    def test_cells_by_kind(self):
        """Mutants: blank text read as text; y / n not Yes / No; a bool or a fraction as a whole number; a minus sign; a whole float as text."""
        self.assertEqual(xi.from_cell("description", "   ", "TEXT"), (None, None))
        self.assertEqual(xi.from_cell("client_visible", " Y ", "INTEGER"), (1, None))
        self.assertEqual(xi.from_cell("client_visible", "N", "INTEGER"), (0, None))
        self.assertIn("whole number", xi.from_cell("pct", True, "INTEGER")[1])
        self.assertIn("whole number", xi.from_cell("pct", 2.5, "INTEGER")[1])
        self.assertEqual(xi.from_cell("pct", 3.0, "INTEGER"), (3, None))
        self.assertEqual(xi.from_cell("pct", "-3", "INTEGER"), (-3, None))
        self.assertEqual(xi.from_cell("description", 3.0, "TEXT"), ("3", None))
        self.assertEqual(xi.from_cell("description", 2.5, "TEXT"), ("2.5", None))
        self.assertIn("cell holds a date", xi.from_cell("description", datetime(2026, 1, 2), "TEXT")[1])

    def test_an_updated_at_cell_is_a_clash_only_past_its_own_slack(self):
        """Mutants: the slack of text without a fraction; the slack of a date-time; the edge itself; the sign; an unreadable stored time."""
        stored = "2026-10-05 10:00:00.500"
        self.assertFalse(xi._moved("2026-10-05 10:00:00", stored), "text without a fraction: a second of slack")
        self.assertTrue(xi._moved("2026-10-05 10:00:00.0", stored), "text with a fraction: 2 ms of slack")
        self.assertTrue(xi._moved(datetime(2026, 10, 5, 10, 0, 0), stored), "a date-time: 2 ms of slack")
        self.assertFalse(xi._moved("2026-10-05 10:00:01", "2026-10-05 10:00:00"), "exactly the slack is no clash")
        self.assertTrue(xi._moved("2026-10-05 10:00:05", "2026-10-05 10:00:00"), "a cell later than the database")
        self.assertTrue(xi._moved("2026-10-05 10:00:00", "2026-10-05 10:00:05"), "a cell earlier than the database")
        self.assertFalse(xi._moved("2026-10-05 10:00:00", "not a time"))
        self.assertFalse(xi._moved("not a time", "2026-10-05 10:00:00"))


class Letters(unittest.TestCase):
    def test_column_letters_are_numbered_from_one(self):
        """Mutant: the numbering starts at zero."""
        self.assertEqual([xi._column_number(x) for x in ("A", "Z", "AA", "cv", "XFD")], [1, 26, 27, 100, 16384])


class Compare(unittest.TestCase):
    def test_titles_are_compared_without_case_or_extra_blanks(self):
        """Mutants: _title_key keeps the case; or does not collapse the blanks."""
        self.assertEqual(xi._title_key("  Draft   The PLAN "), "draft the plan")
        self.assertEqual(xi._title_key(None), "")

    def test_labels_are_the_same_in_any_order_or_case(self):
        """Mutant: labels compared with their case."""
        self.assertFalse(xi._differs("Alpha, beta", "beta,ALPHA", "labels"))
        self.assertTrue(xi._differs("Alpha", "beta", "labels"))

    def test_a_blank_cell_equals_an_empty_stored_text_but_not_a_filled_one(self):
        """Mutant: a blank cell differs from a stored empty text."""
        self.assertFalse(xi._differs(None, ""))
        self.assertFalse(xi._differs(None, None))
        self.assertTrue(xi._differs(None, "x"))
        self.assertTrue(xi._differs("x", None))
        self.assertFalse(xi._differs("a \n", "a"))

    def test_a_not_null_column_with_an_empty_default_means_empty_when_cleared(self):
        """Mutant: _is_blank_default ignores NOT NULL."""
        self.assertTrue(xi._is_blank_default(("TEXT", True, "''")))
        self.assertFalse(xi._is_blank_default(("TEXT", False, "''")))
        self.assertFalse(xi._is_blank_default(("TEXT", True, None)))


class GanttCells(unittest.TestCase):
    def test_blank_and_percent_cells(self):
        """Mutants: a blank of spaces is not blank; a blank percent is None; a percent of three digits is not read; an unknown health loses its trim."""
        self.assertTrue(xi._gantt_blank("   "))
        self.assertTrue(xi._gantt_blank(None))
        self.assertFalse(xi._gantt_blank("x"))
        self.assertFalse(xi._gantt_blank(0))
        self.assertEqual(xi.gantt_cell_value("pct", None), 0)
        self.assertEqual(xi.gantt_cell_value("pct", "  "), 0)
        self.assertEqual(xi.gantt_cell_value("pct", "100"), 100)
        self.assertEqual(xi.gantt_cell_value("pct", " 7 "), 7)
        self.assertEqual(xi.gantt_cell_value("pct", 1000.0 / 10), 100)
        self.assertEqual(xi.gantt_cell_value("health", " Weird "), "Weird")
        self.assertEqual(xi.gantt_cell_value("health", " amber "), "Amber")

    def test_an_empty_name_always_differs_because_the_data_layer_would_refuse_it(self):
        """Mutant: the name may be blank."""
        self.assertTrue(xi.gantt_differs("name", "", ""))
        self.assertFalse(xi.gantt_differs("owner", "", ""))
        self.assertFalse(xi.gantt_differs("owner", "Sam", "Sam"))


class GanttCompare(unittest.TestCase):
    def test_effort_and_budget_compare_by_number(self):
        """Mutants: a blank new value is never a difference; a true is the same as 1."""
        self.assertFalse(xi.gantt_differs("effort", None, None))
        self.assertTrue(xi.gantt_differs("effort", None, 5))
        self.assertTrue(xi.gantt_differs("budget", 5, None))
        self.assertTrue(xi.gantt_differs("effort", True, 1), "a yes is not the number one")
        self.assertFalse(xi.gantt_differs("effort", 5.0, 5))
        self.assertTrue(xi.gantt_differs("effort", 5.5, 5))


class SheetShape(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()

    def tearDown(self):
        self.demo.close()

    def test_a_blank_heading_is_skipped_not_reported_as_unknown(self):
        """Mutant: a heading of only spaces is looked up like any other."""
        header, named, ignored = xi.header_map(["id", "   ", None, "Mystery"], "actions", ["id", "description"], "Actions")
        self.assertEqual((header, ignored), ({"id": 0}, ["Mystery"]))

    def test_a_sheet_with_no_id_column_counts_no_rows(self):
        """Mutant: such a sheet counts one row."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Actions"
        ws.append(["description"])
        ws.append(["Draft the plan"])
        cols = columns(self.demo.store.con, "actions")
        self.assertEqual(xi._rows_counted(ws, "actions", cols), 0)
        ws2 = wb.create_sheet("B")
        ws2.append(["id", "description"])
        ws2.append([None, "Draft the plan"])
        self.assertEqual(xi._rows_counted(ws2, "actions", cols), 1)

    def test_the_gantt_sheet_needs_both_the_id_and_the_line_columns(self):
        """Mutant: a sheet with only an ID column is offered as the Gantt sheet."""
        wb = Workbook()
        only_id = wb.active
        only_id.append(["ID", "Owner"])
        only_id.append(["ABC-G-001", "Sam"])
        self.assertIsNone(xi._gantt_listed(only_id, None))
        both = wb.create_sheet("Gantt")
        both.append(["ID", "Line"])
        both.append(["ABC-G-001", "Plan"])
        self.assertEqual(xi._gantt_listed(both, None), 1)

    def test_a_gantt_sheet_that_reaches_exactly_the_cell_limit_is_still_listed(self):
        """Mutant: the cell limit is hit at exactly 200,000 (2,000 rows by 100 columns)."""
        wb = Workbook()
        ws = wb.active
        ws.append(["ID", "Line"])
        ws.cell(2000, 100).value = "x"
        self.assertEqual((ws.max_row, ws.max_column), (2000, 100))
        self.assertEqual(xi._gantt_listed(ws, None), 1)
        ws.cell(2001, 100).value = "x"
        self.assertEqual(xi._gantt_listed(ws, None), xi.OVER_LIMIT, "one row more is over the limit")


class Reach(unittest.TestCase):
    """The limits on how much of a workbook is read, at the exact edge."""

    def setUp(self):
        self.demo = DemoStore()
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-xlmut-"))
        self.path = wbk.make_workbook(self.demo.store, self.tmp / "ABC.xlsx")

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def corner(self, sheet, row, col="CV"):
        rewrite(self.path, part_of(self.path, sheet), HEAD + '<row r="%d"><c r="%s%d"><v>1</v></c></row>' % (row, col, row) + TAIL)

    def empty(self, sheet):
        rewrite(self.path, part_of(self.path, sheet), HEAD + TAIL)

    def early(self):
        xi.check_sheets_early(self.path, lambda t: t in ("Actions", "RAID", "Decisions"))

    def test_the_sheets_together_may_span_exactly_the_total_and_not_one_cell_more(self):
        """Mutant: MAX_TOTAL_CELLS = 400,001."""
        self.corner("Actions", 2000)           # 2,000 rows by 100 columns: 200,000 cells, the most one sheet may span
        self.corner("RAID", 2000)
        self.empty("Decisions")
        self.early()                           # 400,000 together: allowed
        self.corner("Decisions", 1, "A")       # one cell more
        with self.assertRaises(Invalid) as cm:
            self.early()
        self.assertIn("too large together", str(cm.exception))

    def test_a_text_of_exactly_one_more_than_excel_keeps_is_refused(self):
        """Mutant: MAX_CELL_TEXT = 32,768 (the limit moved up by one)."""
        for size, refused in ((32767, False), (32768, True)):
            path = self.tmp / ("t%d.xlsx" % size)
            shutil.copy(self.path, path)
            rewrite(path, "xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<si><t>%s</t></si></sst>' % ("z" * size))
            if refused:
                with self.assertRaises(Invalid):
                    xi.check_sheets_early(path, lambda t: True)
            else:
                xi.check_sheets_early(path, lambda t: True)


class Scan(unittest.TestCase):
    """The streaming check of a workbook's parts, at its edges."""

    def setUp(self):
        self.demo = DemoStore()
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-xlmut-"))
        self.path = wbk.make_workbook(self.demo.store, self.tmp / "ABC.xlsx")

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def strings(self, body):
        path = self.tmp / "s.xlsx"
        shutil.copy(self.path, path)
        rewrite(path, "xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>%s</t></si></sst>' % body)
        return path

    def test_a_member_of_exactly_the_limit_is_read_and_one_byte_more_is_not(self):
        """Mutant: _small_member refuses a member of exactly `limit` bytes."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("ten", b"0123456789")
            z.writestr("eleven", b"0123456789A")
        with zipfile.ZipFile(buf) as z:
            self.assertEqual(xi._small_member(z, "ten", limit=10), b"0123456789")
            self.assertIsNone(xi._small_member(z, "eleven", limit=10))
            self.assertIsNone(xi._small_member(z, "missing", limit=10))

    def test_the_too_large_sentence_never_says_zero(self):
        """Mutant: the numbers are written as they are."""
        text = xi._too_large("Actions", 0, 0)
        self.assertIn("1 rows by 1 columns", text)
        self.assertIn("The Actions sheet is too large (5,000 rows by 40 columns", xi._too_large("Actions", 5000, 40))

    def test_a_long_text_made_of_entities_is_measured_after_they_are_read(self):
        """Mutants: the raw length of a text is the test; the read-back text is refused at exactly the limit; a part held in the buffer
        is cut at one Excel cell instead of eight."""
        xi.check_sheets_early(self.strings("&amp;" * 15000), lambda t: True)           # 75,000 raw, 15,000 as read: fine
        xi.check_sheets_early(self.strings("&amp;" * 32767), lambda t: True)     # exactly what Excel keeps
        with self.assertRaises(Invalid):
            xi.check_sheets_early(self.strings("&amp;" * (32768)), lambda t: True)

    def sheet(self, xml):
        rewrite(self.path, part_of(self.path, "Actions"), HEAD + xml + TAIL)

    def test_the_cell_count_limit_is_at_500000_and_counts_every_cell_tag(self):
        """Mutant: the count is refused at exactly 5,000 x 100 cells."""
        self.sheet('<row r="1">%s</row>' % ('<c r="A1"/>' * 500000))
        xi.check_sheets_early(self.path, lambda t: t == "Actions")
        self.sheet('<row r="1">%s</row>' % ('<c r="A1"/>' * 500001))
        with self.assertRaises(Invalid) as cm:
            xi.check_sheets_early(self.path, lambda t: t == "Actions")
        self.assertIn("too large", str(cm.exception))

    def test_a_part_is_read_only_as_far_as_the_limit_on_a_member(self):
        """Mutant: the scan goes on reading after excel.MAX_MEMBER_BYTES."""
        far = '<row r="6000"><c r="A6000"/></row>'
        self.sheet('<row r="1"><c r="A1"/></row>' + " " * 300000 + far)
        with mock.patch.object(xi.excel, "MAX_MEMBER_BYTES", 100000):
            self.assertEqual(xi._scan_member(zipfile.ZipFile(self.path), part_of(self.path, "Actions"), "Actions"), (1, 1))
        with self.assertRaises(Invalid):
            xi.check_sheets_early(self.path, lambda t: t == "Actions")          # at the real limit the far row is still read


class Locked(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        with self.demo.store.step("dashboard", USER) as st:
            self.r1 = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Key person leaves", "raised": "2026-10-01",
                                         "impact": "High", "likelihood": "Medium", "source": "demo"})
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-xlmut-"))
        self.path = wbk.make_workbook(self.demo.store, self.tmp / "ABC.xlsx")

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_typed_risk_priority_is_never_read_it_is_worked_out_from_impact_and_likelihood(self):
        """Mutant: LOCKED_IN no longer holds raid's priority."""
        wbk.edit(self.path, "RAID", self.r1, priority="Low" if self.demo.store.read("raid", ref=self.r1)["priority"] != "Low" else "High")
        plan = xi.read_workbook(self.demo.store, self.path, "ABC", allow_unrecorded=True)
        self.assertEqual([(c.kind, c.id) for c in plan.changes], [])


class ReadPlan(unittest.TestCase):
    """read_workbook's decisions about the record, the sheet and the rows that are missing."""

    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.a1 = self.demo.action(description="Draft the cut-over plan", due_date="2026-11-01")
        self.a3 = self.demo.action(description="Agree the test dates", workstream="Build")
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-xlmut-"))
        self.path = wbk.make_workbook(self.s, self.tmp / "ABC.xlsx")
        self.state = self.tmp / "state.json"

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self, path=None, **kw):
        return xi.read_workbook(self.s, path or self.path, "ABC", state_path=self.state, **kw)

    def test_a_workbook_with_no_record_is_unrecorded_and_needs_confirming(self):
        """Mutants: unrecorded is never set; unrecorded_ok is always true."""
        plan = self.plan()
        self.assertTrue(plan.unrecorded)
        self.assertFalse(plan.unrecorded_ok)
        self.assertTrue(any("no record of exporting" in n for n in plan.notes))
        ok = self.plan(allow_unrecorded=True)
        self.assertTrue(ok.unrecorded_ok)

    def test_a_record_with_no_project_is_kept_and_one_of_another_project_is_not(self):
        """Mutant: only a record that names this project is kept."""
        with mock.patch.object(xi.excel, "load_state", return_value={"hash": "h", "rows": {}}):
            self.assertFalse(self.plan().unrecorded, "an older record names no project: it is this one's")
        with mock.patch.object(xi.excel, "load_state", return_value={"hash": "h", "rows": {}, "project": "ABC"}):
            self.assertFalse(self.plan().unrecorded)
        with mock.patch.object(xi.excel, "load_state", return_value={"hash": "h", "rows": {}, "project": "OTHER"}):
            self.assertTrue(self.plan().unrecorded, "another project's record is no record for this one")

    def test_a_file_whose_hash_cannot_be_worked_out_is_never_the_one_imported(self):
        """Mutant: no hash equals a record with no imported hash."""
        with mock.patch.object(xi.excel, "file_hash", return_value=None):
            self.assertFalse(self.plan().already_imported)

    def test_an_import_that_was_undone_is_read_again(self):
        """Mutant: `undone` is never true (an undone import is still taken as imported)."""
        record = {"hash": "h", "rows": {}, "imported_hash": excel.file_hash(self.path), "imported_step": {"step": 1, "db_id": "x", "at": "t"}}
        with mock.patch.object(xi.excel, "load_state", return_value=record), mock.patch.object(xi, "in_force", return_value=True):
            self.assertTrue(self.plan().already_imported)
        with mock.patch.object(xi.excel, "load_state", return_value=record), mock.patch.object(xi, "in_force", return_value=False):
            plan = self.plan()
        self.assertFalse(plan.already_imported)
        self.assertTrue(any("has been undone" in n for n in plan.notes))

    def test_the_workbook_may_span_exactly_the_cell_limits_in_the_loaded_check_too(self):
        """Mutants: the loaded sheet check, or the total of the sheets, refuses at exactly the limit."""
        for sheet in ("Actions", "RAID"):
            rewrite(self.path, part_of(self.path, sheet), HEAD + '<row r="2000"><c r="CV2000"><v>1</v></c></row>' + TAIL)
        plan = self.plan(allow_unrecorded=True, sheets=["actions", "raid"])      # 200,000 and 200,000: allowed, and the sheets have no ID column
        self.assertTrue(any("no id column" in p.message for p in plan.problems))

    def test_a_changed_row_comes_before_a_new_one(self):
        """Mutant: new rows are listed before changed ones."""
        wb = load_workbook(self.path)
        ws = wb["Actions"]
        hdr = [c.value for c in ws[1]]
        ws.cell(2, hdr.index("owner") + 1).value = "Sam Example"
        wb.save(self.path)
        wbk.add_row(self.path, "Actions", description="Order the laptops")
        plan = self.plan(allow_unrecorded=True)
        self.assertEqual([c.kind for c in plan.changes], ["changed", "new"])
        self.assertEqual([c.n for c in plan.changes], [1, 2], "numbered from one")

    def test_ten_formula_rows_are_named_and_an_eleventh_says_and_more(self):
        """Mutant: `and more` is added at ten rows."""
        for count, more in ((10, False), (11, True)):
            path = wbk.make_workbook(self.s, self.tmp / ("f%d.xlsx" % count))
            wb = load_workbook(path)
            ws = wb["Actions"]
            col = [c.value for c in ws[1]].index("description") + 1
            for r in range(2, 2 + count):
                ws.cell(r, col).value = "=1+1"
            wb.save(path)
            plan = self.plan(path, allow_unrecorded=True)
            (note,) = [n for n in plan.notes if "formula cell was ignored" in n]
            self.assertEqual(" and more" in note, more, note)

    def test_an_archived_item_that_is_not_in_the_workbook_is_not_offered_for_archiving(self):
        """Mutant: archived items are offered as removed."""
        wbk.drop_row(self.path, "Actions", self.a3)
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.a3)
        plan = self.plan(allow_unrecorded=True)
        self.assertEqual([(c.kind, c.id) for c in plan.changes], [])

    def test_an_empty_sheet_says_nothing_when_the_project_has_none_either(self):
        """Mutant: the 'no rows' note is made even where the database has no rows to lose."""
        wbk.drop_row(self.path, "Milestones", self.demo.milestone)
        plan = self.plan(allow_unrecorded=True)
        self.assertTrue(any("Milestones has no rows" in n for n in plan.notes), "the project has a milestone: the note is made")
        self.assertEqual([n for n in plan.notes if "RAID has no rows" in n or "Decisions has no rows" in n], [],
                         "the project has none of those either: nothing is lost")

    def test_a_clash_is_found_from_the_exports_own_record(self):
        """Mutant: a row changed in clark since the export is never a clash when the export's record is there."""
        mine = self.tmp / "Mine.xlsx"
        excel.export_project(self.s, "ABC", mine, self.state)
        wb = load_workbook(mine)
        ws = wb["Actions"]
        hdr = [c.value for c in ws[1]]
        for r in range(2, ws.max_row + 1):
            if ws.cell(r, hdr.index("ID") + 1).value == self.a1:
                ws.cell(r, hdr.index("Owner") + 1).value = "Sam Example"
        wb.save(mine)
        self.demo.update("actions", self.a1, {"priority": "High"})
        plan = self.plan(mine)
        self.assertFalse(plan.unrecorded)
        (c,) = plan.changes
        self.assertEqual((c.id, c.state, c.clash), (self.a1, "clash", True))

    def test_two_values_that_match_a_missing_item_are_what_make_a_new_row_look_like_its_changed_id(self):
        """Mutants: one value is enough; three are needed."""
        for given, looks in (({"workstream": "Build"}, False), ({"workstream": "Build", "raised": date(2026, 10, 1)}, True)):
            path = wbk.make_workbook(self.s, self.tmp / ("e%d.xlsx" % len(given)))
            wbk.drop_row(path, "Actions", self.a3)
            wbk.add_row(path, "Actions", description="Different words entirely", **given)
            plan = self.plan(path, allow_unrecorded=True)
            self.assertEqual(any("looks like an ID that was changed" in n for n in plan.notes), looks, given)


class MovedTimezone(unittest.TestCase):
    def test_an_updated_at_cell_with_a_timezone_suffix_never_raises_and_compares_by_the_moment(self):
        """Without the fix a Z or +00:00 suffix raised TypeError (aware minus naive)."""
        stored = "2026-10-01 09:30:00"
        for cell in ("2026-10-01T09:30:00Z", "2026-10-01 09:30:00+00:00", "2026-10-01T09:30:00.000Z",
                     "2026-10-01T11:30:00+02:00"):
            self.assertFalse(xi._moved(cell, stored), cell)
        for cell in ("2026-10-01T09:45:00Z", "2026-10-01 09:45:00+00:00"):
            self.assertTrue(xi._moved(cell, stored), cell)
        from datetime import timezone
        self.assertFalse(xi._moved(datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc), stored))
        self.assertFalse(xi._moved("2026-10-01T09:30:00Z", "2026-10-01T09:30:00+00:00"))
        self.assertFalse(xi._moved("not a time Z", stored))


if __name__ == "__main__":
    unittest.main()
