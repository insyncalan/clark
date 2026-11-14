"""Item 1171: a full export carries a very hidden, protected metadata sheet (four fields and a hash per exported row); the client
workbook does not; the import reads it as information only and never depends on it.

Run: python3 dev/run_tests.py test_excel_metadata_1171
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fx
from _demo import DemoStore
from openpyxl import load_workbook

from clark import __version__, excel, excel_client, excel_import as xi, publish_flow, settings


class Case(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-meta-"))
        self.a1 = self.demo.action(description="Draft the cut-over plan", due_date="2026-11-01", latest_update="First draft")
        self.a2 = self.demo.action(description="Book the training room")
        self.path = excel.export_project(self.s, "ABC", self.tmp / "ABC.xlsx", self.tmp / "state.json", on="2026-11-14", exported_by="Pat Example", exporter_name="Pat Example")

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def edited(self, change):
        wb = load_workbook(self.path)
        change(wb)
        out = self.tmp / "edited.xlsx"
        wb.save(out)
        return out

    def read(self, path):
        return xi.read_workbook(self.s, path, "ABC", state_path=self.tmp / "state.json", allow_unrecorded=True)

    def row_of(self, ws, rid):
        return next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == rid)


class Sheet(Case):
    def test_very_hidden_protected_with_four_fields_and_row_hashes_only(self):
        ws = load_workbook(self.path)[excel.META_NAME]
        self.assertEqual(ws.sheet_state, "veryHidden")
        self.assertTrue(ws.protection.sheet)
        rows = [[c for c in r] for r in ws.iter_rows(values_only=True)]
        self.assertEqual([r[:2] for r in rows[:4]], [["exporter", "Pat Example"], ["exported_at_utc", "2026-11-14 00:00:00"],
                                    ["clark_version", __version__], ["project", "ABC"]])
        hashes = rows[4:]
        self.assertTrue(hashes)
        self.assertTrue(all(r[0] == "row" and len(r[3]) == 64 for r in hashes))
        self.assertIn(("actions", self.a1), {(r[1], r[2]) for r in hashes})
        self.assertEqual(ws.max_column, 4)

    def test_the_sheet_name_is_never_a_gantt_tab_name(self):
        self.assertNotEqual(excel.gantt_sheet_name(excel.META_NAME), excel.META_NAME)

    def test_the_template_has_no_metadata_sheet(self):
        import io
        self.assertNotIn(excel.META_NAME, load_workbook(io.BytesIO(excel.template_bytes())).sheetnames)


class Import(Case):
    def test_untouched_has_no_edited_rows_and_one_note(self):
        plan = self.read(self.path)
        self.assertEqual(plan.edited_rows, [])
        self.assertEqual(plan.changes, [])
        self.assertEqual(plan.export_info["exporter"], "Pat Example")
        self.assertTrue(any("2026-11-14 00:00:00 UTC" in n for n in plan.notes))

    def test_with_no_profile_name_the_exporter_is_blank_and_the_note_has_no_name(self):
        """Item 1171 ruling: the Settings name only, never the login name. The Cover may still show the login name; the sheet does not."""
        path = excel.export_project(self.s, "ABC", self.tmp / "NoName.xlsx", self.tmp / "state2.json", on="2026-11-14", exported_by="login-name")
        wb = load_workbook(path)
        rows = [[c.value for c in r] for r in wb[excel.META_NAME].iter_rows(max_row=4)]
        self.assertEqual(rows[0][:2], ["exporter", None])
        self.assertNotIn("login-name", [c for r in rows for c in r])
        plan = self.read(path)
        self.assertTrue(any(n.startswith("Exported with clark ") and n.endswith(" on 2026-11-14 00:00:00 UTC.") for n in plan.notes), plan.notes)

    def test_an_edited_row_is_reported_and_an_untouched_one_is_not(self):
        def edit(wb):
            ws = wb["Actions"]
            ws.cell(self.row_of(ws, self.a1), 2).value = "Draft the cut-over plan v2"
        plan = self.read(self.edited(edit))
        self.assertEqual(plan.edited_rows, [("actions", self.a1)])
        self.assertEqual([c.id for c in plan.changes], [self.a1])

    def test_a_missing_or_mismatching_hash_says_nothing(self):
        def drop(wb):
            ws = wb[excel.META_NAME]
            for r in range(ws.max_row, 4, -1):
                ws.delete_rows(r)
        plan = self.read(self.edited(drop))
        self.assertEqual(plan.edited_rows, [])

        def wrong(wb):
            ws = wb[excel.META_NAME]
            for r in range(5, ws.max_row + 1):
                ws.cell(r, 4).value = "0" * 63 + "z"           # not a hash: not used
            wb["Actions"].cell(2, 2).value = "changed"
        plan = self.read(self.edited(wrong))
        self.assertEqual(plan.edited_rows, [])
        self.assertTrue(plan.changes)                           # the staged comparison still works

    def test_a_deleted_edited_or_junk_sheet_never_blocks_or_grants_trust(self):
        def delete(wb):
            del wb[excel.META_NAME]

        def junk(wb):
            ws = wb[excel.META_NAME]
            ws.delete_rows(1, ws.max_row)
            ws["A1"], ws["B7"], ws["D3"] = 5, object.__class__.__name__, 12
            ws["A2"], ws["B2"] = "row", None

        def edit_fields(wb):
            wb[excel.META_NAME]["B1"] = "x" * 5000
            wb[excel.META_NAME]["B3"] = None
        for change in (delete, junk, edit_fields):
            plan = self.read(self.edited(change))
            self.assertTrue(plan.unrecorded)                    # trust is the export record's, never this sheet's
            self.assertFalse(plan.problems)
        self.assertIsNone(self.read(self.edited(delete)).export_info)
        self.assertLessEqual(len(self.read(self.edited(edit_fields)).export_info["exporter"]), excel.META_TEXT_CUT)

    def test_another_sheet_named_like_it_is_not_a_project_sheet(self):
        self.assertNotIn(excel.META_NAME.lower(), xi.SHEET_TABLES)


class Client(unittest.TestCase):
    def test_client_workbook_has_no_metadata_sheet(self):
        import io
        from test_excel_client_protect import published
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(published())))
        self.assertNotIn(excel.META_NAME, wb.sheetnames)
        self.assertFalse([w.title for w in wb.worksheets if w.sheet_state == "veryHidden"])


class ThroughThePublisher(unittest.TestCase):
    """Item 1171, end to end: Publisher.export puts the Settings profile name in the sheet, and nothing when none is saved (the login
    name, which is what by_user gives, never goes in; the Cover is not changed by this)."""

    def export(self, name):
        tmp = Path(tempfile.mkdtemp(prefix="clark-meta-pub-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        db = tmp / "clark.db"
        fx.build_db(db, fx.load())
        if name:
            settings.set_profile(tmp, name, "")
        pub = publish_flow.Publisher(db, [], today=lambda: "2026-10-28", by_user=lambda: "the-login-name", data_dir=tmp)
        status, body = pub.export("PUB")
        self.assertEqual(status, 200, body)
        out = tmp / "out.xlsx"
        out.write_bytes(body["data"])
        wb = load_workbook(out)
        return [[c.value for c in r] for r in wb[excel.META_NAME].iter_rows(max_row=4)]

    def test_the_saved_profile_name_is_the_exporter(self):
        rows = self.export("Pat Example")
        self.assertEqual(rows[0][:2], ["exporter", "Pat Example"])
        self.assertEqual(rows[1][:2], ["exported_at_utc", "2026-10-28 00:00:00"])
        self.assertEqual(rows[2][:2], ["clark_version", __version__])

    def test_no_saved_name_leaves_the_exporter_blank_not_the_login_name(self):
        rows = self.export(None)
        self.assertEqual(rows[0][:2], ["exporter", None])
        self.assertNotIn("the-login-name", [c for r in rows for c in r])


if __name__ == "__main__":
    unittest.main()
