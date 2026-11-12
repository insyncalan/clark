"""#944 T1: migration step 20, projects.brand (src/clark/store.py migrate_brand, guarded).

The step adds one column at the end of projects (ALTER TABLE ... ADD COLUMN with the CHECK of schema.sql), so no table is made again and no
existing value changes. A safety copy is taken first by the runner. A second run changes nothing. An older clark (layout 19) refuses a
layout-20 file and changes nothing. Fictional data only.

Run: python3 dev/run_tests.py test_store_brand_migration
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC
from clark import store as store_module
from clark.store import Invalid, connect, open_store
from test_store_migration import make_v1, version
from test_store_use_case_done_migration import make_at, schema_of

STEP = 20
BEFORE = str(STEP - 1)
NOW = str(store_module.SCHEMA_VERSION)
NEW_COLUMNS = ("brand",)
COLUMN = "brand TEXT NOT NULL DEFAULT 'generic' CHECK (length(brand) BETWEEN 1 AND 60)"


def add_projects(path):
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("INSERT INTO projects (code, name, health, health_reason) VALUES ('DEF', 'Other Programme', 'At risk', 'Late supplier')")
    con.execute("INSERT INTO milestones (id, project, name, source) VALUES ('ABC-M-001', 'ABC', 'Pilot live', 'test')")
    con.execute("INSERT INTO actions (id, project, description, raised, source) VALUES ('ABC-A-001', 'ABC', 'Send the matching rules', '2026-10-01', 'test')")
    con.close()


def project_columns(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("PRAGMA table_info(projects)").fetchall()
    finally:
        con.close()


def every_row(path, leave_out=()):
    """Every table's rows (meta and SQLite's own tables left out) in rowid order, without the columns in `leave_out`."""
    con = sqlite3.connect(str(path))
    try:
        out = {}
        for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name != 'meta' ORDER BY name").fetchall():
            kept = ", ".join(f'"{c[1]}"' for c in con.execute(f'PRAGMA table_info("{n}")') if c[1] not in leave_out)
            out[n] = con.execute(f'SELECT rowid, {kept} FROM "{n}" ORDER BY rowid').fetchall()
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

    def copies(self):
        return sorted((self.dir / "backups").glob("*-migrate.db")) if (self.dir / "backups").exists() else []

    def test_the_step_is_in_the_table_at_its_number_and_the_literal_and_the_table_agree(self):
        self.assertIn((STEP, store_module.migrate_brand), store_module.MIGRATIONS)
        self.assertEqual(store_module.BRAND_STEP, STEP)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))
        self.assertEqual(store_module.MIGRATIONS[-1][0], store_module.SCHEMA_VERSION)
        src = (SRC / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^SCHEMA_VERSION = (\d+)", src, re.M), [str(store_module.SCHEMA_VERSION)])

    def test_a_layout_19_file_opens_keeps_every_value_and_gets_generic(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        self.assertEqual(version(path), BEFORE)
        self.assertFalse(set(NEW_COLUMNS) & {c[1] for c in project_columns(path)})
        before = every_row(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)          # a migration is not a step: no Undo
            for code in ("ABC", "DEF"):
                self.assertEqual(s.read("projects", ref=code)["brand"], "generic")
        finally:
            s.close()
        after = every_row(path, NEW_COLUMNS)
        self.assertEqual({t: after[t] for t in before}, before, "no existing value changed")
        self.assertEqual(set(after) - {"use_case_milestones"}, set(before))      # row 1107 (layout 24) adds that table

    def test_a_safety_copy_is_taken_before_the_step_runs_and_it_is_the_old_layout(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        open_store(path, onedrive_roots=[]).close()
        copies = self.copies()
        self.assertEqual(len(copies), 1)
        self.assertEqual(version(copies[0]), BEFORE)
        self.assertFalse(set(NEW_COLUMNS) & {c[1] for c in project_columns(copies[0])})

    def test_no_copy_no_step_when_the_copy_cannot_be_made(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        was = dump(path)
        from clark import backup
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("Nothing was changed", str(e.exception))
        self.assertEqual(dump(path), was)
        self.assertEqual(version(path), BEFORE)

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        open_store(path, onedrive_roots=[]).close()
        shutil.rmtree(self.dir / "backups", ignore_errors=True)
        was = dump(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), [])

    def test_the_step_is_safe_to_run_twice(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_brand(con)
            con.execute("UPDATE projects SET brand = 'generic' WHERE code = 'ABC'")
            store_module.migrate_brand(con)
            con.execute("COMMIT")
        finally:
            con.close()
        con = sqlite3.connect(str(path))
        try:
            self.assertEqual(con.execute("SELECT brand FROM projects WHERE code = 'ABC'").fetchall(), [("generic",)])
        finally:
            con.close()

    def test_an_older_clark_refuses_the_migrated_file_and_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        open_store(path, onedrive_roots=[]).close()
        was, copies = dump(path), self.copies()
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("newer clark", str(e.exception))
        self.assertEqual(str(e.exception), store_module.NEWER_DATA)
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), copies, "an older clark takes no copy either")

    def test_an_older_clark_refuses_through_bring_up_to_date_too(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)
        con = connect(path)
        try:
            with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1):
                with self.assertRaises(Invalid) as e:
                    store_module.bring_up_to_date(con, path)
            self.assertEqual(str(e.exception), store_module.NEWER_DATA)
        finally:
            con.close()

    def test_a_layout_1_file_goes_through_every_step_and_ends_with_the_column(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)
        self.assertEqual([c[1] for c in project_columns(path)][-1], "brand")

    def test_a_brought_up_file_and_a_new_file_have_the_same_columns_in_the_same_order(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir))) / "clark.db"
        open_store(fresh, onedrive_roots=[]).close()
        self.assertEqual(project_columns(path), project_columns(fresh))
        self.assertEqual(set(schema_of(path)), set(schema_of(fresh)), "the same tables, indexes and triggers by name")

    def test_the_column_text_in_the_step_is_the_text_in_schema_sql(self):
        schema = (SRC / "clark" / "schema.sql").read_text(encoding="utf-8")
        squash = lambda text: re.sub(r"\s+", "", text)
        self.assertIn(squash(COLUMN), squash(re.sub(r"--[^\n]*", "", schema)))
        self.assertEqual(squash(store_module.BRAND_COLUMN), squash(COLUMN))

    def test_the_step_changes_no_other_table_index_or_trigger(self):
        path = make_at(self.dir, STEP - 1)
        keep = lambda d: {k: v for k, v in d.items() if k != ("table", "projects")}
        before = keep(schema_of(path))
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= STEP)):      # this step alone
            open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), str(STEP))
        self.assertEqual(keep(schema_of(path)), before)

    def test_a_step_that_fails_after_its_changes_rolls_back_and_the_second_open_migrates(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        was = every_row(path)

        def broken(con):
            store_module.migrate_brand(con)
            con.execute("SELECT nonsense FROM nowhere")
        table = tuple((n, broken if n == STEP else fn) for n, fn in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        self.assertEqual(version(path), BEFORE)
        self.assertFalse(set(NEW_COLUMNS) & {c[1] for c in project_columns(path)})
        self.assertEqual(every_row(path), was)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)

    def test_the_column_refuses_bad_values_at_the_database(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO projects (code, name) VALUES ('ABC', 'Example Programme')")
        try:
            for sql in ("UPDATE projects SET brand = ''", "UPDATE projects SET brand = '" + "x" * 61 + "'", "UPDATE projects SET brand = NULL"):
                with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                    con.execute(sql)
            con.execute("UPDATE projects SET brand = '" + "x" * 60 + "'")
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
