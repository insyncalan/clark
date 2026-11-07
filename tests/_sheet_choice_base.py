"""Shared by test_excel_sheet_listing, test_excel_sheet_choice and test_excel_sheet_followups (#912): the exported workbook is built once
for each class (setUpClass) and its bytes kept; each test writes them into its own temp folder and gets a fresh DemoStore.
The ids of the two actions are the same in every DemoStore (ABC-A-001, ABC-A-002), which is checked below."""
import shutil
import tempfile
import time  # noqa: F401
from pathlib import Path

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_excel_route import Base, encoded, ON, USER, DemoStore
from clark import excel, excel_import, excel_route

TABLES = excel_import.CHOICE_ORDER
SHEET = {"actions": "Actions", "raid": "Risks & Issues", "decisions": "Decisions", "milestones": "Milestones", "use_cases": "Use cases"}
TITLE = {"actions": "Description", "raid": "Description", "decisions": "Decision", "milestones": "Milestone", "use_cases": "Use case"}
EXTRA = {"raid": {"Type": "Risk"}, "decisions": {"Status": "Pending"}, "use_cases": {"Status": "On track"}}


def add_row(ws, table, text, **cells):
    head = {c.value: c.column for c in ws[1]}
    row = ws.max_row + 1
    for label, value in {TITLE[table]: text, **EXTRA.get(table, {}), **cells}.items():   # (cells may override the status)
        ws.cell(row, head[label]).value = value


STAMPED = ("milestones", "workstreams", "actions", "raid", "decisions", "use_cases")


class Cached(Base):
    """Base without the per-test export: the workbook (edited by `prepare(wb, a1, a2)` when a class defines it) is made once."""
    prepare = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        demo = DemoStore()
        tmp = Path(tempfile.mkdtemp(prefix="clark-route-xlsx-"))
        try:
            cls.a1 = demo.action(description="Draft the cut-over plan", due_date="2030-04-15")
            cls.a2 = demo.action(description="Book the training room")
            path = tmp / "ABC work items.xlsx"
            made = excel.export_project(demo.store, "ABC", path, tmp / "state.json", on=ON)
            cls.record = excel.load_state(tmp / "state.json", made)
            cls.state_key = excel.id_key("ABC", cls.record["export_id"])
            if cls.prepare is not None:
                wb = load_workbook(str(path))
                cls.prepare(wb, cls.a1, cls.a2)
                wb.save(str(path))
            cls.workbook = path.read_bytes()
            cls.stamps = {t: dict(demo.store.con.execute(f"SELECT id, updated_at FROM {t}").fetchall()) for t in STAMPED}
        finally:
            demo.close()
            shutil.rmtree(str(tmp), True)

    def setUp(self):
        excel_route.PLANS.clear()
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-route-xlsx-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.addCleanup(excel_route.PLANS.clear)
        self.now = [1000.0]
        self.seam = excel_route.make_excel_import(self.store.path, [], USER, clock=lambda: self.now[0])
        a1 = self.demo.action(description="Draft the cut-over plan", due_date="2030-04-15")
        a2 = self.demo.action(description="Book the training room")
        self.assertEqual((a1, a2), (self.a1, self.a2), "the ids are the same in every store")
        for t, rows in self.stamps.items():          # the rows carry the times they had when the workbook was made (no clash that was not there)
            for ident, at in rows.items():
                self.store.con.execute(f"UPDATE {t} SET updated_at = ? WHERE id = ?", (at, ident))
        self.store.con.commit()
        self.path = self.tmp / "ABC work items.xlsx"
        self.path.write_bytes(self.workbook)
        excel.save_state(Path(self.store.path).parent / excel.STATE_FILE, self.state_key, json_copy(self.record))
        self.fresh = self.workbook


def json_copy(x):
    import json
    return json.loads(json.dumps(x))


def prepare_sheets(wb, a1, a2):
    ws = wb["Actions"]
    head = {c.value: c.column for c in ws[1]}
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == a2)
    ws.delete_rows(row)                                         # a2 is now "not in the workbook"
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == a1:
            ws.cell(r, head["Description"]).value = "Draft the cut-over plan, version two"
    for t in TABLES:
        add_row(wb[SHEET[t]], t, f"A new {t} row")


class Sheets(Cached):
    prepare = staticmethod(prepare_sheets)

    def counts(self):
        return {t: len(self.store.read(t, project="ABC")) for t in TABLES}

    def archived(self):
        return {r["id"] for r in self.store.read("actions", project="ABC") if r["archived"]}

    def sheets(self):
        return self.post(op="sheets", project="ABC", name="ABC work items.xlsx", data=encoded(self.path))

    def pick(self, tables):
        status, listed = self.sheets()
        self.assertEqual(status, 200, listed)
        return self.post(op="check", project="ABC", file=listed["file"], sheets=list(tables))

    def import_all_numbers(self, got):
        return self.post(op="apply", project="ABC", plan=got["plan"], accept=[i["n"] for i in got["items"]], confirm=True)
