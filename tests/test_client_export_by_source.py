"""Row 1390 slice 3: two exports by source. The editor export carries every row and every column; the workbook made from the
published client page leaves out the rows a client may not see, the columns that say who may see a row, the Internal note, and
the History sheet, and the import refuses it.

Run: python3 dev/run_tests.py test_client_export_by_source
Fictional data only (tests/fixtures/publish-plant.json). Headings are matched without caring about the hyphen, so a rename of
"Client-visible" to "Client visible" does not change what is pinned.
"""
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS  # noqa: F401

import _publish_fixture as fx  # noqa: E402
import test_gantt_excel_export as ge  # noqa: E402
from _demo import USER, DemoStore  # noqa: E402
from clark import changes, excel, excel_client, publish  # noqa: E402
from clark import excel_import as xi  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

FLAG = re.compile(r"client[\s_-]*visible|on (?:the )?dashboard", re.I)
NOTE = re.compile(r"internal[\s_-]*note", re.I)
NOT_FOR_CLIENT = re.compile(r"labels?|response action|sensitive", re.I)
TABLES = ("actions", "raid", "decisions", "milestones", "use_cases")


def heads(wb):
    """Every cell text on every sheet of a workbook, with its sheet."""
    return [(ws.title, str(c.value)) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None]


class ClientCopy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant = fx.load()
        inputs = ge.plant()
        cls.inputs = inputs
        cls.pub = publish.select(inputs)
        cls.data = excel_client.workbook_bytes(cls.pub)
        cls.wb = load_workbook(io.BytesIO(cls.data))
        cls.text = heads(cls.wb)

    def test_every_data_sheet_is_in_the_copy(self):
        got = set(self.wb.sheetnames)
        self.assertTrue({excel.SHEET_OF[t] for t in TABLES} <= got, got)
        self.assertIn("Plan", got)

    def test_a_row_with_client_visible_no_is_on_no_sheet(self):
        hidden = {r["id"] for t in TABLES for r in self.plant["data"][t] if r.get("client_visible") == 0}
        self.assertTrue(hidden, "the plant has hidden rows")
        for sheet, cell in self.text:
            for ident in hidden:
                self.assertNotIn(ident, cell, f"{ident} is on {sheet}")

    def test_a_gantt_line_with_its_eye_off_is_not_on_the_gantt_sheet(self):
        off = [r for r in self.inputs["data"]["gantt_lines"] if r.get("show") == 0]
        on = [r for r in self.inputs["data"]["gantt_lines"] if r.get("show") == 1]
        self.assertTrue(off and on)
        ids = {str(c.value) for row in self.wb["Plan"].iter_rows() for c in row if c.value is not None}
        for r in off:
            self.assertNotIn(r["id"], ids)
        for r in on:
            self.assertIn(r["id"], ids)

    def test_the_gantt_flag_column_is_left_out_even_when_no_column_is_hidden(self):
        inputs = ge.plant(gantt_hidden_columns="")
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(inputs))))
        labels = [str(c.value) for c in wb["Plan"][4] if c.value]
        self.assertIn("Line", labels)
        self.assertIn("Notes", labels, "no column was hidden, so the others are all there")
        self.assertEqual([x for x in labels if FLAG.fullmatch(x)], [])

    def test_no_heading_says_client_visible_or_internal_note_on_any_sheet(self):
        for sheet, cell in self.text:
            self.assertIsNone(FLAG.fullmatch(cell.strip()), f"{sheet}: {cell}")
            self.assertIsNone(NOTE.fullmatch(cell.strip()), f"{sheet}: {cell}")
        for ws in self.wb.worksheets:
            for row in ws.iter_rows(min_row=1, max_row=4):
                for c in row:
                    self.assertFalse(c.value and (FLAG.search(str(c.value)) or NOTE.search(str(c.value))), f"{ws.title}!{c.coordinate}")

    def test_no_labels_response_action_or_sensitive_column_in_the_copy(self):
        for ws in self.wb.worksheets:
            for c in ws[4]:
                self.assertFalse(c.value and NOT_FOR_CLIENT.fullmatch(str(c.value).strip()), f"{ws.title}: {c.value}")

    def test_no_client_sheet_has_a_latest_update_labels_response_action_or_source_heading(self):
        """Row 1390 (PM ruling): the four client sheets carry no Latest update; no client sheet has any of these four headings."""
        banned = {"latest update", "labels", "response action", "source"}
        for ws in self.wb.worksheets:
            for c in ws[4]:
                self.assertNotIn(str(c.value).strip().lower(), banned, f"{ws.title}!{c.coordinate}: {c.value}")
        for table in ("actions", "raid", "decisions", "milestones", "use_cases"):
            self.assertNotIn("Latest update", [h for h, _, _ in excel_client.COLUMNS[table]], table)

    def test_the_copy_has_no_history_sheet_and_no_internal_tag(self):
        self.assertNotIn("History", self.wb.sheetnames)
        self.assertFalse([w for w in self.wb.sheetnames if w.lower() in ("history", "lists", "cover")], self.wb.sheetnames)
        for ws in self.wb.worksheets:
            self.assertEqual(ws.sheet_state, "visible")
        for sheet, cell in self.text:
            self.assertNotIn("INTERNAL", cell, sheet)

    def test_client_workbook_has_no_hidden_rows_or_client_visible_columns(self):
        """DoD9 (1390), the name the ticket gives: the two checks together, run on the same client copy."""
        self.test_a_row_with_client_visible_no_is_on_no_sheet()
        self.test_no_heading_says_client_visible_or_internal_note_on_any_sheet()

    def test_the_client_wording_stays(self):
        ws = self.wb[excel.SHEET_OF["actions"]]
        self.assertIn("ZQ-KEEP-MESSAGE-1", {str(c.value) for row in ws.iter_rows(min_row=5) for c in row})


