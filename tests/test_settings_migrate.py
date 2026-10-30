"""#47: the settings migration step (store.migrate_settings, src/clark/schema_v3.sql), guarded: the ask switch's one row.

Run: python3 dev/run_tests.py test_settings_migrate
The step is wired as step 3 (the next free number after main's 2; whichever of this and #120's step lands second renumbers). SettingsStep calls
it directly; InTheOrderedTable goes through open_store. Fictional data only.
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT
from clark import store as store_module
from clark.store import Invalid, connect, migration_plan, open_store

V1 = ROOT / "tests" / "fixtures" / "schema-v1.sql"


def make_v1(folder):
    path = Path(folder) / "clark.db"
    con = sqlite3.connect(str(path), isolation_level=None)
    con.executescript(V1.read_text(encoding="utf-8"))
    for k, v in (("schema_version", "1"), ("created_at", "2026-10-01"), ("device", "d1"), ("db_id", "i1"), ("role", "owner")):
        con.execute("INSERT INTO meta (k, v) VALUES (?, ?)", (k, v))
    con.execute("INSERT INTO projects (code, name) VALUES ('ABC', 'Example Programme')")
    con.execute("INSERT INTO projects (code, name) VALUES ('DEF', 'Other Programme')")
    con.close()
    return path


def run_step(path):
    con = connect(path)
    try:
        con.execute("BEGIN IMMEDIATE")
        store_module.migrate_settings(con)
        con.execute("COMMIT")
    finally:
        con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = make_v1(self.dir)
        with mock.patch.object(store_module, "SCHEMA_VERSION", 2), mock.patch.object(store_module, "MIGRATIONS", store_module.MIGRATIONS[:1]):
            open_store(self.path, onedrive_roots=[]).close()      # to version 2, as the last release left it: no settings step yet
        self.con = connect(self.path)
        self.addCleanup(self.con.close)

    def cols(self, table):
        return [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]

    def version(self):
        return self.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0]


class SettingsStep(Base):
    def test_the_table_and_the_one_row_start_on(self):
        run_step(self.path)
        self.assertEqual(self.cols("app_settings"), ["id", "ask_enabled", "updated_at"])
        self.assertEqual(tuple(self.con.execute("SELECT id, ask_enabled FROM app_settings").fetchall()[0]), (1, 1))
        self.assertEqual(self.con.execute("SELECT count(*) FROM app_settings").fetchone()[0], 1)

    def test_nothing_else_changes(self):
        before = [tuple(r) for r in self.con.execute("SELECT * FROM projects ORDER BY code")]
        run_step(self.path)
        self.assertEqual([tuple(r) for r in self.con.execute("SELECT * FROM projects ORDER BY code")], before)

    def test_idempotent(self):
        run_step(self.path)
        before = self.con.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
        rows = [tuple(r) for r in self.con.execute("SELECT * FROM app_settings")]
        run_step(self.path)
        run_step(self.path)
        self.assertEqual(self.con.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall(), before)
        self.assertEqual([tuple(r) for r in self.con.execute("SELECT * FROM app_settings")], rows)

    def test_a_second_run_keeps_a_switch_that_was_turned_off(self):
        run_step(self.path)
        self.con.execute("UPDATE app_settings SET ask_enabled = 0")
        run_step(self.path)
        self.assertEqual(self.con.execute("SELECT ask_enabled FROM app_settings").fetchone()[0], 0)

    def test_the_table_rules(self):
        run_step(self.path)
        for bad in ("UPDATE app_settings SET ask_enabled = 2", "UPDATE app_settings SET ask_enabled = -1",
                    "UPDATE app_settings SET ask_enabled = NULL", "UPDATE app_settings SET id = 2",
                    "INSERT INTO app_settings (id) VALUES (2)", "INSERT INTO app_settings (id) VALUES (1)"):
            with self.assertRaises(sqlite3.IntegrityError, msg=bad):
                self.con.execute(bad)

    def test_the_foreign_keys_stay_clean(self):
        run_step(self.path)
        self.assertEqual(self.con.execute("PRAGMA foreign_key_check").fetchall(), [])


class InTheOrderedTable(Base):
    """The step as it is wired: step 3 in MIGRATIONS, SCHEMA_VERSION 3. The named migration test (#47) is here."""

    def make_v2_with_data(self):
        """A version 2 file (as the last release made it) with a project, an action and a milestone, none of it settings."""
        con = connect(self.path)
        con.execute("INSERT INTO milestones (id, project, name, source) VALUES ('ABC-M-001', 'ABC', 'Go live', 'test')")
        con.execute("INSERT INTO actions (id, project, description, raised, source) VALUES ('ABC-A-001', 'ABC', 'Send the plan', '2026-10-01', 'test')")
        con.close()

    def test_an_old_version_2_file_migrates_and_keeps_its_data_and_its_settings(self):
        """Named test: version 2 to 3 keeps every row and every existing value; the new row and column start at their defaults."""
        self.make_v2_with_data()
        self.assertEqual(self.version(), "2")
        before = {t: [tuple(r) for r in self.con.execute(f"SELECT * FROM {t} ORDER BY 1")] for t in ("milestones", "actions")}
        projects = [tuple(r) for r in self.con.execute("SELECT code, name, active, archived, layout, health FROM projects ORDER BY code")]
        open_store(self.path, onedrive_roots=[]).close()
        self.assertEqual(self.version(), str(store_module.SCHEMA_VERSION))
        self.assertEqual(self.version(), "3")
        self.assertEqual({t: [tuple(r) for r in self.con.execute(f"SELECT * FROM {t} ORDER BY 1")] for t in ("milestones", "actions")}, before)
        self.assertEqual([tuple(r) for r in self.con.execute("SELECT code, name, active, archived, layout, health FROM projects ORDER BY code")], projects)
        self.assertEqual(self.con.execute("SELECT ask_enabled FROM app_settings").fetchone()[0], 1)

    def test_the_settings_a_person_chose_survive_a_later_open(self):
        open_store(self.path, onedrive_roots=[]).close()
        self.con.execute("UPDATE app_settings SET ask_enabled = 0")
        open_store(self.path, onedrive_roots=[]).close()
        self.assertEqual(self.con.execute("SELECT ask_enabled FROM app_settings").fetchone()[0], 0)

    def test_a_second_open_changes_nothing(self):
        open_store(self.path, onedrive_roots=[]).close()
        before = (self.con.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall(),
                  [tuple(r) for r in self.con.execute("SELECT * FROM app_settings")], [tuple(r) for r in self.con.execute("SELECT * FROM projects")])
        open_store(self.path, onedrive_roots=[]).close()
        self.assertEqual((self.con.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall(),
                          [tuple(r) for r in self.con.execute("SELECT * FROM app_settings")], [tuple(r) for r in self.con.execute("SELECT * FROM projects")]), before)

    def test_a_version_1_file_moves_up_through_2_to_3(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        path = make_v1(folder)
        open_store(path, onedrive_roots=[]).close()
        c = sqlite3.connect(str(path))
        self.addCleanup(c.close)
        self.assertEqual(c.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "3")
        self.assertEqual(c.execute("SELECT ask_enabled FROM app_settings").fetchone()[0], 1)

    def test_the_table_has_no_gap_and_the_runner_refuses_one(self):
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], [2, 3])
        gap = ((2, store_module.migrate_to_2), (4, store_module.migrate_settings))
        with mock.patch.object(store_module, "SCHEMA_VERSION", 4):
            with self.assertRaises(Invalid) as caught:
                migration_plan(2, gap)
        self.assertIn("missing a step", str(caught.exception))

    def test_an_older_clark_refuses_the_newer_file(self):
        open_store(self.path, onedrive_roots=[]).close()
        with mock.patch.object(store_module, "SCHEMA_VERSION", 2), mock.patch.object(store_module, "MIGRATIONS", store_module.MIGRATIONS[:1]):
            with self.assertRaises(Invalid) as caught:
                open_store(self.path, onedrive_roots=[])
        self.assertIn("newer clark", str(caught.exception))
        self.assertEqual(self.version(), "3")

    def test_a_failure_in_the_step_rolls_everything_back(self):
        def breaks(con):
            store_module.migrate_settings(con)
            raise sqlite3.IntegrityError("boom")
        table = ((2, store_module.migrate_to_2), (3, breaks))
        with mock.patch.object(store_module, "MIGRATIONS", table):
            with self.assertRaises(Invalid):
                open_store(self.path, onedrive_roots=[])
        self.assertEqual(self.version(), "2")
        self.assertNotIn("app_settings", [r[0] for r in self.con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")])

    def test_a_safety_copy_is_made_before_the_step_runs(self):
        open_store(self.path, onedrive_roots=[]).close()
        copies = list((self.path.parent / "backups").rglob("*"))
        self.assertTrue([p for p in copies if p.is_file()], copies)


class WhenTheStepIsWired(unittest.TestCase):
    """The step is wired: a new file made from schema.sql and an old file brought up by the steps have the same settings shape.
    It fails (never skips) if the step is taken out of MIGRATIONS."""

    def test_a_new_file_and_a_migrated_file_agree(self):
        self.assertIn(store_module.migrate_settings, [fn for _, fn in store_module.MIGRATIONS])
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        fresh = open_store(folder / "new.db", onedrive_roots=[])
        (folder / "old").mkdir()
        old = make_v1(folder / "old")
        migrated = open_store(old, onedrive_roots=[])
        self.addCleanup(fresh.close)
        self.addCleanup(migrated.close)
        for table in ("app_settings", "projects"):
            a = [tuple(r) for r in fresh.con.execute(f"PRAGMA table_info({table})")]
            b = [tuple(r) for r in migrated.con.execute(f"PRAGMA table_info({table})")]
            self.assertEqual(sorted(a), sorted(b), table)
        self.assertEqual(fresh.con.execute("SELECT count(*) FROM app_settings").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
