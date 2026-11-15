"""Row 1185: tests that close the gaps a mutation run found in the first tests of the Latest update on a risk, an issue and a milestone.
Real store, real change route, real publish and Excel code, a real migration. All rows are fictional.

Run: python3 dev/run_tests.py test_latest_update_survivors_1185
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from clark import excel, publish
from clark import excel_import as xi
from clark.store import open_store
from test_latest_update_1185 import Base, KINDS
from test_store_use_case_done_migration import make_at

STEP = 25


class WordlessLooks(Base):
    """A client wording nobody can see (spaces, a zero-width mark) is no wording: the Latest update stays out of the file, the title stays in."""
    def published(self):
        return publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")

    def test_an_unseen_client_wording_keeps_the_latest_update_out_and_the_title_in(self):
        titles = {"raid-risk": "Supplier late", "raid-issue": "Supplier late", "milestones": "Go live"}
        for kind in KINDS:
            for unseen in (" ", "​​", "​ ⁠"):
                with self.subTest(kind=kind, unseen=repr(unseen)):
                    table, ref = self.make(kind)
                    mark = "zz-1185-unseen-%s-%d" % (kind, len(unseen))
                    self.set_latest(table, ref, mark)
                    with self.s.step("dashboard", USER) as st:
                        st.update(table, ref, {"client_message": unseen})
                    text = self.published()
                    self.assertNotIn(mark, text)
                    self.assertIn(titles[kind], text, "the item itself is still in the file")

    def test_one_item_with_no_wording_does_not_take_its_neighbours_update_with_it(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, bare = self.make(kind, client_message="")
                worded = self.make(kind)[1]
                self.set_latest(table, bare, "zz-1185-bare-" + kind)
                self.set_latest(table, worded, "zz-1185-worded-" + kind)
                text = self.published()
                self.assertNotIn("zz-1185-bare-" + kind, text)
                self.assertIn("zz-1185-worded-" + kind, text)

    def test_an_action_with_no_wording_is_dropped_as_before(self):
        with self.s.step("dashboard", USER) as st:
            ref = st.create("actions", {"project": "ABC", "description": "Book the room", "raised": "2026-10-01", "client_visible": 1,
                                        "client_message": "", "latest_update": "<p>zz-1185-action</p>", "source": "demo"})
        self.assertNotIn("zz-1185-action", self.published())


class Duplicate(Base):
    def test_a_copy_of_a_risk_or_an_issue_carries_its_latest_update(self):
        for kind in ("raid-risk", "raid-issue"):
            with self.subTest(kind=kind):
                table, ref = self.make(kind, impact="High", likelihood="Low")
                self.set_latest(table, ref, "Chased the supplier")
                status, body = self.change({"project": "ABC", "kind": "raid", "op": "new", "copy_of": ref, "place": "menu",
                                            "values": {"description": "Copy of Supplier late", "type": kind.split("-")[1].capitalize()}})
                self.assertEqual(status, 200, body)
                self.assertNotEqual(body["ref"], ref)
                self.assertEqual(self.s.read("raid", ref=body["ref"])["latest_update"], "<p>Chased the supplier</p>")


class ExcelCells(Base):
    """The sheet carries the words of the update, not the editor's markup, and a plain text from an older clark comes back as no change."""
    def sheet(self, name):
        tmp = Path(tempfile.mkdtemp(prefix="clark-1185-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        path, state = tmp / "ABC work items.xlsx", tmp / "state.json"
        excel.export_project(self.s, "ABC", path, state, on="2030-06-01")
        from openpyxl import load_workbook
        ws = load_workbook(str(path))[name]
        head = {c.value: c.column for c in ws[1]}
        cells = {ws.cell(r, head["ID"]).value: ws.cell(r, head["Latest update"]).value for r in range(2, ws.max_row + 1)}
        return cells, xi.read_workbook(self.s, path, "ABC")

    def test_the_cell_holds_words_and_an_older_plain_text_imports_as_no_change(self):
        for kind, sheet in (("raid-risk", "Risks & Issues"), ("milestones", "Milestones")):
            with self.subTest(kind=kind):
                _, rich = self.make(kind, latest_update="<p>Chased <b>twice</b></p>")
                _, old = self.make(kind, latest_update="Plain words from before & more")
                cells, plan = self.sheet(sheet)
                self.assertEqual(cells[rich], "Chased twice")
                self.assertEqual(cells[old], "Plain words from before & more")
                self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [])


class SameColumnAsAFreshFile(unittest.TestCase):
    """A brought-up file's new column and a new file's column take the same values: empty, and any text (no hidden rule in either)."""
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_two_columns_are_alike_in_type_null_default_and_what_they_take(self):
        old = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(old), isolation_level=None)
        con.execute("INSERT INTO raid (id, project, type, description, raised, source) VALUES ('ABC-001', 'ABC', 'Risk', 'Supplier late', '2026-10-01', 'test')")
        con.execute("INSERT INTO milestones (id, project, name, baseline_date, source) VALUES ('ABC-M-001', 'ABC', 'Go live', '2030-03-01', 'test')")
        con.close()
        open_store(old, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir))) / "clark.db"
        open_store(fresh, onedrive_roots=[]).close()
        con = sqlite3.connect(str(fresh), isolation_level=None)
        con.execute("INSERT INTO raid (id, project, type, description, raised, source) VALUES ('ABC-001', 'ABC', 'Risk', 'Supplier late', '2026-10-01', 'test')")
        con.execute("INSERT INTO milestones (id, project, name, baseline_date, source) VALUES ('ABC-M-001', 'ABC', 'Go live', '2030-03-01', 'test')")
        con.close()
        for table in ("raid", "milestones"):
            shape = []
            for path in (old, fresh):
                con = sqlite3.connect(str(path))
                try:
                    shape.append([r for r in con.execute("PRAGMA table_info(%s)" % table) if r[1] == "latest_update"])
                    row = con.execute("SELECT rowid FROM %s LIMIT 1" % table).fetchone()[0]
                    self.assertIsNone(con.execute("SELECT latest_update FROM %s WHERE rowid = ?" % table, (row,)).fetchone()[0], "empty to begin with")
                    con.execute("UPDATE %s SET latest_update = ? WHERE rowid = ?" % table, ("x" * 20000, row))
                    self.assertEqual(len(con.execute("SELECT latest_update FROM %s WHERE rowid = ?" % table, (row,)).fetchone()[0]), 20000)
                    con.execute("UPDATE %s SET latest_update = NULL WHERE rowid = ?" % table, (row,))
                finally:
                    con.close()
            self.assertEqual(len(shape[0]), 1, table)
            self.assertEqual([r[1:] for r in shape[0]], [r[1:] for r in shape[1]], table + ": same type, not-null flag, default and key")


if __name__ == "__main__":
    unittest.main()