class EditorExport(unittest.TestCase):
    """The same plant through the editor's own sheets: the flag and the Internal note are there, in the headings."""

    def test_every_editor_sheet_has_the_flag_heading_and_milestones_the_note(self):
        for sheet, table, columns, _ in excel.SHEETS:
            labels = [label for label, _ in columns]
            self.assertTrue([x for x in labels if FLAG.fullmatch(x)], f"{sheet}: {labels}")
            self.assertEqual(bool([x for x in labels if NOTE.fullmatch(x)]), table == "milestones", sheet)
        self.assertTrue([label for label, _ in excel.GANTT_SHEET_COLUMNS if FLAG.fullmatch(label)])

    def test_a_real_editor_export_carries_the_hidden_rows_and_the_note(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        tmp = Path(tempfile.mkdtemp(prefix="clark-cx-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        change = changes.make_change(demo.store.path, [], USER)
        status, body = change({"project": "ABC", "kind": "actions", "op": "new", "values": {"description": "Kept off the client page"}})
        self.assertEqual(status, 200, body)
        status, body = change({"project": "ABC", "kind": "actions", "op": "update", "id": body["ref"], "changes": {"client_visible": 0}})
        self.assertEqual(status, 200, body)
        path = tmp / "editor.xlsx"
        excel.export_project(demo.store, "ABC", path, tmp / "state.json", on="2030-06-01")
        wb = load_workbook(str(path))
        seen = {sheet: cell for sheet, cell in heads(wb)}
        self.assertTrue(any(FLAG.fullmatch(cell.strip()) for _, cell in heads(wb)))
        self.assertTrue(any(NOTE.fullmatch(cell.strip()) for sheet, cell in heads(wb) if sheet == "Milestones"), seen.keys())
        self.assertIn("History", wb.sheetnames)
        hidden = [r["id"] for r in demo.store.read("actions", project="ABC") if r.get("client_visible") == 0]
        self.assertEqual(len(hidden), 1)
        got = {cell for _, cell in heads(wb)}
        for ident in hidden:
            self.assertIn(ident, got, f"the editor export keeps {ident}")

    def test_editor_export_keeps_them(self):
        """DoD9 (1390), the name the ticket gives: the editor export keeps the hidden rows, the flag headings and the note."""
        self.test_every_editor_sheet_has_the_flag_heading_and_milestones_the_note()
        self.test_a_real_editor_export_carries_the_hidden_rows_and_the_note()


class ImportOfAClientCopy(unittest.TestCase):
    def test_the_import_refuses_every_sheet_and_stages_nothing(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        tmp = Path(tempfile.mkdtemp(prefix="clark-cx-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        path = tmp / "client.xlsx"
        path.write_bytes(excel_client.workbook_bytes(publish.select(fx.inputs())))
        self.assertIsNone(excel.export_id_of(path))
        plan = xi.read_workbook(demo.store, path, "ABC", state_path=tmp / "state.json")
        self.assertEqual(plan.changes, [])
        for table in TABLES:
            sheet = excel.SHEET_OF[table]
            self.assertTrue(any(p.sheet == sheet and "no id column" in p.message for p in plan.problems), (sheet, plan.problems))


if __name__ == "__main__":
    unittest.main()
