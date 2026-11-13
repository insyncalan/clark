"""Mutation audit of store.py's migration runner (migration_plan and migrate): the mutants no earlier test killed.
Each test names the change to store.py that it catches. Tests only; fictional data only.

Run: python3 dev/run_tests.py test_store_migrate_runner_mutants
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clark import store as store_module
from clark.store import Invalid, connect, migrate, open_store
from test_store_migration import make_v1, version

DANGLING = ("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) "
            "VALUES ('2026-10-01', 'ABC-A-001', 'change', 'dashboard', 'you', 999)")


class RunnerMutants(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_a_gap_in_the_middle_of_a_table_that_ends_right_is_refused(self):
        # Catches: dropping the "numbers run 2, 3, ..." half of the check in migration_plan (the end alone was tested).
        top = store_module.SCHEMA_VERSION
        for hole in (2, top // 2, top - 1):
            table = tuple((n, print) for n in range(2, top + 1) if n != hole)
            self.assertEqual(table[-1][0], top)
            with self.assertRaises(Invalid) as caught:
                store_module.migration_plan(1, table)
            self.assertIn("is missing a step", str(caught.exception))

    def test_a_table_that_starts_after_2_is_refused(self):
        top = store_module.SCHEMA_VERSION
        with self.assertRaises(Invalid):
            store_module.migration_plan(1, tuple((n, print) for n in range(3, top + 1)))

    def test_a_step_that_puts_a_dangling_row_right_is_not_refused(self):
        # Catches: "_violations(con) - before" becoming "!=" (fewer problems than before is not a new problem).
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute(DANGLING)
        con.close()

        def repairs(c):
            c.execute("DELETE FROM item_events WHERE undoes = 999")
        with mock.patch.object(store_module, "MIGRATIONS", ((2, store_module.migrate_to_2), (3, repairs))), \
                mock.patch.object(store_module, "SCHEMA_VERSION", 3):
            open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), "3")
        con = sqlite3.connect(str(path))
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM item_events WHERE undoes = 999").fetchone()[0], 0)
        finally:
            con.close()

    def test_a_version_that_is_not_a_number_is_left_alone_and_does_not_crash(self):
        # Catches: dropping the isdigit guard in migrate (int('abc') would raise a bare ValueError).
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE meta SET v = 'abc' WHERE k = 'schema_version'")
        con.close()
        ran = []
        con = connect(path)
        try:
            migrate(con, table=tuple((n, lambda c, n=n: ran.append(n)) for n in range(2, store_module.SCHEMA_VERSION + 1)))
            self.assertEqual(ran, [])
            self.assertEqual(con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "abc")
            self.assertFalse(con.in_transaction)
        finally:
            con.close()

    def test_foreign_keys_are_on_again_after_a_run_and_after_a_failure(self):
        # Catches: removing the PRAGMA foreign_keys = ON in migrate's finally (open_store hides it by switching them on itself).
        path = make_v1(self.dir)
        con = connect(path)
        try:
            migrate(con)
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)

            def boom(c):
                raise RuntimeError("forced")
            later = store_module.SCHEMA_VERSION + 1
            with mock.patch.object(store_module, "SCHEMA_VERSION", later):
                with self.assertRaises(RuntimeError):
                    migrate(con, table=(*store_module.MIGRATIONS, (later, boom)))
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertFalse(con.in_transaction)
        finally:
            con.close()


class GanttStepMutants(unittest.TestCase):
    """Step 19 (migrate_gantt_section_type): the two early exits."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = make_v1(self.dir)
        open_store(self.path, onedrive_roots=[]).close()
        self.con = sqlite3.connect(str(self.path), isolation_level=None)
        self.addCleanup(self.con.close)

    def test_a_table_that_already_takes_gantt_is_not_made_again(self):
        # Catches: removing the "already names 'gantt'" exit. A rebuild would drop an index the test adds; a skip keeps it.
        self.con.execute("CREATE INDEX marker_mut ON report_sections (project)")
        self.con.execute("BEGIN")
        store_module.migrate_gantt_section_type(self.con)
        self.con.execute("COMMIT")
        names = [r[0] for r in self.con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")]
        self.assertIn("marker_mut", names)

    def test_a_file_with_no_report_sections_table_gets_the_new_one(self):
        # Catches: the missing-table branch returning without making the table.
        self.con.execute("DROP TABLE report_sections")
        self.con.execute("BEGIN")
        store_module.migrate_gantt_section_type(self.con)
        self.con.execute("COMMIT")
        sql = self.con.execute("SELECT sql FROM sqlite_master WHERE name = 'report_sections'").fetchone()
        self.assertIsNotNone(sql)
        self.assertIn("'gantt'", sql[0])


if __name__ == "__main__":
    unittest.main()
