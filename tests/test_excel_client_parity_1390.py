"""Row 1390 slice 5: the client copy keeps Latest update, carries no Labels, Response action or Source column, and the import
refuses it with the approved sentence.

Run: python3 dev/run_tests.py test_excel_client_parity_1390
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS  # noqa: F401

import _publish_fixture as fx  # noqa: E402
from _demo import DemoStore  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from clark import excel, excel_client, excel_import as xi, publish  # noqa: E402
from clark.store import Invalid  # noqa: E402

SENTENCE = "This is a client copy of the report. Import the Excel you exported from the editor."
DROPPED = {"labels", "response action", "source"}


class Parity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub = publish.select(fx.inputs(fx.load()))
        cls.data = excel_client.workbook_bytes(cls.pub)
        cls.wb = load_workbook(io.BytesIO(cls.data))

    def test_each_item_sheet_keeps_latest_update(self):
        tables = [t for t in excel_client.sheet_tables(self.pub) if t != "use_cases"]
        self.assertTrue(tables)
        for t in tables:
            labels = [c[0] for c in excel_client.COLUMNS[t]]
            self.assertIn("Latest update", labels, t)

    def test_no_sheet_has_a_dropped_column(self):
        for table, cols in excel_client.COLUMNS.items():
            self.assertFalse(DROPPED & {c[0].lower() for c in cols}, table)
        for ws in self.wb.worksheets:
            for row in ws.iter_rows(max_row=6):
                self.assertFalse(DROPPED & {str(c.value or "").strip().lower() for c in row}, ws.title)

    def test_the_milestones_columns_other_than_the_spec_ones_stay(self):
        keep = {"id", "milestone", "description", "workstream", "original", "agreed", "forecast", "owner", "state reason", "achieved on", "latest update"}
        self.assertTrue(keep <= {c[0].lower() for c in excel_client.COLUMNS["milestones"]})

    def test_every_client_workbook_carries_the_client_copy_mark(self):
        self.assertIn(excel.CLIENT_COPY_NAME, self.wb.defined_names)
        self.assertTrue(self.wb.defined_names[excel.CLIENT_COPY_NAME].hidden)


class Refused(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-xlsx-"))
        self.path = self.tmp / "client.xlsx"
        self.path.write_bytes(excel_client.workbook_bytes(publish.select(fx.inputs(fx.load()))))

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_client_copy_is_refused_with_the_approved_sentence(self):
        for allow in (False, True):
            with self.assertRaises(Invalid) as cm:
                xi.read_workbook(self.demo.store, self.path, "ABC", allow_unrecorded=allow)
            self.assertEqual(str(cm.exception), SENTENCE)
        self.assertEqual(xi.CLIENT_COPY_REFUSAL, SENTENCE)

    def test_nothing_was_staged_or_written(self):
        before = self.demo.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        with self.assertRaises(Invalid):
            xi.read_workbook(self.demo.store, self.path, "ABC", allow_unrecorded=True)
        self.assertEqual(self.demo.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], before)

    def test_an_editor_export_is_not_refused(self):
        import _workbook as wbk
        p = wbk.make_workbook(self.demo.store, self.tmp / "ed.xlsx")
        plan = xi.read_workbook(self.demo.store, p, "ABC", allow_unrecorded=True)
        self.assertIsNotNone(plan)
        wb = load_workbook(str(p))
        self.assertNotIn(excel.CLIENT_COPY_NAME, wb.defined_names)


if __name__ == "__main__":
    unittest.main()
