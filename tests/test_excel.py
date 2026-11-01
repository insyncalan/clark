"""#37: the Excel export (src/clark/excel.py), against a real temporary store (#31) with fictional demo data.

Run: python3 dev/run_tests.py test_excel
Shown state is worked out for a fixed day, ON, so nothing depends on the real date.
"""
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock
from datetime import date, datetime
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import USER, DemoStore
from openpyxl import load_workbook

from clark import excel, history, look
from clark import excel_import as xi
from clark import page

FIXED_ID = "0123456789ab4def8123456789abcdef"     # an export id held still, so two exports can be compared byte for byte


_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")    # a brand logo on this computer never changes a test (#133)


def setUpModule():
    global _OLD_BRANDING
    _OLD_BRANDING, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD_BRANDING
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


ON = "2030-06-01"
HEADERS = {
    "Milestones": ["ID", "Milestone", "Project", "Description", "Workstream", "Original", "Agreed", "Forecast", "Status",
                   "Order", "% complete", "Owner", "Shown state", "State", "State set by you", "State reason", "Movement",
                   "Achieved on", "Client-visible", "Client wording", "Internal note", "Source", "Updated"],
    "Actions": ["ID", "Description", "Project", "Workstream", "Owner", "Priority", "Due", "Status", "Raised", "Closed",
                "Latest update", "Client-visible", "Client wording", "Milestone", "Use case", "Labels", "Source", "Updated"],
    "Risks and issues": ["ID", "Description", "Project", "Type", "Workstream", "Owner", "Response action", "Due", "Impact", "Likelihood",
             "Priority", "Status", "Raised", "Closed", "Client-visible", "Client wording", "Milestone", "Use case", "Labels",
             "Source", "Updated"],
    "Decisions": ["ID", "Decision", "Project", "Status", "Made by", "Needed by", "Date", "Reasoning", "Options", "Revisit",
                  "Replaces", "Client-visible", "Client wording", "Use case", "Labels", "Source", "Updated"],
    "Use cases": ["ID", "Use case", "Project", "Shown as", "Status", "Headline", "Where it stands", "Order", "Client-visible",
                  "Source", "Updated"],
}


class Demo:
    """A store with one fictional project (ABC) holding every kind of row: actions, a risk and an issue, decisions, a
    milestone in each state, and use cases."""

    def __init__(self):
        self.demo = DemoStore()
        self.store = self.demo.store
        d = self.demo
        uc = d.use_case
        with self.store.step("dashboard", USER) as st:
            self.action = st.create("actions", {
                "project": "ABC", "description": "Draft the cut-over plan", "workstream": "Build", "owner": "Demo Owner",
                "priority": "High", "due_date": "2030-04-15", "raised": "2030-01-10", "latest_update": "First draft shared",
                "client_message": "The plan is being drafted", "milestone": d.milestone, "use_case": uc, "source": "demo",
                "labels": "Sensitive"})
            self.closed = st.create("actions", {"project": "ABC", "description": "Book the demo room", "raised": "2030-01-11",
                                                "status": "Closed", "closed": "2030-01-20", "client_visible": 0,
                                                "source": "demo"})
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Test data arrives late",
                                           "impact": "High", "likelihood": "Medium", "due_date": "2030-05-01",
                                           "response_action": "Ask for a sample early", "raised": "2030-01-12",
                                           "use_case": uc, "source": "demo"})
            self.issue = st.create("raid", {"project": "ABC", "type": "Issue", "description": "Demo server is slow",
                                            "impact": "Low", "likelihood": "Low", "raised": "2030-01-13", "source": "demo"})
            self.decision = st.create("decisions", {"project": "ABC", "decision": "Pilot with one team", "date": "2030-01-14",
                                                    "made_by": "Demo Sponsor", "reasoning": "Smaller first step",
                                                    "use_case": uc, "source": "demo"})
            self.pending = st.create("decisions", {"project": "ABC", "decision": "Choose the second team", "status": "Pending",
                                                   "needed_by": "2030-07-01", "source": "demo"})
            ms = {}
            for name, values in (
                    ("Achieved", {"baseline_date": "2026-02-01", "status": "Done", "actual_date": "2026-02-03"}),
                    ("At risk", {"baseline_date": "2030-09-01", "state": "At risk", "state_set": 1}),
                    ("Forecast", {"forecast_date": "2030-12-01", "state": "Forecast", "state_set": 1}),
                    ("Overdue", {"baseline_date": "2030-05-01"}),
                    ("Slipped", {"baseline_date": "2030-08-01", "forecast_date": "2030-08-20", "percent_complete": 40}),
                    ("On track", {"baseline_date": "2030-10-01", "owner": "Demo Owner", "internal_note": "Keep an eye"})):
                ms[name] = st.create("milestones", {"project": "ABC", "name": f"{name} milestone", "source": "demo", **values})
            self.milestones = ms
            st.create("use_cases", {"project": "ABC", "title": "Report checks", "status": "Flag", "ref": "1.2",
                                    "headline": "Waiting on access", "standing": "<p>Access is <b>requested</b></p>",
                                    "sort_order": 2, "source": "demo"})
        # The demo milestone (ABC-M-001, agreed 01-03-2030) is rebaselined, so its Original differs from its Baseline.
        d.update("milestones", d.milestone, {"baseline_date": "2030-04-01"},
                 rebaseline={"agreed_with": "Demo Sponsor", "reason": "Scope grew", "source": "Steering, 01-02-2030"})
        self.dir = Path(tempfile.mkdtemp(prefix="clark-excel-"))
        self.path = self.dir / "ABC work items.xlsx"
        self.state = self.dir / "state.json"

    def export(self, **kw):
        return excel.export_project(self.store, "ABC", self.path, self.state, on=ON, **kw)

    def close(self):
        self.demo.close()
        shutil.rmtree(self.dir, ignore_errors=True)


