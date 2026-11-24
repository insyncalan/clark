"""Item 1390, the ticket's DoD6 and DoD7 under the names the ticket gives them, plus the Help words of the Report sheet.

Both DoD tests check behaviour that already exists (the alias tables and the Milestones columns); the longer cases are in
tests/test_excel_old_headings_1390.py, whose helper writes the old headings over a fresh export. Fictional data only.

Run: python3 dev/run_tests.py test_excel_redesign_1390_b2
"""
import json
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import DemoStore
from openpyxl import load_workbook

from clark import excel
from clark import excel_client
from clark import excel_cover as cover
from clark import page
from clark import excel_import as xi
from test_excel_old_headings_1390 import OLD, make_old
from test_excel_roundtrip import RoundTrip, edit, setUpModule, tearDownModule  # noqa: F401  (the hooks keep a brand logo out of every test)

HELP = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"

DATA_CARD = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "logic" / "dataCard.js"
ACCEPTED = ("Title", "Client visible", "Added from", "Last updated", "Decided on", "Options considered", "State", "Progress %",
            "Sort order", "Reference", "On the dashboard")
OLD_NAMES = ("Client-visible", "Source", "Updated", "Date", "Options", "% complete", "Order", "On dashboard", "Shown state", "State set by you")


class AcceptedHeadings(unittest.TestCase):
    def test_headings_are_the_accepted_ones(self):
        """DoD5: the accepted headings are in excel.py, excel_client.py, dataCard.js and helpContent.json, and no old name is a heading."""
        sheets = {name: [label for label, _ in cols] for name, _, cols, _ in excel.SHEETS}
        client = {t: [h for h, _, _ in cols] for t, cols in excel_client.COLUMNS.items()}
        block = re.search(r"export const IMPORT_COLUMNS = \[(.*?)\n\];", DATA_CARD.read_text(encoding="utf8"), re.S).group(1)
        card = {m.group(1): json.loads(m.group(2)) for m in re.finditer(r'\["([^"]+)", (\[.*?\])\]', block)}
        self.assertEqual(len(card), 5)
        help_text = HELP.read_text(encoding="utf8")
        everywhere = [h for hs in sheets.values() for h in hs] + [h for hs in client.values() for h in hs] + [h for hs in card.values() for h in hs]
        for name in ACCEPTED:
            self.assertIn(name, [h for hs in sheets.values() for h in hs], f"{name} missing from excel.py")
            self.assertIn(name, help_text, f"{name} missing from helpContent.json")
        for name in ("Title", "Decided on", "State", "Progress %", "Reference"):
            self.assertIn(name, [h for hs in client.values() for h in hs], f"{name} missing from excel_client.py")
        for name in ("Title", "Client visible", "Decided on", "Options considered", "Progress %", "Sort order", "Reference", "On the dashboard"):
            self.assertIn(name, [h for hs in card.values() for h in hs], f"{name} missing from dataCard.js")
        for old in OLD_NAMES:
            self.assertNotIn(old, everywhere, f"the old heading {old} is still a column")
        for table in (sheets, client, card):
            for name in ("Actions", "Risks & Issues"):
                if name in table:
                    self.assertNotIn("Description", table[name], name)
        # the same label per field in the editor export and the import card
        self.assertEqual(sheets["Decisions"][sheets["Decisions"].index("Decided on")], card["Decisions"][card["Decisions"].index("Decided on")])
        self.assertEqual(sheets["Use cases"][sheets["Use cases"].index("On the dashboard")], "On the dashboard")
        for name in ("Actions", "Risks & Issues", "Decisions", "Milestones", "Use cases"):
            self.assertEqual([h for h in card[name] if h in sheets[name]], card[name], f"dataCard.js lists a heading {name} does not export")


class OldHeadingWorkbook(RoundTrip):
    def setUp(self):
        super().setUp()
        make_old(self.path)

    def test_old_heading_workbook_still_imports(self):
        """DoD6: a workbook with every old heading is read with no change and no problem, and an edit made under an old name lands."""
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))
        edit(self.path, "Actions", self.a1, Description="Old file, reworded", **{"Client-visible": "No"})
        p = self.read()
        self.assertEqual(p.problems, [])
        after = {c.table: c.after for c in p.changes}
        self.assertEqual(after["actions"], {"description": "Old file, reworded", "client_visible": 0})


class MilestoneStateColumns(RoundTrip):
    def test_milestones_state_columns_are_gone(self):
        """DoD7: the export writes one State column and not State set by you or Shown state, and the import does not read them."""
        labels = [c.value for c in load_workbook(str(self.path))["Milestones"][1]]
        self.assertEqual(labels.count("State"), 1, labels)
        for gone in ("State set by you", "Shown state", "State chosen", "Chosen by you"):
            self.assertNotIn(gone, labels)
        before = {r["id"]: (r["state"], r["state_set"]) for r in self.s.read("milestones", "ABC")}
        make_old(self.path)      # puts the two old state columns back, with a state that differs
        p = self.read()
        self.assertEqual([c for c in p.changes if c.table == "milestones"], [])
        for old in ("State set by you", "State chosen", "Chosen by you"):
            self.assertIn(xi._key(old), xi.OLD_STATE_COLUMNS, old)
        self.assertEqual(before, {r["id"]: (r["state"], r["state_set"]) for r in self.s.read("milestones", "ABC")})


