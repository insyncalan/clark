"""Row 1185: the migration step that gives risks, issues and milestones a Latest update column (src/clark/store.py, guarded). Step 25.
A file from the layout before keeps every row with the column empty; a new file has the columns from schema.sql. Fictional data only.

Run: python3 dev/run_tests.py test_latest_update_migration_1185
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clark import store as store_module
from clark.store import open_store
from test_store_migration import version
from test_store_use_case_done_migration import make_at, schema_of

STEP = 25
TABLES = ("raid", "milestones")


def names(path, table):
    con = sqlite3.connect(str(path))
    try:
        return [c[1] for c in con.execute("PRAGMA table_info(%s)" % table)]
    finally:
        con.close()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_in_the_table_and_the_table_has_no_gap(self):
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertIn(STEP, [n for n, _ in store_module.MIGRATIONS])
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_old_data_opens_keeps_its_rows_and_the_column_is_empty(self):
        path = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO raid (id, project, type, description, raised, source) VALUES ('ABC-001', 'ABC', 'Risk', 'Supplier late', '2026-10-01', 'test')")
        con.execute("INSERT INTO milestones (id, project, name, baseline_date, source) VALUES ('ABC-M-001', 'ABC', 'Go live', '2030-03-01', 'test')")
        con.close()
        self.assertEqual(version(path), str(STEP - 1))
        for t in TABLES:
            self.assertNotIn("latest_update", names(path, t))
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)
            self.assertIsNone(s.read("raid", ref="ABC-001")["latest_update"])
            self.assertIsNone(s.read("milestones", ref="ABC-M-001")["latest_update"])
            self.assertEqual(s.read("raid", ref="ABC-001")["description"], "Supplier late")
        finally:
            s.close()
        self.assertEqual(len(sorted((self.dir / "backups").glob("*-migrate.db"))), 1)

    def test_a_brought_up_file_and_a_new_file_have_the_same_tables(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir))) / "clark.db"
        open_store(fresh, onedrive_roots=[]).close()
        for t in TABLES:
            self.assertIn("latest_update", names(path, t))
            self.assertEqual(sorted(names(path, t)), sorted(names(fresh, t)))
        self.assertEqual(set(schema_of(path)), set(schema_of(fresh)))

    def test_a_second_open_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        before = list(sqlite3.connect(str(path)).iterdump())
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(list(sqlite3.connect(str(path)).iterdump()), before)


if __name__ == "__main__":
    unittest.main()
