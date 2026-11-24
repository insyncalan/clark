"""Row 1390, slice 7: the Report sheet's frame (the Cover renamed and drawn as the mock-up shows it). Not UI: every check opens the
produced .xlsx with openpyxl. Fictional data only.

Run: python3 dev/run_tests.py test_excel_report_1390s7
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import DemoStore
from openpyxl import load_workbook

from clark import excel
from clark import excel_colours as colours
from clark import excel_cover as cover
from clark import page, secret_screen

ON = "2030-06-01"
FORMULA_STARTS = ("=1+1", "+1", "-1", "@SUM(1)", "\t=1", "\r=1")


class ReportSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old, page.BRANDING = page.BRANDING, Path(tempfile.mkdtemp(prefix="clark-no-brand-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(page.BRANDING, ignore_errors=True)
        page.BRANDING = cls._old

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-report-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path, self.state = self.dir / "ABC.xlsx", self.dir / "state.json"
        self.demo.action(description="One action", due_date="2030-01-01")
        for kind, status in (("Risk", "Open"), ("Risk", "Open"), ("Issue", "Open"), ("Assumption", "Closed"), ("Dependency", "Cancelled")):
            with self.demo.store.step("dashboard", "Demo User") as st:
                st.create("raid", {"project": "ABC", "type": kind, "description": f"A {kind}", "status": status, "raised": "2020-01-01", "source": "demo"})
        self.set_project("Example Client", "2030-05-31")

    def set_project(self, client, week, state="<p>Phase two.</p>"):
        con = sqlite3.connect(self.demo.store.path)
        con.execute("UPDATE projects SET client_name = ?, week_ending = ?, current_state = ? WHERE code = 'ABC'", (client, week, state))
        con.execute("DELETE FROM report_sections WHERE project = 'ABC'")
        con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES "
                    "('ABC','a','current','Current state','',0,0,1), ('ABC','b','glance','At a glance','',0,0,2), "
                    "('ABC','m','milestones','Milestones','',0,0,20), ('ABC','n','raid','Risks','',0,0,21), "
                    "('ABC','o','actions','Actions','',0,0,22), ('ABC','p','decisions','Decisions','',0,0,23), "
                    "('ABC','q','usecases','Use cases','',0,0,24)")
        con.commit()
        con.close()

    def export(self, **kw):
        excel.export_project(self.demo.store, "ABC", self.path, self.state, on=ON, exported_by="Sam Example", **kw)
        return load_workbook(self.path)

    def test_the_first_sheet_is_the_report_and_no_cover_is_left(self):
        wb = self.export()
        self.assertEqual(wb.sheetnames[0], "Report")
        self.assertEqual(wb.active.title, "Report")
        self.assertNotIn("Cover", wb.sheetnames)
        self.assertEqual(excel.REPORT_NAME, "Report")

    def test_a_gantt_tab_may_not_take_the_name_report_or_the_old_cover(self):
        self.assertEqual(excel.gantt_sheet_name("Report"), "Gantt")
        self.assertEqual(excel.gantt_sheet_name("Cover"), "Gantt")
        self.assertEqual(excel.gantt_sheet_name("Plan"), "Plan")

    def test_the_subtitle_is_exactly_the_dashboard_header_and_never_names_the_client(self):
        ws = self.export()["Report"]
        self.assertEqual(ws["A2"].value, "Weekly report · Week ending 31-05-2030")
        every = "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
        self.assertNotIn("Example Client", every)
        self.assertNotIn("for ", ws["A2"].value)
        self.assertEqual(ws.freeze_panes, "A3", "the band (title and subtitle) stays when the sheet scrolls")

    def test_shown_as_at_is_one_line_under_the_band_only_when_an_as_at_day_is_used(self):
        ws = self.export()["Report"]
        self.assertFalse([c for c in ws["A"] if c.value and str(c.value).startswith("Shown as at")])
        ws = self.export(as_at="2030-05-20")["Report"]
        self.assertEqual(ws["A3"].value, "Shown as at 20-05-2030")
        self.assertTrue(ws["A3"].font.b)

    def test_the_sections_with_a_sheet_are_links_inside_the_workbook_to_each_sheets_a1(self):
        wb = self.export()
        ws = wb["Report"]
        head = next(c for c in ws["A"] if c.value == "■  " + cover.SHEETS_HEADING)
        got = {}
        for r in range(head.row + 2, head.row + 9):
            label, link = ws.cell(row=r, column=1).value, ws.cell(row=r, column=7)
            if not label:
                break
            got[label] = (link.value, link.hyperlink.location, link.hyperlink.target)
        self.assertEqual(got, {"Use cases": ("Use cases sheet", "'Use cases'!A1", None), "Milestones": ("Milestones sheet", "'Milestones'!A1", None),
                               "Risks and issues": ("Risks & Issues sheet", "'Risks & Issues'!A1", None),
                               "Actions": ("Actions sheet", "'Actions'!A1", None), "Decisions": ("Decisions sheet", "'Decisions'!A1", None)})
        for _, (_, loc, _) in got.items():
            self.assertIn(loc.split("!")[0].strip("'"), wb.sheetnames)
        self.assertEqual((ws.cell(row=head.row + 1, column=1).value, ws.cell(row=head.row + 1, column=7).value),
                         ("Dashboard section", "Where in this workbook"))

    def test_a_gantt_sheet_is_listed_under_its_own_tab_name_and_only_when_it_exists(self):
        self.assertNotIn("Gantt", [c.value for c in self.export()["Report"]["A"]])
        self.assertEqual(excel.sheet_links(["Report", "Actions", "Plan x"], "Plan x"), [("Actions", "Actions"), ("Gantt", "Plan x")])
        self.assertEqual(excel.sheet_links(["Report"], None), [])
        self.assertEqual(excel.sheet_links(["Report", "Gantt"], None), [])        # no name given for the Gantt tab: it is not guessed

    def test_open_risks_and_issues_are_counted_by_type_in_name_order(self):
        ws = self.export()["Report"]
        head = next(c for c in ws["A"] if c.value == "■  " + cover.COUNTS_HEADING)
        chips = [ws.cell(row=head.row + 1, column=c).value for c in range(1, 13) if ws.cell(row=head.row + 1, column=c).value]
        self.assertEqual(chips, ["Issue: 1", "Risk: 2"], "closed and cancelled items are not open; a type with none is left out")
        self.assertEqual(ws.cell(row=head.row + 1, column=1).fill.fgColor.rgb[-6:], colours.TOKENS["grey-50"])

    def heading_row(self, ws, words):
        return next(c.row for c in ws["A"] if c.value is not None and str(c.value) == "■  " + words)

    def test_the_as_at_line_is_20_points_high(self):
        self.assertEqual(self.export(as_at="2030-05-20")["Report"].row_dimensions[3].height, 20)

    def test_the_counts_and_sheets_blocks_have_one_8_point_spacer_row_above_their_heading_and_20_point_rows_below(self):
        ws = self.export()["Report"]
        for words in (cover.COUNTS_HEADING, cover.SHEETS_HEADING):
            with self.subTest(words=words):
                head = self.heading_row(ws, words)
                self.assertEqual(ws.row_dimensions[head - 1].height, 8, "the spacer row")
                self.assertIsNone(ws.cell(row=head - 1, column=1).value)
                self.assertTrue(any(c.value for c in ws[head - 2]), "only one spacer row between the blocks")
                self.assertEqual(ws.row_dimensions[head + 1].height, 20, "the chip row / the table's header row")

    def test_at_most_six_type_chips_are_drawn_two_columns_each(self):
        lines = cover.lines({"name": "n"}, [], [], "stamp", counts=[(f"T{i}", i + 1) for i in range(9)])
        ws = excel.workbook("ABC", {}, cover=lines)["Report"]
        head = self.heading_row(ws, cover.COUNTS_HEADING)
        chips = [ws.cell(row=head + 1, column=c).value for c in range(1, excel.COVER_COLUMNS + 1) if ws.cell(row=head + 1, column=c).value]
        self.assertEqual(chips, [f"T{i}: {i + 1}" for i in range(excel.COVER_COLUMNS // 2)])
        self.assertEqual(len(chips), 6)

    def test_no_open_risks_means_no_counts_line(self):
        self.assertEqual(cover.raid_counts({"data": {"raid": [{"type": "Risk", "status": "Closed"}]}}), [])
        self.assertEqual(cover.raid_counts({"data": {}}), [])
        self.assertEqual(cover.raid_counts({"data": {"raid": [{"type": "Risk", "status": "Open"}, {"type": " ", "status": "Open"}]}}), [("Risk", 1)])

    def test_the_colour_key_paints_each_chip_with_the_colour_the_sheets_use_and_one_locked_cell(self):
        wb = self.export()
        ws = wb["Report"]
        head = next(c for c in ws["A"] if c.value == "■  " + cover.COLOUR_KEY_HEADING)
        pri, status, locked = (ws.cell(row=head.row + i, column=1).value for i in (1, 2, 3))
        self.assertEqual((pri, status, locked), ("Priority (Risks & Issues)", "Status (Actions)", "Locked cell"))
        for r, table in ((head.row + 1, colours.PRIORITY), (head.row + 2, colours.ACTION_STATUS)):
            for i, (word, colour) in enumerate(table.items()):
                cell = ws.cell(row=r, column=3 + 2 * i)
                fill, pen = colours.hexes(colour)
                self.assertEqual((cell.value, cell.fill.fgColor.rgb[-6:], cell.font.color.rgb[-6:]), (word, fill, pen))
        lock = ws.cell(row=head.row + 3, column=3)
        self.assertEqual(lock.fill.fgColor.rgb[-6:], wb["Actions"]["A2"].fill.fgColor.rgb[-6:], "the key's locked cell is the colour of a locked data cell")

    def test_where_to_edit_says_report_sheet_and_the_import_still_ignores_it(self):
        self.assertTrue(cover.WHERE_TO_EDIT.endswith("Changes made on this Report sheet are ignored."))
        ws = self.export()["Report"]
        self.assertIn(cover.WHERE_TO_EDIT, [c.value for row in ws.iter_rows() for c in row])

    def test_formula_start_text_in_the_project_fields_is_neutralised_on_the_report(self):
        for start in FORMULA_STARTS:
            with self.subTest(start=repr(start)):
                self.set_project(start + "client", "2030-05-31", state=f"<p>{start.strip()}1 phase</p>")
                ws = self.export()["Report"]
                for row in ws.iter_rows():
                    for c in row:
                        self.assertNotEqual(c.data_type, "f", c.coordinate)
                        if c.value is not None:
                            self.assertIn(c.data_type, ("s", "inlineStr"), c.coordinate)

    def test_a_raid_type_that_starts_with_a_formula_character_is_text_in_its_chip(self):
        for start in FORMULA_STARTS:
            with self.subTest(start=repr(start)):
                lines = cover.lines({"name": "n"}, [], [], "stamp", counts=[(start + "T", 2)])
                ws = excel.workbook("ABC", {}, cover=lines)["Report"]
                chip = next(c for row in ws.iter_rows() for c in row if c.value and "T: 2" in str(c.value))
                self.assertIn(chip.data_type, ("s", "inlineStr"))

    def test_the_export_does_not_call_the_secret_screen_and_leaves_it_as_it_is(self):
        for module in (excel, cover):
            self.assertFalse(hasattr(module, "secret_screen"), module.__name__)
        self.assertTrue(secret_screen.looks_like_secret("pass" + "word=" + "hunter2" * 3))
        self.assertFalse(secret_screen.looks_like_secret("Weekly report"))


if __name__ == "__main__":
    unittest.main()
