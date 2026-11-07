"""Row 811: the migration step that gives an action, a risk and an issue the "needed from the client" flag (actions.client_action and
raid.client_action, src/clark/store.py, guarded).

The step is ALTER TABLE ... ADD COLUMN of an INTEGER NOT NULL DEFAULT 0 column with the 0/1 CHECK, on actions and on raid. A file from
1.0.1 (layout 16) keeps every row, with the flag off; a new file has the columns from schema.sql. The step is step 17 of MIGRATIONS
(STEP below). Fictional data only.

Run: python3 dev/run_tests.py test_store_client_action_migration
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clark import store as store_module
from clark.store import Invalid, connect, open_store
from test_store_migration import make_v1, version
from test_store_use_case_done_migration import make_at, schema_of

STEP = 17
BEFORE = str(STEP - 1)
NOW = str(store_module.SCHEMA_VERSION)
TABLES = ("actions", "raid")


def add_items(path):
    """An action and a risk written raw as the layout before this step left them."""
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("INSERT INTO actions (id, project, description, raised, source) VALUES ('ABC-A-001', 'ABC', 'Send the matching rules', '2026-10-01', 'test')")
    con.execute("INSERT INTO raid (id, project, type, description, raised, source) VALUES ('ABC-001', 'ABC', 'Risk', 'Portal supplier late', '2026-10-01', 'test')")
    con.close()


def columns(path, table):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("PRAGMA table_info(%s)" % table).fetchall()
    finally:
        con.close()


def rows_without_flag(path):
    con = sqlite3.connect(str(path))
    try:
        out = {}
        for t in TABLES:
            names = ", ".join(c[1] for c in con.execute("PRAGMA table_info(%s)" % t) if c[1] != "client_action")
            out[t] = con.execute("SELECT %s FROM %s ORDER BY id" % (names, t)).fetchall()
        return out
    finally:
        con.close()


def dump(path):
    con = sqlite3.connect(str(path))
    try:
        return list(con.iterdump())
    finally:
        con.close()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_in_the_table_at_its_number_and_the_table_has_no_gap(self):
        self.assertIn((STEP, store_module.migrate_client_action), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_old_data_opens_keeps_every_row_and_the_flag_is_off(self):
        path = make_at(self.dir, STEP - 1)
        add_items(path)
        self.assertEqual(version(path), BEFORE)
        for t in TABLES:
            self.assertNotIn("client_action", [c[1] for c in columns(path, t)])
        before = rows_without_flag(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)        # a migration is not a step
            self.assertEqual(s.read("actions", ref="ABC-A-001")["client_action"], 0)
            self.assertEqual(s.read("raid", ref="ABC-001")["client_action"], 0)
        finally:
            s.close()
        self.assertEqual(rows_without_flag(path), before)
        self.assertEqual(len(sorted((self.dir / "backups").glob("*-migrate.db"))), 1)               # the safety copy

    def test_a_version_1_file_goes_through_every_step_and_ends_with_the_columns(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)
        for t in TABLES:
            self.assertEqual(columns(path, t)[-1][1:], ("client_action", "INTEGER", 1, "0", 0))

    def test_a_brought_up_file_and_a_new_file_have_the_same_tables(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir))) / "clark.db"
        open_store(fresh, onedrive_roots=[]).close()
        for t in TABLES:
            self.assertEqual(columns(path, t), columns(fresh, t))
        self.assertEqual(set(schema_of(path)), set(schema_of(fresh)))

    def test_the_step_changes_no_other_table_index_or_trigger(self):
        path = make_at(self.dir, STEP - 1)

        def keep(d):
            return {k: v for k, v in d.items() if k not in {("table", t) for t in TABLES}}
        before = keep(schema_of(path))
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= STEP)):     # this step alone (row 926's, step 18, adds a table and projects columns)
            open_store(path, onedrive_roots=[]).close()
        self.assertEqual(keep(schema_of(path)), before)

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        path = make_at(self.dir, STEP - 1)
        add_items(path)
        open_store(path, onedrive_roots=[]).close()
        shutil.rmtree(self.dir / "backups", ignore_errors=True)
        was = dump(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(dump(path), was)
        self.assertEqual(list((self.dir / "backups").glob("*-migrate.db")) if (self.dir / "backups").exists() else [], [])

    def test_the_step_is_safe_to_run_twice_and_keeps_a_set_flag(self):
        path = make_at(self.dir, STEP - 1)
        add_items(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_client_action(con)
            con.execute("UPDATE actions SET client_action = 1 WHERE id = 'ABC-A-001'")
            store_module.migrate_client_action(con)
            con.execute("COMMIT")
        finally:
            con.close()
        con = sqlite3.connect(str(path))
        try:
            self.assertEqual(con.execute("SELECT client_action FROM actions").fetchall(), [(1,)])
            self.assertEqual(con.execute("SELECT client_action FROM raid").fetchall(), [(0,)])
        finally:
            con.close()

    def test_the_column_takes_only_0_or_1(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        add_items(path)
        con = sqlite3.connect(str(path))
        try:
            for t in TABLES:
                with self.assertRaises(sqlite3.IntegrityError):
                    con.execute("UPDATE %s SET client_action = 2" % t)
        finally:
            con.close()

    def test_an_older_clark_refuses_the_migrated_file_and_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        add_items(path)
        open_store(path, onedrive_roots=[]).close()
        was = dump(path)
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("newer clark", str(e.exception))
        self.assertEqual(dump(path), was)

    def test_a_step_that_fails_after_its_alter_rolls_back_and_the_second_open_migrates(self):
        path = make_at(self.dir, STEP - 1)
        add_items(path)

        def broken(con):
            con.execute("ALTER TABLE actions ADD COLUMN client_action INTEGER NOT NULL DEFAULT 0 CHECK (client_action IN (0,1))")
            con.execute("SELECT nonsense FROM nowhere")
        table = tuple((n, broken if n == STEP else fn) for n, fn in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        self.assertEqual(version(path), BEFORE)
        self.assertNotIn("client_action", [c[1] for c in columns(path, "actions")])
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)


if __name__ == "__main__":
    unittest.main()
