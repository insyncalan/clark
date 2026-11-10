"""Row 875: migration step 22, use_cases.owner and use_cases.owner_id (src/clark/store.py migrate_use_case_owner, guarded).

The step adds two columns at the end of use_cases (ALTER TABLE ... ADD COLUMN), so no table is made again, no existing value changes and
every existing use case has no owner (NULL). A safety copy is taken first by the runner. A second run changes nothing. An older clark
(layout 21) refuses a layout-22 file and changes nothing. Fictional data only.

Run: python3 dev/run_tests.py test_store_use_case_owner_migration
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

STEP = 22
BEFORE = str(STEP - 1)
NOW = str(store_module.SCHEMA_VERSION)
NEW_COLUMNS = ("owner", "owner_id")
COLUMNS = ("owner TEXT", "owner_id TEXT REFERENCES people(id)")


def add_use_cases(path):
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("INSERT INTO use_cases (id, project, ref, title, status, headline, source, archived) VALUES "
                "('ABC-U-001', 'ABC', '1.1', 'Invoice matching', 'On track', 'Live', 'test', 0)")
    con.execute("INSERT INTO use_cases (id, project, ref, title, status, headline, source, archived) VALUES "
                "('ABC-U-002', 'ABC', '1.2', 'Supplier onboarding', 'Flag', '', 'test', 1)")
    con.close()


def uc_columns(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("PRAGMA table_info(use_cases)").fetchall()
    finally:
        con.close()


def add_milestone_with_owner(path):
    """A milestone that has an owner: a step that touched milestones.owner would show here (the other tables are empty)."""
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("INSERT INTO milestones (id, project, name, owner, source) VALUES ('ABC-M-001', 'ABC', 'Go live', 'Carol Example', 'test')")
    con.close()


def every_row(path, leave_out=()):
    """Every row of every table; `leave_out` is (table, column) pairs to leave out, so only the columns the step adds are skipped."""
    con = sqlite3.connect(str(path))
    try:
        out = {}
        for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name != 'meta' ORDER BY name").fetchall():
            kept = ", ".join(f'"{c[1]}"' for c in con.execute(f'PRAGMA table_info("{n}")') if (n, c[1]) not in leave_out)
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
        self.assertIn((STEP, store_module.migrate_use_case_owner), store_module.MIGRATIONS)
        self.assertEqual(store_module.OWNER_STEP, STEP)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))
        src = (SRC / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^SCHEMA_VERSION = (\d+)", src, re.M), [str(store_module.SCHEMA_VERSION)])

    def test_a_populated_layout_20_file_opens_gains_both_columns_and_keeps_every_value(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        self.assertEqual(version(path), BEFORE)
        self.assertFalse(set(NEW_COLUMNS) & {c[1] for c in uc_columns(path)})
        before = every_row(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)          # a migration is not a step: no Undo
            self.assertEqual([tuple(r) for r in s.con.execute("SELECT id, owner, owner_id FROM use_cases ORDER BY id").fetchall()],
                             [("ABC-U-001", None, None), ("ABC-U-002", None, None)])
        finally:
            s.close()
        after = every_row(path, [("use_cases", c) for c in NEW_COLUMNS])
        self.assertEqual({t: after[t] for t in before}, before, "no existing value changed")
        self.assertEqual([c[1] for c in uc_columns(path)][-2:], list(NEW_COLUMNS))

    def test_a_safety_copy_is_taken_before_the_step_runs_and_it_is_the_old_layout(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        open_store(path, onedrive_roots=[]).close()
        copies = self.copies()
        self.assertEqual(len(copies), 1)
        self.assertEqual(version(copies[0]), BEFORE)
        self.assertFalse(set(NEW_COLUMNS) & {c[1] for c in uc_columns(copies[0])})

    def test_no_copy_no_step_when_the_copy_cannot_be_made(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        was = dump(path)
        from clark import backup
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        self.assertEqual(dump(path), was)
        self.assertEqual(version(path), BEFORE)

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        open_store(path, onedrive_roots=[]).close()
        shutil.rmtree(self.dir / "backups", ignore_errors=True)
        was = dump(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), [])

    def test_the_step_is_safe_to_run_twice_and_keeps_an_owner_already_set(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_use_case_owner(con)
            con.execute("UPDATE use_cases SET owner = 'Anna Example' WHERE id = 'ABC-U-001'")
            store_module.migrate_use_case_owner(con)
            con.execute("COMMIT")
        finally:
            con.close()
        con = sqlite3.connect(str(path))
        try:
            self.assertEqual(con.execute("SELECT owner, owner_id FROM use_cases WHERE id = 'ABC-U-001'").fetchall(), [("Anna Example", None)])
        finally:
            con.close()

    def test_an_older_clark_refuses_the_migrated_file_and_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        open_store(path, onedrive_roots=[]).close()
        was, copies = dump(path), self.copies()
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.NEWER_DATA)
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), copies, "an older clark takes no copy either")

    def test_a_layout_1_file_goes_through_every_step_and_ends_with_the_columns(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)
        self.assertEqual([c[1] for c in uc_columns(path)][-2:], list(NEW_COLUMNS))

    def test_a_brought_up_file_and_a_new_file_have_the_same_columns_in_the_same_order(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir))) / "clark.db"
        open_store(fresh, onedrive_roots=[]).close()
        self.assertEqual(uc_columns(path), uc_columns(fresh))
        self.assertEqual(set(schema_of(path)), set(schema_of(fresh)), "the same tables, indexes and triggers by name")

    def test_the_column_text_in_the_step_is_the_text_in_schema_sql(self):
        schema = re.sub(r"--[^\n]*", "", (SRC / "clark" / "schema.sql").read_text(encoding="utf-8"))
        squash = lambda text: re.sub(r"\s+", "", text)
        table = squash(re.search(r"CREATE TABLE IF NOT EXISTS use_cases \((.*?)\n\);", schema, re.S).group(1))
        self.assertTrue(table.endswith(squash(",".join(COLUMNS))), table[-80:])
        self.assertEqual([squash(c) for c in store_module.OWNER_COLUMNS], [squash(c) for c in COLUMNS])

    def test_the_step_changes_no_other_table_index_or_trigger(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        add_milestone_with_owner(path)
        before = every_row(path)
        self.assertEqual(len(before["milestones"]), 1)
        open_store(path, onedrive_roots=[]).close()
        after = every_row(path, [("use_cases", c) for c in NEW_COLUMNS])
        for t in before:
            if t not in ("meta",):
                self.assertEqual(after[t], before[t], t)
        self.assertEqual(set(after), set(before))


if __name__ == "__main__":
    unittest.main()
