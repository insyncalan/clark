"""Row 1390: a client copy is refused whole on import, in the approved sentence, and nothing is written; the editor's own file is not refused.

Run: python3 dev/run_tests.py test_excel_client_copy_refused_1390
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import DemoStore
from openpyxl import load_workbook

from clark import excel, excel_client, publish
from clark import excel_import as xi
from clark.store import Invalid

SENTENCE = ("This file is a client copy. It leaves out the rows hidden from the client, so importing it would overwrite them. "
            "Import the project's own file instead.")


class ClientCopyRefused(unittest.TestCase):
    def test_a_client_copy_is_refused_whole_in_the_approved_sentence_and_nothing_is_written(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        d = Path(tempfile.mkdtemp(prefix="clark-cc-"))
        self.addCleanup(shutil.rmtree, d, True)
        import test_gantt_excel_export as ge
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(ge.plant(gantt_tab_name="Gantt")))))
        self.assertIn(excel.CLIENT_COPY_NAME, wb.defined_names)
        wb.save(str(d / "client.xlsx"))
        steps = demo.store.read("projects", ref="ABC")
        with self.assertRaises(Invalid) as cm:
            xi.read_workbook(demo.store, d / "client.xlsx", "ABC", state_path=d / "s.json", allow_unrecorded=True)
        self.assertEqual(str(cm.exception), SENTENCE)
        self.assertEqual(demo.store.read("projects", ref="ABC"), steps)

    def _client_copy(self, d, rename=None):
        import test_gantt_excel_export as ge
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(ge.plant(gantt_tab_name="Gantt")))))
        if rename:
            for ws in wb.worksheets:
                ws.title = rename + str(wb.worksheets.index(ws))      # no sheet is called Gantt any more; the mark stays
        self.assertIn(excel.CLIENT_COPY_NAME, wb.defined_names)
        wb.save(str(d / "client.xlsx"))

    def test_a_client_copy_with_no_gantt_sheet_is_refused_by_the_mark(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        d = Path(tempfile.mkdtemp(prefix="clark-cc-"))
        self.addCleanup(shutil.rmtree, d, True)
        self._client_copy(d, rename="Other")
        with self.assertRaises(Invalid) as cm:
            xi.read_workbook(demo.store, d / "client.xlsx", "ABC", state_path=d / "s.json", allow_unrecorded=True)
        self.assertEqual(str(cm.exception), SENTENCE)

    def test_a_client_copy_is_refused_when_only_some_sheets_are_asked_for(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        d = Path(tempfile.mkdtemp(prefix="clark-cc-"))
        self.addCleanup(shutil.rmtree, d, True)
        self._client_copy(d)
        with self.assertRaises(Invalid) as cm:
            xi.read_workbook(demo.store, d / "client.xlsx", "ABC", state_path=d / "s.json", allow_unrecorded=True, sheets={"actions"})
        self.assertEqual(str(cm.exception), SENTENCE)

    def test_the_editors_own_file_is_not_refused(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        d = Path(tempfile.mkdtemp(prefix="clark-cc-"))
        self.addCleanup(shutil.rmtree, d, True)
        excel.export_project(demo.store, "ABC", d / "w.xlsx", d / "s.json", on="2030-06-01")
        p = xi.read_workbook(demo.store, d / "w.xlsx", "ABC", state_path=d / "s.json")
        self.assertIsNotNone(p)


if __name__ == "__main__":
    unittest.main()
