"""Mutation sweep of src/clark/excel_client.py (the client-view workbook): the pins the existing files did not hold.

Each test names the change to excel_client.py that it catches. Fictional data only (the publish plant).

Run: python3 dev/run_tests.py test_excel_client_mutwave
"""
import io
import unittest
import zipfile
from unittest import mock

from _paths import ROOT, SRC, TOOLS  # noqa: F401

import _publish_fixture as fx  # noqa: E402
from openpyxl import Workbook, load_workbook  # noqa: E402
from clark import excel, excel_client, platform, publish  # noqa: E402
from test_gantt_excel_export import plant as gantt_plant, selected as gantt_selected  # noqa: E402


def published():
    return publish.select(fx.inputs(fx.load()))


def sheet_of(pub, table):
    wb = Workbook()
    wb.remove(wb.active)
    return excel_client.write_sheet(wb, pub, table)


def loaded(pub):
    return load_workbook(io.BytesIO(excel_client.workbook_bytes(pub)))


class SizeLimit(unittest.TestCase):
    def test_the_cap_is_one_and_a_half_million_bytes(self):
        self.assertEqual(excel_client.MAX_WORKBOOK_BYTES, 1_500_000)

    def test_a_workbook_exactly_at_the_cap_is_kept_and_one_over_is_not(self):
        pub = published()
        size = len(excel_client.workbook_bytes(pub))
        with mock.patch.object(excel_client, "MAX_WORKBOOK_BYTES", size):
            self.assertIn("client_workbook", excel_client.embed(pub))
        with mock.patch.object(excel_client, "MAX_WORKBOOK_BYTES", size - 1):
            self.assertEqual(excel_client.embed(pub), {"client_workbook_too_large": True})


class Rows(unittest.TestCase):
    def test_a_cancelled_milestone_is_left_out_and_a_cancelled_row_of_another_table_is_not(self):
        pub = {"data": {"milestones": [{"id": "M1", "status": "Cancelled"}, {"id": "M2", "status": "Open"}],
                        "decisions": [{"id": "D1", "status": "Cancelled"}]}}
        self.assertEqual([r["id"] for r in excel_client.rows_of(pub, "milestones")], ["M2"])
        self.assertEqual([r["id"] for r in excel_client.rows_of(pub, "decisions")], ["D1"])
        self.assertEqual(excel_client.rows_of({"data": {}}, "actions"), [])

    def test_only_a_milestone_with_the_status_cancelled_is_dropped(self):
        pub = {"data": {"milestones": [{"id": "M1", "status": "cancelled"}]}}
        self.assertEqual(len(excel_client.rows_of(pub, "milestones")), 1)


class Words(unittest.TestCase):
    def test_client_wording_is_trimmed_and_blank_wording_falls_back_to_the_own_text(self):
        self.assertEqual(excel_client.value_of("actions", {"client_message": "  Said  ", "description": "Own"}, "_words"), "Said")
        self.assertEqual(excel_client.value_of("actions", {"client_message": "   ", "description": "Own"}, "_words"), "Own")

    def test_rich_text_is_shown_as_its_plain_text(self):
        html = "<p>A &amp; B &lt;c&gt;</p><script>ZQ-SCRIPT()</script><p>D</p>"
        self.assertEqual(excel_client.value_of("use_cases", {"standing": html}, "standing"), "A & B <c>\nD")

    def test_plain_text_has_no_outer_blank_lines_and_collapses_long_gaps(self):
        self.assertEqual(excel_client.plain("<p>A</p>"), "A")
        self.assertEqual(excel_client.plain("<p>A</p><p></p><p></p><p>B</p>"), "A\n\nB")
        self.assertEqual(excel_client.plain("<p>A</p><p></p><p>B</p>"), "A\n\nB")
        self.assertEqual(excel_client.plain('<p onclick="x()">hi</p><script>ZQ-SCRIPT()</script>'), "hi")
        self.assertEqual(excel_client.plain(None), "")

    def test_a_legacy_rich_field_is_shown_as_text(self):
        self.assertIn(("actions", "latest_update"), excel_client.LEGACY_RICH)
        self.assertEqual(excel_client.value_of("actions", {"latest_update": "<p>Hi &amp; there</p>"}, "latest_update"), "Hi & there")


