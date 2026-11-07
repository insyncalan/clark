"""#171: the migration step that gives every project its own "not reviewed after N days" (projects.review_after_days, src/clark/store.py, guarded).

The step is ALTER TABLE ... ADD COLUMN with a default of 14 and the CHECK of schema.sql, so no table is made again and no frozen schema
file is needed. A file from before the step gets 14 on every project that is in it; a new file has the column from schema.sql. The step
is step 14 of MIGRATIONS (STEP below); if another step lands first, renumbering is: STEP here, SCHEMA_VERSION's line and REVIEW_DAYS_STEP in store.py. Fictional data only.

Run: python3 dev/run_tests.py test_store_review_days_migration
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT
from clark import backup, store as store_module
from clark.store import Invalid, connect, open_store
from test_store_migration import make_v1, version
from test_store_use_case_done_migration import every_row, make_at, schema_of

STEP = 14                                           # this step's number (see the docstring)
BEFORE = str(STEP - 1)                              # the version this step brings a file from
NOW = str(store_module.SCHEMA_VERSION)              # the version a plain open brings a file to (this step and any later one)


def add_projects(path):
    """Two more projects and their children, written raw as an old clark would have left them (the file already has ABC)."""
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("INSERT INTO projects (code, name, health, week_ending, layout) VALUES ('DEF', 'Other Programme', 'At risk', '2026-10-30', 'spine')")
    con.execute("INSERT INTO projects (code, name, active, archived) VALUES ('GHI', 'Old Programme', 0, 1)")
    con.execute("INSERT INTO actions (id, project, description, raised, source) VALUES ('DEF-A-001', 'DEF', 'Send the plan', '2026-10-01', 'test')")
    con.close()


def project_columns(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("PRAGMA table_info(projects)").fetchall()
    finally:
        con.close()


def days(path):
    con = sqlite3.connect(str(path))
    try:
        return dict(con.execute("SELECT code, review_after_days FROM projects ORDER BY code").fetchall())
    finally:
        con.close()


def dump(path):
    con = sqlite3.connect(str(path))
    try:
        return list(con.iterdump())
    finally:
        con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def copies(self):
        return sorted((self.dir / "backups").glob("*-migrate.db")) if (self.dir / "backups").exists() else []


class TheNumber(Base):
    def test_the_step_is_in_the_table_at_its_number_and_the_table_has_no_gap(self):
        self.assertIn((STEP, store_module.migrate_review_after_days), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_the_number_is_written_once_beside_its_step(self):
        src = (ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^REVIEW_DAYS_STEP = (\d+)", src, re.M), [str(STEP)])
        self.assertEqual(re.findall(r"\(REVIEW_DAYS_STEP, migrate_review_after_days\)", src), ["(REVIEW_DAYS_STEP, migrate_review_after_days)"])
        self.assertEqual(store_module.REVIEW_DAYS_STEP, STEP)
        self.assertEqual(len(re.findall(r"^SCHEMA_VERSION = ", src, re.M)), 1)

    def test_the_step_changes_no_other_table_index_or_trigger(self):
        path = make_at(self.dir, STEP - 1)
        before = {k: v for k, v in schema_of(path).items() if k != ("table", "projects")}
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= STEP)):
            open_store(path, onedrive_roots=[]).close()          # this step only: a later step (#269, 15) changes publications
        after = {k: v for k, v in schema_of(path).items() if k != ("table", "projects")}
        self.assertEqual(after, before)


class Migrating(Base):
    def test_a_version_11_file_gives_every_project_14_keeps_every_row_and_takes_the_new_version(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        self.assertEqual(version(path), BEFORE)
        self.assertNotIn("review_after_days", [c[1] for c in project_columns(path)])
        before = every_row(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)        # a migration is not a step
        finally:
            s.close()
        self.assertEqual(days(path), {"ABC": 14, "DEF": 14, "GHI": 14})
        after = every_row(path)
        self.assertEqual({t: after[t] for t in before}, before)
        self.assertEqual(after["projects"], before["projects"], "a project's other columns are as they were (every_row leaves the new one out)")
        self.assertEqual(len(self.copies()), 1)

    def test_a_version_1_file_goes_through_every_step_and_ends_with_the_column(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)
        self.assertEqual(days(path), {"ABC": 14})

    def test_the_safety_copy_is_taken_first_and_holds_the_old_version_without_the_column(self):
        path = make_at(self.dir, STEP - 1)
        add_projects(path)
        found = []
        real = store_module.migrate_review_after_days

        def look_first(con):
            found.extend(self.copies())                                       # the copy is already on disk when the step runs
            real(con)
        table = tuple((n, look_first if n == STEP else fn) for n, fn in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            open_store(path, onedrive_roots=[]).close()
        self.assertEqual(len(found), 1)
        (copy,) = self.copies()
        self.assertEqual(version(copy), BEFORE)
        self.assertNotIn("review_after_days", [c[1] for c in project_columns(copy)])

    def test_a_failed_copy_refuses_the_open_and_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        was = dump(path)
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("Nothing was changed", str(e.exception))
        self.assertEqual(dump(path), was)
        self.assertEqual(version(path), BEFORE)

    def test_a_brought_up_file_and_a_new_file_have_the_same_project_columns_in_the_same_order(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir)))
        open_store(fresh / "clark.db", onedrive_roots=[]).close()
        self.assertEqual(project_columns(path), project_columns(fresh / "clark.db"))
        self.assertIn(("review_after_days", "INTEGER", 1, "14", 0), [c[1:] for c in project_columns(path)])   # a later step (row 926, 18) adds the Gantt columns after it
        self.assertEqual(set(schema_of(path)), set(schema_of(fresh / "clark.db")), "the same tables, indexes and triggers by name")

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        for old in self.copies():
            old.unlink()
        was = dump(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), [])

    def test_the_step_is_safe_to_run_twice_and_keeps_a_changed_value(self):
        path = make_at(self.dir, STEP - 1)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_review_after_days(con)
            con.execute("UPDATE projects SET review_after_days = 30")
            store_module.migrate_review_after_days(con)                  # the column is there: nothing happens, the 30 stays
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(days(path), {"ABC": 30})

    def test_the_step_on_a_new_database_does_nothing(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        was = dump(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_review_after_days(con)
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(dump(path), was)


class TheColumnRefusesBadValues(Base):
    """The CHECK is the last guard, whichever route a value comes by: a brought-up file and a new file hold the same one."""

    def check(self, path):
        con = sqlite3.connect(str(path), isolation_level=None)
        try:
            for good in (1, 14, 365, "30"):                              # a text of digits is turned into a whole number by the column
                con.execute("UPDATE projects SET review_after_days = ? WHERE code = 'ABC'", (good,))
                self.assertEqual(con.execute("SELECT review_after_days, typeof(review_after_days) FROM projects").fetchone(),
                                 (int(good), "integer"))
            for bad in (0, -1, 366, 10 ** 12, 14.5, "abc", "", None, "14.5", b"14"):
                with self.subTest(bad=bad), self.assertRaises(sqlite3.IntegrityError):
                    con.execute("UPDATE projects SET review_after_days = ? WHERE code = 'ABC'", (bad,))
            self.assertEqual(con.execute("SELECT review_after_days FROM projects").fetchone()[0], 30)
        finally:
            con.close()

    def test_a_brought_up_file_refuses_them(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        self.check(path)

    def test_a_new_file_refuses_them(self):
        path = self.dir / "clark.db"
        s = open_store(path, onedrive_roots=[])
        with s.step("dashboard", "Demo User") as st:
            st.create("projects", {"code": "ABC", "name": "Example Programme"})
        s.close()
        self.check(path)


if __name__ == "__main__":
    unittest.main()