class ExcelTests(unittest.TestCase):
    def setUp(self):
        self.d = Demo()
        self.d.export()

    def tearDown(self):
        self.d.close()

    def sheet(self, name):
        return load_workbook(self.d.path)[name]

    def column(self, ws, label):
        """{ID: cell} for one column."""
        head = [c.value for c in ws[1]]
        i = head.index(label)
        return {r[0].value: r[i] for r in ws.iter_rows(min_row=2) if r[0].value}

    def test_each_sheet_and_its_headers(self):
        wb = load_workbook(self.d.path)
        self.assertEqual(wb.sheetnames, ["Cover", "Milestones", "Actions", "Risks and issues", "Decisions", "Use cases", "History", "Lists"])
        for name, header in HEADERS.items():
            self.assertEqual([c.value for c in wb[name][1]], header, name)

    def test_every_kind_is_there(self):
        types = {k: c.value for k, c in self.column(self.sheet("Risks and issues"), "Type").items()}
        self.assertEqual(types, {self.d.risk: "Risk", self.d.issue: "Issue"})
        self.assertEqual(set(self.column(self.sheet("Actions"), "ID")), {self.d.action, self.d.closed})
        decisions = set(self.column(self.sheet("Decisions"), "ID"))
        self.assertTrue({self.d.decision, self.d.pending} < decisions)       # and the rebaseline's own decision
        self.assertEqual(len(decisions), 3)
        self.assertEqual(len(self.column(self.sheet("Use cases"), "ID")), 2)

    def test_every_milestone_state(self):
        shown = {k: c.value for k, c in self.column(self.sheet("Milestones"), "Shown state").items()}
        for state, ref in self.d.milestones.items():
            self.assertEqual(shown[ref], state)

    def test_dates_are_real_dates_shown_dd_mm_yyyy(self):
        due = self.column(self.sheet("Actions"), "Due")[self.d.action]
        self.assertIsInstance(due.value, datetime)
        self.assertEqual(due.value.date(), date(2030, 4, 15))
        self.assertEqual(due.number_format, "dd-mm-yyyy")
        needed = self.column(self.sheet("Decisions"), "Needed by")[self.d.pending]
        self.assertEqual((needed.value.date(), needed.number_format), (date(2030, 7, 1), "dd-mm-yyyy"))
        ws = self.sheet("Actions")
        self.assertEqual(ws.cell(row=200, column=HEADERS["Actions"].index("Due") + 1).number_format, "dd-mm-yyyy")  # new rows too

    def test_original_date_comes_from_the_history(self):
        ws = self.sheet("Milestones")
        m = self.d.demo.milestone
        self.assertEqual(self.column(ws, "Original")[m].value.date(), date(2030, 3, 1))
        self.assertEqual(self.column(ws, "Agreed")[m].value.date(), date(2030, 4, 1))

    def test_round_trip_gives_the_database_values(self):
        back = excel.read_workbook(self.d.path)
        for _, table, cols, _ in excel.SHEETS:
            fields = [f for _, f in cols if f not in excel.DERIVED and f != "labels"]
            stored = {r["id"]: {f: r[f] for f in fields} for r in self.d.store.read(table, "ABC")}
            got = {r["id"]: {f: r.get(f) for f in fields} for r in back[table]}
            self.assertEqual(got, stored, table)
        labels = {r["id"]: r["labels"] for r in back["actions"]}
        self.assertEqual(labels, {self.d.action: "Sensitive", self.d.closed: None})

    def test_drop_downs_and_locked_columns(self):
        ws = self.sheet("Actions")
        rules = [(dv.type, dv.formula1) for dv in ws.data_validations.dataValidation]
        self.assertIn(("custom", "FALSE"), rules)                                # locked ID, source, updated
        self.assertIn(("list", '"Open,Delayed,Closed,Cancelled"'), rules)
        ms = [(dv.type, dv.formula1) for dv in self.sheet("Milestones").data_validations.dataValidation]
        self.assertIn(("list", '"On track,At risk,Slipped,Overdue,Forecast,Achieved"'), ms)

    def test_the_id_column_is_shaded_and_nothing_is_locked_or_protected(self):
        """#85d: no cell locks and no sheet protection (Excel won't sort a range with locked cells; the Cover is unprotected on
        purpose too). The ID column is shaded, with a header note and an input message on each ID cell."""
        for name, table, cols, _ in excel.SHEETS:
            ws = self.sheet(name)
            n = len(self.d.store.read(table, "ABC"))
            self.assertFalse(ws.protection.sheet, name)
            self.assertGreater(n, 0)
            default = (True, False)    # no cell carries a lock flag of its own: the ID is like the rest
            for row in range(2, n + 2 + excel.EXTRA_ROWS):
                for col in range(1, len(cols) + 1):
                    c = ws.cell(row=row, column=col)
                    self.assertEqual((c.protection.locked, c.protection.hidden), default, (name, row, col))
            for row in range(2, n + 2):
                self.assertEqual(ws.cell(row=row, column=1).fill.fgColor.rgb[-6:], look.colour("grey-100"), (name, row))
            self.assertNotEqual(ws.cell(row=n + 2, column=1).fill.fgColor.rgb[-6:], look.colour("grey-100"))
            self.assertIn(excel.ID_NOTE, ws["A1"].comment.text)
            self.assertEqual(excel.ID_NOTE, "IDs are given by clark. Don't change or move an ID, and don't sort the ID column on its own: an ID moved to another row takes that row's details with it when the file is imported. Leave the ID empty on a new row.")
            prompts = {str(dv.sqref): dv for dv in ws.data_validations.dataValidation          # the ID column's (A) prompts;
                       if dv.prompt and all(r.min_col == 1 for r in dv.sqref.ranges)}         # #127 adds Owner's elsewhere
            self.assertEqual(sorted(prompts), sorted([f"A2:A{n + 1}", f"A{n + 2}:A{n + 1 + excel.EXTRA_ROWS}"]), name)
            old = prompts[f"A2:A{n + 1}"]
            new = prompts[f"A{n + 2}:A{n + 1 + excel.EXTRA_ROWS}"]
            self.assertEqual(old.prompt, "Don't change this ID: if it changes, this row's details go to another item when the file is imported.")
            self.assertEqual(new.prompt, "Leave the ID empty for a new item. clark gives it an ID when the file is imported.")
            for dv in (old, new):
                self.assertTrue(dv.showInputMessage)
                self.assertEqual(dv.promptTitle, "ID")
                self.assertIsNone(dv.type)      # a message only: it refuses nothing
            # the old "FALSE" rule covers the other set-by-clark columns, never the ID column
            for dv in ws.data_validations.dataValidation:
                if dv.formula1 == "FALSE":
                    self.assertFalse(any(r.min_col == 1 for r in dv.sqref.ranges), name)

    def test_the_milestones_id_note_does_not_start_a_line_with_clark(self):
        text = self.sheet("Milestones")["A1"].comment.text
        for line in text.splitlines():
            self.assertFalse(line.startswith("clark"), line)

    def test_a_row_typed_with_an_empty_id_is_new_and_an_untouched_export_has_no_changes(self):
        from clark import excel_import as xi
        plan = xi.read_workbook(self.d.store, self.d.path, "ABC")
        self.assertEqual(([c for c in plan.changes if c.kind != "unchanged"], plan.problems), ([], []))
        wb = load_workbook(self.d.path)
        ws = wb["Actions"]
        n = len(self.d.store.read("actions", "ABC"))
        head = {c.value: c.column for c in ws[1]}
        self.assertIsNone(ws.cell(row=n + 2, column=head["ID"]).value)
        ws.cell(row=n + 2, column=head["Description"]).value = "Typed in a spare row"
        wb.save(self.d.path)
        plan = xi.read_workbook(self.d.store, self.d.path, "ABC")
        new = [c for c in plan.changes if c.kind == "new"]
        self.assertEqual([(c.table, c.after.get("description")) for c in new], [("actions", "Typed in a spare row")])
        self.assertEqual(plan.problems, [])

    def test_refuses_to_overwrite_unimported_edits(self):
        wb = load_workbook(self.d.path)
        wb["Actions"].cell(row=2, column=2, value="Changed in Excel")
        wb.save(self.d.path)
        before = self.d.path.read_bytes()
        with self.assertRaises(excel.Refused) as e:
            self.d.export()
        self.assertIn("ABC work items.xlsx has edits that haven't been imported", str(e.exception))
        self.assertEqual(self.d.path.read_bytes(), before)
        excel.mark_imported(self.d.path, self.d.state)            # once imported, the export may overwrite it
        self.d.export()
        self.assertNotEqual(self.d.path.read_bytes(), before)

    def test_an_unchanged_workbook_is_overwritten(self):
        with self.d.store.step("dashboard", USER) as st:
            st.update("actions", self.d.action, {"owner": "Second Owner"})
        self.d.export()
        self.assertEqual(self.column(self.sheet("Actions"), "Owner")[self.d.action].value, "Second Owner")

    def test_no_workbook_is_written(self):
        self.d.path.unlink()
        self.d.state.unlink()
        self.d.export()
        self.assertTrue(self.d.path.exists())

    def test_a_workbook_it_did_not_write_is_not_overwritten(self):
        self.d.state.unlink()
        with self.assertRaises(excel.Refused) as e:
            self.d.export()
        self.assertIn("ABC work items.xlsx already exists", str(e.exception))

    def test_refuses_while_open_in_excel(self):
        excel.lock_file(self.d.path).write_bytes(b"lock")
        with self.assertRaises(excel.Refused) as e:
            self.d.export()
        self.assertIn("open in Excel", str(e.exception))

    def test_archived_rows_are_left_out(self):
        self.d.store.con.execute("UPDATE actions SET archived = 1 WHERE id = ?", (self.d.closed,))
        self.d.store.con.commit()
        self.d.export()
        self.assertEqual(set(self.column(self.sheet("Actions"), "ID")), {self.d.action})

    def test_the_default_place_and_name(self):
        path = excel.export_project(self.d.store, "ABC", on=ON)
        self.assertEqual(path, self.d.demo.dir / "ABC work items.xlsx")
        self.assertTrue((self.d.demo.dir / excel.STATE_FILE).exists())