class Title(unittest.TestCase):
    def test_the_sub_title_without_a_week_is_the_published_day(self):
        pub = {"as_at": "2026-10-01", "data": {"project": {"name": "N", "code": "C"}}}
        self.assertEqual(excel_client.title_text(pub), ("N", "As at 2026-10-01"))

    def test_the_title_falls_back_to_the_code_then_to_nothing(self):
        self.assertEqual(excel_client.title_text({"as_at": "2026-10-01", "data": {"project": {"code": "C"}}})[0], "C")
        self.assertEqual(excel_client.title_text({"as_at": "2026-10-01", "data": {}})[0], "")

    def test_file_name_falls_back_to_report_and_the_published_day(self):
        self.assertEqual(excel_client.file_name({"as_at": "2026-10-01", "data": {"project": {}}}), "report-report-2026-10-01.xlsx")
        self.assertEqual(excel_client.file_name({"as_at": "2026-10-01", "data": {"project": {"code": "PUB", "week_ending": "2026-10-23"}}}),
                         "PUB-report-2026-10-23.xlsx")
        self.assertEqual(excel_client.file_name({"as_at": "2026-10-01", "data": {"project": {"code": "PUB"}}}), "PUB-report-2026-10-01.xlsx")

    def test_a_name_the_page_would_refuse_becomes_report_xlsx(self):
        pub = published()
        for bad in ("a/b.xlsx", "x" * 121, ""):
            with mock.patch.object(excel_client, "file_name", return_value=bad):
                self.assertEqual(excel_client.embed(pub)["client_workbook"]["name"], "report.xlsx", bad[:10])
        good = "x" * 115 + ".xlsx"
        with mock.patch.object(excel_client, "file_name", return_value=good):
            self.assertEqual(excel_client.embed(pub)["client_workbook"]["name"], good)

    def test_the_base64_has_no_line_break(self):
        self.assertNotIn("\n", excel_client.embed(published())["client_workbook"]["base64"])

    def test_the_title_property_is_the_cleaned_name_and_the_stamp_is_midnight_of_the_published_day(self):
        pub = published()
        pub["data"]["project"]["name"] = "Alpha\x0bBeta"
        data = excel_client.workbook_bytes(pub)
        self.assertEqual(load_workbook(io.BytesIO(data)).properties.title, "Alpha Beta")
        core = zipfile.ZipFile(io.BytesIO(data)).read("docProps/core.xml").decode("utf-8")
        for tag in ("created", "modified"):
            self.assertRegex(core, r"<dcterms:%s[^>]*>%sT00:00:00" % (tag, pub["as_at"]))


class Columns(unittest.TestCase):
    def heads(self, table):
        return [c[0] for c in excel_client.columns(table)]

    def test_a_field_the_file_does_not_carry_has_no_column(self):
        fields = {**publish.PUBLISH_FIELDS, "actions": tuple(f for f in publish.PUBLISH_FIELDS["actions"] if f != "owner")}
        with mock.patch.object(publish, "PUBLISH_FIELDS", fields):
            self.assertNotIn("Owner", self.heads("actions"))
        self.assertIn("Owner", self.heads("actions"))

    def test_the_flag_column_sits_after_status_and_only_on_use_cases(self):
        fields = {t: tuple(f) + ("commitment",) for t, f in publish.PUBLISH_FIELDS.items()}
        with mock.patch.object(publish, "PUBLISH_FIELDS", fields):
            heads = self.heads("use_cases")
            self.assertEqual(heads.index("Commitment"), heads.index("Status") + 1)
            for table in ("actions", "raid", "decisions", "milestones"):
                self.assertNotIn("Commitment", self.heads(table))


class SheetLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub = published()
        cls.wb = loaded(cls.pub)

    def test_widths_follow_the_column_table(self):
        for table in excel_client.sheet_tables(self.pub):
            ws = self.wb[excel.SHEET_OF[table]]
            for i, (_, _, width) in enumerate(excel_client.columns(table), start=1):
                self.assertEqual(ws.column_dimensions[ws.cell(4, i).column_letter].width, width, (table, i))

    def test_the_heading_row_is_frozen_under_the_headings(self):
        for table in excel_client.sheet_tables(self.pub):
            self.assertEqual(self.wb[excel.SHEET_OF[table]].freeze_panes, "A5", table)

    def test_title_band_fonts(self):
        ws = self.wb["Actions"]
        self.assertEqual((ws["A1"].font.sz, ws["A1"].font.b), (16, True))
        self.assertEqual(ws["A2"].font.sz, 11)
        self.assertFalse(ws["A2"].font.b)
        self.assertTrue(ws["A4"].font.b)
        self.assertEqual(ws["A4"].font.color.rgb[-6:], excel_client.PALETTE["text"].lstrip("#")[-6:])

    def test_the_palette_of_a_call_is_used(self):
        pal = {"fill": "112233", "text": "FFEEDD"}
        ws = load_workbook(io.BytesIO(excel_client.workbook_bytes(self.pub, pal)))["Actions"]
        self.assertEqual(ws["A1"].fill.fgColor.rgb[-6:], "112233")
        self.assertEqual(ws["A4"].font.color.rgb[-6:], "FFEEDD")
        got = load_workbook(io.BytesIO(__import__("base64").b64decode(excel_client.embed(self.pub, pal)["client_workbook"]["base64"])))["Actions"]
        self.assertEqual(got["A1"].fill.fgColor.rgb[-6:], "112233", "embed passes the palette on")

    def test_data_cells_start_at_row_five_and_are_top_aligned(self):
        ws = self.wb["Actions"]
        self.assertTrue(ws.cell(5, 1).value)
        self.assertEqual(ws.cell(4, 1).value, "ID")
        self.assertEqual(ws.cell(5, 2).alignment.vertical, "top")

    def test_a_blank_text_is_an_empty_cell(self):
        pub = published()
        pub["data"]["actions"][0]["owner"] = ""
        ws = sheet_of(pub, "actions")
        owner = [h for h, f, _ in excel_client.columns("actions")].index("Owner") + 1
        self.assertIsNone(ws.cell(5, owner).value)

    def test_dates_are_dates_left_aligned_and_top(self):
        pub = published()
        pub["data"]["decisions"][0]["revisit"] = "2026-10-05"
        ws = sheet_of(pub, "decisions")
        col = [c[0] for c in excel_client.columns("decisions")].index("Revisit") + 1
        cell = ws.cell(5, col)
        self.assertNotIsInstance(cell.value, str)
        self.assertEqual(cell.number_format, excel.DATE_FORMAT)
        self.assertEqual((cell.alignment.horizontal, cell.alignment.vertical), ("left", "top"))
        for table in ("actions", "milestones"):
            w = sheet_of(pub, table)
            for i, (_, f, _) in enumerate(excel_client.columns(table), start=1):
                if f in excel_client.DATE_FIELDS and w.cell(5, i).value is not None:
                    self.assertEqual(w.cell(5, i).alignment.vertical, "top", (table, f))

    def test_the_shown_state_column_follows_the_export_lock_rule(self):
        self.assertEqual(excel_client.EDITOR_FIELD, {"state_word": "shown_state"})
        ws = sheet_of(published(), "milestones")
        locked = excel.locked_fields(excel_client.EDITOR_LOCKED["milestones"])
        for i, (_, f, _) in enumerate(excel_client.columns("milestones"), start=1):
            want = excel_client.EDITOR_FIELD.get(f, f) not in locked
            self.assertEqual(ws.cell(5, i).protection.locked, not want, f)


class GanttSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = gantt_plant()
        cls.pub = gantt_selected(cls.inputs)
        cls.wb = loaded(cls.pub)
        cls.ws = cls.wb["Plan"]

    def heads(self):
        return [self.ws.cell(4, c).value for c in range(1, self.ws.max_column + 1)]

    def test_widths_follow_the_export_table_and_default_to_twelve(self):
        fields = {f for label, f in excel.GANTT_SHEET_COLUMNS if label in self.heads()}
        seen_default = False
        for i, (label, f) in enumerate([c for c in excel.GANTT_SHEET_COLUMNS if c[0] in self.heads()], start=1):
            want = excel.GANTT_WIDTHS.get(f, 12)
            seen_default = seen_default or f not in excel.GANTT_WIDTHS
            self.assertEqual(self.ws.column_dimensions[self.ws.cell(4, i).column_letter].width, want, label)
        self.assertTrue(seen_default and fields)

    def test_days_and_status_are_worked_out_columns(self):
        self.assertIn("Days", self.heads())
        self.assertIn("Status", self.heads())

    def test_dates_are_left_aligned_dates_and_the_rest_is_not_forced(self):
        saw = 0
        for i, (label, f) in enumerate([c for c in excel.GANTT_SHEET_COLUMNS if c[0] in self.heads()], start=1):
            cell = self.ws.cell(5, i)
            if f in excel.GANTT_DATES:
                saw += 1
                self.assertEqual((cell.alignment.horizontal, cell.number_format), ("left", excel.DATE_FORMAT), label)
            else:
                self.assertIsNone(cell.alignment.horizontal, label)
                self.assertNotEqual(cell.number_format, excel.DATE_FORMAT, label)
        self.assertGreaterEqual(saw, 2)

    def test_frozen_after_the_second_column(self):
        self.assertEqual(self.ws.freeze_panes, "C5")

    def test_the_client_copy_name_is_hidden_and_points_at_the_sheet(self):
        name = self.wb.defined_names[excel.CLIENT_COPY_NAME]
        self.assertTrue(name.hidden)
        self.assertEqual(name.attr_text, "'Plan'!$A$1")

    def test_no_lines_no_gantt_sheet(self):
        pub = gantt_selected(self.inputs)
        pub["data"]["gantt"]["lines"] = []
        self.assertNotIn("Plan", loaded(pub).sheetnames)
        pub["data"].pop("gantt")
        self.assertNotIn("Plan", loaded(pub).sheetnames)


class NoTables(unittest.TestCase):
    def test_the_one_sheet_holds_the_title_band_in_a1_and_a2(self):
        pub = published()
        pub["sections"] = []
        wb = loaded(pub)
        name, sub = excel_client.title_text(pub)
        self.assertEqual(wb.sheetnames, [excel.SHEET_OF["actions"]])
        self.assertEqual((wb.worksheets[0]["A1"].value, wb.worksheets[0]["A2"].value, wb.worksheets[0]["A3"].value), (name, sub, None))

    def test_a_sheet_is_made_only_when_no_table_section_is_shown(self):
        self.assertGreater(len(loaded(published()).sheetnames), 1)

    def test_only_shown_sections_have_sheets(self):
        pub = published()
        keep = [s for s in pub["sections"] if s.get("type") == "actions"]
        pub["sections"] = keep
        self.assertEqual(excel_client.sheet_tables(pub), ["actions"])


if __name__ == "__main__":
    unittest.main()
