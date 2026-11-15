"""Item 1185: migration step 25, raid.latest_update and milestones.latest_update (src/clark/store.py migrate_latest_update, guarded).

The step adds one column at the end of raid and of milestones (ALTER TABLE ... ADD COLUMN): no table is made again, no existing value
changes, and every row already there has no latest update (NULL). A safety copy is taken first by the runner. A second run changes
nothing. Fictional data only.

Run: python3 dev/run_tests.py test_store_latest_update_migration
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from clark import store as store_module
from clark.store import open_store
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 25
TABLES = ("raid", "milestones")


def add_rows(path):
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("INSERT INTO milestones (id, project, name, owner, source) VALUES ('ABC-M-001', 'ABC', 'Go live', 'Carol Example', 'test')")
    con.execute("INSERT INTO raid (id, project, type, description, raised, source) VALUES ('ABC-001', 'ABC', 'Risk', 'Supplier may be late', '2026-10-02', 'test')")
    con.execute("INSERT INTO raid (id, project, type, description, raised, source) VALUES ('ABC-002', 'ABC', 'Issue', 'Feed is down', '2026-10-03', 'test')")
    con.close()


def names(path, table):
    con = sqlite3.connect(str(path))
    try:
        return [c[1] for c in con.execute(f"PRAGMA table_info({table})")]
    finally:
        con.close()


def rows(path, table, leave_out=()):
    con = sqlite3.connect(str(path))
    try:
        kept = ", ".join(f'"{c}"' for c in names(path, table) if c not in leave_out)
        return con.execute(f'SELECT rowid, {kept} FROM "{table}" ORDER BY rowid').fetchall()
    finally:
        con.close()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_in_the_table_at_its_number_and_the_literal_and_the_table_agree(self):
        self.assertIn((STEP, store_module.migrate_latest_update), store_module.MIGRATIONS)
        self.assertEqual(store_module.LATEST_UPDATE_STEP, STEP)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        src = (SRC / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^SCHEMA_VERSION = (\d+)", src, re.M), [str(store_module.SCHEMA_VERSION)])

    def test_a_populated_layout_24_file_gains_the_column_last_on_both_tables_and_keeps_every_value(self):
        path = make_at(self.dir, STEP - 1)
        add_rows(path)
        self.assertEqual(version(path), str(STEP - 1))
        for t in TABLES:
            self.assertNotIn("latest_update", names(path, t))
        before = {t: rows(path, t) for t in TABLES}
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)      # a migration is not a step: no Undo
        finally:
            s.close()
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
        for t in TABLES:
            self.assertEqual(names(path, t)[-1], "latest_update")
            self.assertEqual(rows(path, t, ("latest_update",)), before[t], "no existing value changed")
            self.assertEqual(sqlite3.connect(str(path)).execute(f"SELECT count(*) FROM {t} WHERE latest_update IS NOT NULL").fetchone()[0], 0)

    def test_a_safety_copy_is_taken_and_a_second_open_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        add_rows(path)
        open_store(path, onedrive_roots=[]).close()
        copies = sorted((self.dir / "backups").glob("*-migrate.db"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(version(copies[0]), str(STEP - 1))
        shutil.rmtree(self.dir / "backups", ignore_errors=True)
        was = {t: rows(path, t) for t in TABLES}
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual({t: rows(path, t) for t in TABLES}, was)
        self.assertFalse((self.dir / "backups").exists())

    def test_the_step_is_safe_to_run_twice_and_keeps_a_value_already_set(self):
        path = make_at(self.dir, STEP)
        add_rows(path)
        con = store_module.connect(path)
        con.execute("UPDATE raid SET latest_update = '<p>Chased</p>' WHERE id = 'ABC-001'")
        store_module.migrate_latest_update(con)
        self.assertEqual([r[0] for r in con.execute("SELECT latest_update FROM raid ORDER BY id")], ["<p>Chased</p>", None])
        con.close()


if __name__ == "__main__":
    unittest.main()