class HelpSaysReport(unittest.TestCase):
    def test_no_help_text_calls_the_first_sheet_the_cover(self):
        """The first sheet is the Report (excel.REPORT_NAME); Help says so in the approved words and never says Cover."""
        text = HELP.read_text(encoding="utf8")
        self.assertEqual(excel.REPORT_NAME, "Report")
        self.assertNotIn("Cover", text)
        self.assertIn("It opens on the Report sheet: a title band with the project name, tagged INTERNAL, and under it the same line "
                      "the Dashboard header shows (with Shown as at and the date when the report is shown as at a day).", text)
        self.assertIn("After the Report come the sheets of rows", text)
        self.assertIn("Changes made on the Report are ignored.", text)
        json.loads(text)


if __name__ == "__main__":
    unittest.main()


class ReportSheetFollowsTheDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old, page.BRANDING = page.BRANDING, Path(tempfile.mkdtemp(prefix="clark-no-brand-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(page.BRANDING, ignore_errors=True)
        page.BRANDING = cls._old

    def test_report_sheet_follows_the_dashboard(self):
        """DoD8: the Report sheet carries the Dashboard header line, the Report headline words in the Dashboard order, and Shown as at only for an as-at day.
        (The Documents sheet is DoD8's other half, test_documents_sheet_lists_the_documents, and is not here.)"""
        demo = DemoStore()
        self.addCleanup(demo.close)
        tmp = Path(tempfile.mkdtemp(prefix="clark-redesign-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        body = {"v": 1, "health": "at_risk", "headline": "Go live moves one week", "sentence": "The vendor test slipped to Friday."}
        con = sqlite3.connect(demo.store.path)
        con.execute("UPDATE projects SET week_ending = '2030-05-31' WHERE code = 'ABC'")
        con.execute("DELETE FROM report_sections WHERE project = 'ABC'")
        con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES "
                    "('ABC','a','current','Current state','',0,0,1), ('ABC','h','reportheadline','',?,0,0,2), "
                    "('ABC','b','glance','At a glance','',0,0,3)", (json.dumps(body),))
        con.commit()
        con.close()

        def export(**kw):
            path = tmp / "w.xlsx"
            excel.export_project(demo.store, "ABC", path, tmp / "state.json", on="2030-06-01", **kw)
            return load_workbook(path)["Report"]

        ws = export()
        self.assertEqual(ws["A2"].value, "Weekly report \u00b7 Week ending 31-05-2030")
        self.assertEqual(ws["A2"].value, cover.subtitle({"week_ending": "2030-05-31"}))
        column = [str(c.value) for c in ws["A"] if c.value is not None]
        self.assertFalse([v for v in column if v.startswith(cover.AS_AT)])
        self.assertIn("At risk \u00b7 Go live moves one week", column)
        self.assertIn("The vendor test slipped to Friday.", column)
        self.assertLess(column.index("\u25a0  Report headline"), column.index("The vendor test slipped to Friday."))
        self.assertEqual(export(as_at="2030-05-20")["A3"].value, "Shown as at 20-05-2030")


class HistorySheetHidden(RoundTrip):
    def test_the_report_sheet_says_how_to_unhide_the_history_1390(self):
        """1390: the editor workbook's Report sheet carries the approved sentence exactly; the client export (no History) does not."""
        sentence = "The History sheet is hidden: right-click any sheet tab and choose Unhide."
        wb = load_workbook(self.path)
        report = [str(c.value) for row in wb[excel.REPORT_NAME].iter_rows() for c in row if c.value is not None]
        self.assertIn(sentence, report)
        self.assertEqual(sentence, cover.HISTORY_HIDDEN)
        import io
        import _publish_fixture as fx
        from clark import publish
        client = load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(fx.inputs(fx.load())))))
        texts = [str(c.value) for ws in client.worksheets for row in ws.iter_rows() for c in row if c.value is not None]
        self.assertNotIn(sentence, texts)
        self.assertFalse([t for t in texts if "Unhide" in t])

    def test_history_sheet_is_hidden_not_very_hidden_1390(self):
        """1390 DoD 'History hidden': the editor export's History sheet is plain hidden (Unhide shows it), a visible sheet is
        active, and the import still reads the workbook with its hidden History."""
        wb = load_workbook(self.path)
        self.assertEqual(wb[excel.HISTORY_NAME].sheet_state, "hidden")
        self.assertEqual(wb.active.sheet_state, "visible")
        self.assertNotEqual(wb.active.title, excel.HISTORY_NAME)
        edit(self.path, "Actions", self.a1, Owner="Sam Example")
        p = self.read()
        self.assertEqual(p.problems, [])
        self.assertEqual({c.table: c.after for c in p.changes}["actions"], {"owner": "Sam Example"})