class RowsOnly(unittest.TestCase):
    """export() needs only rows, not a store."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-excel-"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_characters_a_workbook_cannot_hold_are_left_out(self):
        """As creaite's #127 test: control characters and U+FFFE/U+FFFF go, tab and line breaks stay."""
        path = self.dir / "DEMO.xlsx"
        rows = {"actions": [{"id": "DEMO-A-001", "project": "DEMO", "description": "Book\x07 the\x0bdemo￾ room\tnow\nplease",
                             "raised": "2030-01-01", "client_message": "", "client_visible": 1, "source": "demo"}]}
        counts = excel.export(path, "DEMO", rows, self.dir / "state.json")
        self.assertEqual(counts["actions"], 1)
        self.assertEqual(counts["raid"], 0)
        self.assertEqual(excel.read_workbook(path)["actions"][0]["description"], "Book the demo room\tnow\nplease")
        bad = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                self.assertIsNone(bad.search(z.read(name).decode("utf-8", "surrogatepass")), name)

    def rows(self, **fields):
        return {"actions": [{"id": "DEMO-A-001", "project": "DEMO", "raised": "2030-01-01", "client_message": "",
                             "client_visible": 1, "source": "demo", **fields}]}

    def test_text_that_could_be_a_formula_is_neutralised_and_comes_back(self):
        """Review: =1+1 or =HYPERLINK(...) was a live formula. Now a leading apostrophe; read back it is the same text."""
        path = self.dir / "DEMO.xlsx"
        values = ["=1+1", '=HYPERLINK("http://x.invalid","hi")', "+1", "-cmd", "@SUM(A1)", "\tTabbed", "'quoted",
                  "'=1", "''", "a=b", "-5", "#N/A", "=", "plain", " =1"]
        for text in values:
            rows = {"actions": [self.rows(description=text, owner=text, client_message=text)["actions"][0]]}
            excel.export(path, "DEMO", rows, self.dir / "state.json", on=ON)
            got = excel.read_workbook(path)["actions"][0]
            for f in ("description", "owner", "client_message"):
                self.assertEqual(got[f], text, (f, text))
            ws = load_workbook(path)["Actions"]                          # not data_only: formulas would show as 'f'
            for c in ws[2]:
                self.assertNotEqual(c.data_type, "f", (text, c.coordinate))
            for c in (ws.cell(row=2, column=2), ws.cell(row=2, column=5)):
                self.assertEqual(c.data_type, "s", (text, c.coordinate))
            with zipfile.ZipFile(path) as z:
                sheets = [z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("xl/worksheets/sheet")]
            self.assertFalse(any("<f>" in x or "<f " in x for x in sheets), text)
            os_state = self.dir / "state.json"
            os_state.unlink()
            path.unlink()

    def test_a_carriage_return_becomes_a_line_feed_so_it_cannot_lead(self):
        self.assertEqual(excel.to_cell("description", "\r=1"), "\n=1")        # a leading CR/LF is no formula start in Excel
        self.assertEqual(excel.to_cell("description", "a\r\nb"), "a\nb")
        self.assertEqual(excel.from_cell("description", "'\r=1"), "\r=1")     # but a CR found in a file is undone like the rest

    def test_the_escape_rule(self):
        for text, cell in (("=1+1", "'=1+1"), ("+1", "'+1"), ("-cmd", "'-cmd"), ("@x", "'@x"), ("\tx", "'\tx"),
                           ("'q", "''q"), ("'=1", "''=1"), ("a=b", "a=b"), ("x'", "x'"), ("", "")):
            self.assertEqual(excel.to_cell("description", text), cell)
            self.assertEqual(excel.from_cell("description", cell) if cell else None, text or None)
        self.assertEqual(excel.escape_text("\rx"), "'\rx")                    # (to_cell turns a CR into a line feed first)
        self.assertEqual(excel.from_cell("description", "'abc"), "'abc")      # typed in Excel: no escape to undo
        self.assertEqual(excel.from_cell("description", "=A1+1"), "=A1+1")    # a typed formula stays its text

    def test_numbers_and_dates_are_not_touched(self):
        path = self.dir / "DEMO.xlsx"
        self.assertEqual(excel.to_cell("sort_order", -5), -5)
        self.assertEqual(excel.to_cell("percent_complete", -5), -5)
        self.assertEqual(excel.to_cell("due_date", "2030-04-15"), date(2030, 4, 15))
        rows = {"milestones": [{"id": "DEMO-M-001", "project": "DEMO", "name": "-5", "sort_order": -5, "percent_complete": 40,
                                "baseline_date": "2030-04-01", "status": "Planned", "source": "demo"}]}
        excel.export(path, "DEMO", rows, self.dir / "state.json", on=ON)
        ws = load_workbook(path)["Milestones"]
        head = [c.value for c in ws[1]]
        order, name = ws.cell(row=2, column=head.index("Order") + 1), ws.cell(row=2, column=head.index("Milestone") + 1)
        self.assertEqual((order.value, order.data_type), (-5, "n"))
        self.assertEqual((name.value, name.data_type), ("'-5", "s"))
        back = excel.read_workbook(path)["milestones"][0]
        self.assertEqual((back["sort_order"], back["name"], back["baseline_date"]), (-5, "-5", "2030-04-01"))

    def test_a_formula_found_in_an_edited_workbook_is_read_as_its_text(self):
        path = self.dir / "DEMO.xlsx"
        excel.export(path, "DEMO", self.rows(description="x"), self.dir / "state.json", on=ON)
        wb = load_workbook(path)
        wb["Actions"]["B2"] = '=HYPERLINK("http://x.invalid","hi")'     # as someone might type it in Excel
        wb["Actions"]["E2"] = "=1+1"
        self.assertEqual(wb["Actions"]["B2"].data_type, "f")
        wb.save(path)
        got = excel.read_workbook(path)["actions"][0]
        self.assertEqual((got["description"], got["owner"]), ('=HYPERLINK("http://x.invalid","hi")', "=1+1"))

    def test_the_same_rows_and_day_give_the_same_bytes(self):
        """Review: created/modified times and the zip's member times made every export differ."""
        rows = self.rows(description="Book the room")
        out = []
        for real in (datetime(2031, 1, 1, 9, 0, 1), datetime(2031, 1, 1, 9, 0, 5), datetime(2032, 5, 6, 7, 8, 9)):
            with mock.patch.object(excel, "clock", lambda real=real: real), \
                    mock.patch.object(excel, "new_export_id", lambda: FIXED_ID), \
                    mock.patch("time.time", lambda real=real: real.timestamp()), \
                    mock.patch("time.localtime", lambda t=None, real=real: real.timetuple()):
                path = self.dir / f"{len(out)}.xlsx"
                excel.export(path, "DEMO", rows, self.dir / f"state{len(out)}.json", on=ON)
                out.append(path.read_bytes())
        self.assertEqual(out[0], out[1])
        self.assertEqual(out[0], out[2])
        with zipfile.ZipFile(self.dir / "0.xlsx") as z:
            self.assertEqual({i.date_time for i in z.infolist()}, {(1980, 1, 1, 0, 0, 0)})
            self.assertEqual(z.namelist(), sorted(z.namelist()))
            core = z.read("docProps/core.xml").decode("utf-8")
        self.assertEqual(core.count("2030-06-01T00:00:00"), 2)                 # created and modified, not the real time
        self.assertIn("<dc:creator>clark</dc:creator>", core)
        self.assertEqual(excel.read_workbook(self.dir / "0.xlsx")["actions"][0]["description"], "Book the room")

    def test_without_on_the_clock_decides_the_stamp(self):
        rows = self.rows(description="x")
        with mock.patch.object(excel, "clock", lambda: datetime(2031, 2, 3, 4, 5, 6, 789)):
            excel.export(self.dir / "a.xlsx", "DEMO", rows, self.dir / "s.json")
        with zipfile.ZipFile(self.dir / "a.xlsx") as z:
            self.assertIn("2031-02-03T04:05:06", z.read("docProps/core.xml").decode("utf-8"))
        self.assertEqual(json.loads((self.dir / "s.json").read_text(encoding="utf-8"))["workbooks"][excel._key(self.dir / "a.xlsx")]
                         ["exported_at"], "2031-02-03 04:05:06")

    def test_the_workbook_says_it_is_internal(self):
        path = self.dir / "DEMO.xlsx"
        excel.export(path, "DEMO", self.rows(description="x"), self.dir / "state.json", on=ON)
        wb = load_workbook(path)
        self.assertIn("Never share it with a client", wb.properties.description)
        self.assertIn("Never share it with a client", wb["Milestones"]["A1"].comment.text)
        self.assertEqual(wb["Milestones"]["A1"].value, "ID")                    # the header itself is unchanged

    def test_empty_tables_are_empty_sheets(self):
        path = self.dir / "DEMO.xlsx"
        excel.export(path, "DEMO", {}, self.dir / "state.json")
        self.assertEqual(excel.read_workbook(path), {t: [] for t in excel.TABLES})


if __name__ == "__main__":
    unittest.main()


class HistorySheetTests(unittest.TestCase):
    """#123: the History sheet is history.view_for_project's rows and nothing else; read-only text; the import ignores it."""

    def setUp(self):
        self.d = Demo()

    def tearDown(self):
        self.d.close()

    def view(self, limit=history.ROW_LIMIT):
        return history.view_for_project(self.d.store.con, "ABC", "all", limit)

    def sheet(self):
        self.d.export()
        return load_workbook(self.d.path)["History"]

    def test_sheet_is_after_the_data_sheets_before_lists(self):
        names = load_workbook(self.d.path if self.d.export() else None).sheetnames
        self.assertEqual(names[-3:], ["Use cases", "History", "Lists"])

    def test_headers_note_and_frozen_header(self):
        ws = self.sheet()
        self.assertEqual([c.value for c in ws[2]], ["When", "Who", "How", "Item", "Field", "From", "To"])
        self.assertEqual(ws.freeze_panes, "A3")
        self.assertIn("Do not send it to a client.", ws["A1"].value)
        self.assertIn(self.view()["footnote"], ws["A1"].value)
        self.assertEqual(ws["F3"].alignment.wrap_text, True)
        self.assertEqual(ws["G3"].alignment.wrap_text, True)

    def test_rows_equal_view_for_project_cell_for_cell(self):
        ws = self.sheet()
        rows = self.view()["rows"]
        self.assertTrue(rows)
        keys = ("when_text", "who", "how", "item", "field", "from", "to")
        got = [[c.value for c in r] for r in ws.iter_rows(min_row=3, max_col=7)]
        self.assertEqual(got, [[r[k] if r[k] != "" else None for k in keys] for r in rows])

    def test_rich_text_is_words_in_every_history_cell(self):
        """Review of #189: where things stand and a use case's standing are HTML in the store; the sheet shows their words."""
        self.d.demo.update("projects", "ABC", {"current_state": "<p>Build is <strong>on track</strong> &amp; tested</p>"})
        self.d.demo.update("projects", "ABC", {"current_state": "<p>Build is <strong>late</strong> &amp; tested</p>"})
        cells = [c.value for r in self.sheet().iter_rows(min_row=3, max_col=7) for c in r if c.value]
        for text in cells:
            self.assertNotIn("<p>", text)
            self.assertNotIn("<strong>", text)
            self.assertNotIn("&amp;", text)
        self.assertIn("Build is on track & tested", cells)       # the first fill from empty, as words
        self.assertIn("Build is late & tested", cells)

    def test_limit_and_closing_line(self):
        total = len(self.view()["rows"])
        self.assertGreater(total, 3)
        with mock.patch.object(history, "ROW_LIMIT", 3):
            ws = self.sheet()
        self.assertEqual(ws.max_row, 2 + 3 + 1)
        self.assertEqual(ws.cell(row=6, column=1).value, history.CLOSING_LINE)
        self.assertEqual([c.value for c in ws[3]][:3], [self.view(3)["rows"][0][k] for k in ("when_text", "who", "how")])

    def test_no_closing_line_when_nothing_is_cut(self):
        ws = self.sheet()
        self.assertEqual(ws.max_row, 2 + len(self.view()["rows"]))

    def test_empty_state(self):
        wb = excel.workbook("ABC", {}, history=history.view_for_project(self.d.store.con, "NONE", "all", history.ROW_LIMIT))
        ws = wb["History"]
        self.assertEqual(ws.max_row, 3)
        self.assertEqual(ws["A3"].value, history.EMPTY["all"])

    def test_every_cell_is_the_looks_office_font_text(self):
        ws = self.sheet()
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    self.assertEqual(c.font.name, look.office_font(), c.coordinate)
                    self.assertEqual(c.data_type, "s", c.coordinate)

    def test_formula_text_is_not_a_formula(self):
        with self.d.store.step("dashboard", USER) as st:
            st.update("actions", self.d.action, {"latest_update": "=1+1"})
        ws = self.sheet()
        cells = [c for row in ws.iter_rows() for c in row if c.value == "=1+1"]
        self.assertTrue(cells)
        self.assertTrue(all(c.data_type == "s" for c in cells))
        with zipfile.ZipFile(self.d.path) as z:
            xml = [z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/")]
        self.assertFalse(any("<f>" in x or "<f " in x for x in xml))

    def test_long_cell_is_cut(self):
        with self.d.store.step("dashboard", USER) as st:
            st.update("actions", self.d.action, {"latest_update": "x" * 6000})
        ws = self.sheet()
        longest = max(len(c.value) for row in ws.iter_rows(min_row=3) for c in row if c.value)
        self.assertEqual(longest, excel.HISTORY_CELL_LIMIT)

    def test_import_ignores_the_history_sheet(self):
        self.d.export()
        plan = xi.read_workbook(self.d.store, self.d.path, "ABC", state_path=self.d.state)
        self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [])
        self.assertNotIn("history", xi.SHEET_TABLES)
        wb = load_workbook(self.d.path)
        for row in wb["History"].iter_rows(min_row=3):       # doctor it: still no change
            row[6].value = "doctored"
        wb.save(self.d.path)
        plan = xi.read_workbook(self.d.store, self.d.path, "ABC", state_path=self.d.state)
        self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [])
