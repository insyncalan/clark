"""#115: the people migration step (store.migrate_people, src/clark/schema_v8.sql), guarded.

Run: python3 dev/run_tests.py test_people_migrate
The step is entry 8 of MIGRATIONS (the number is set finally at merge). Fictional data only.
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT
from clark import store as store_module
from clark.store import Invalid, connect, migrate, open_store

V1 = ROOT / "tests" / "fixtures" / "schema-v1.sql"
OWNER_TABLES = ("actions", "raid", "milestones", "workstreams", "decisions")


def make_v1(folder):
    path = Path(folder) / "clark.db"
    con = sqlite3.connect(str(path), isolation_level=None)
    con.executescript(V1.read_text(encoding="utf-8"))
    for k, v in (("schema_version", "1"), ("created_at", "2026-10-01"), ("device", "d1"), ("db_id", "i1"), ("role", "owner")):
        con.execute("INSERT INTO meta (k, v) VALUES (?, ?)", (k, v))
    con.execute("INSERT INTO projects (code, name) VALUES ('ABC', 'Example Programme')")
    con.close()
    return path


def run_step(path):
    con = connect(path)
    try:
        con.execute("BEGIN IMMEDIATE")
        store_module.migrate_people(con)
        con.execute("COMMIT")
    finally:
        con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = make_v1(self.dir)
        open_store(self.path, onedrive_roots=[]).close()          
        self.con = connect(self.path)
        self.addCleanup(self.con.close)

    def cols(self, table):
        return [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]


class PeopleStep(Base):
    def test_the_table_and_the_five_links(self):
        con = self.con
        con.execute("BEGIN IMMEDIATE")
        store_module.migrate_people(con)
        con.execute("COMMIT")
        self.assertEqual(self.cols("people"), ["id", "name", "email", "organisation", "role", "label", "aliases", "kind",
                                               "needs_details", "archived", "source", "updated_at"])
        for table in OWNER_TABLES:
            self.assertIn("owner_id", self.cols(table), table)

    def test_idempotent(self):
        run_step(self.path)
        before = self.con.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
        run_step(self.path)
        run_step(self.path)
        self.assertEqual(self.con.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall(), before)

    def test_creates_no_people_and_leaves_existing_owner_text_and_links_null(self):
        self.con.execute("INSERT INTO actions (id, project, description, owner, raised, source) VALUES ('ABC-A-001', 'ABC', 'Do it', 'Sam Reed', '2026-10-01', 'test')")
        self.con.execute("INSERT INTO workstreams (id, project, name, lead, source, created) VALUES ('ABC-W-001', 'ABC', 'Build', 'Jo Park', 'test', '2026-10-01')")
        run_step(self.path)
        self.assertEqual(self.con.execute("SELECT count(*) FROM people").fetchone()[0], 0)
        self.assertEqual(tuple(self.con.execute("SELECT owner, owner_id FROM actions").fetchone()), ("Sam Reed", None))
        self.assertEqual(tuple(self.con.execute("SELECT lead, owner_id FROM workstreams").fetchone()), ("Jo Park", None))

    def test_the_foreign_keys_stay_clean(self):
        run_step(self.path)
        self.assertEqual(self.con.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_a_link_must_point_at_a_person(self):
        run_step(self.path)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("INSERT INTO actions (id, project, description, owner, raised, source) VALUES ('ABC-A-001', 'ABC', 'Do it', 'Sam Reed', '2026-10-01', 'test')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("UPDATE actions SET owner_id = 'P-009'")
        self.con.execute("INSERT INTO people (id, name, source) VALUES ('P-001', 'Sam Reed', 'test')")
        self.con.execute("UPDATE actions SET owner_id = 'P-001'")

    def test_the_table_rules(self):
        run_step(self.path)
        ins = "INSERT INTO people (id, name, email, label, kind, source) VALUES (?, ?, ?, ?, ?, 'test')"
        self.con.execute(ins, ("P-001", "Sam Reed", "a@x.example", "Harbour team", "person"))
        bad = [("P-1", "A", None, None, "person"), ("P-002", "  ", None, None, "person"), ("P-002", "A", "A@x.example", None, "person"),
               ("P-002", "A", None, "x" * 31, "person"), ("P-002", "A", None, None, "robot"),
               ("P-002", "A", "a@x.example", None, "person"),           # the same email twice
               ("P-001", "A", None, None, "person")]                     # the same id twice
        for row in bad:
            with self.assertRaises(sqlite3.IntegrityError, msg=row):
                self.con.execute(ins, row)
        self.con.execute(ins, ("P-002", "Sam Reed", None, None, "group"))      # a name may be shared; a missing email is not a clash
        self.con.execute(ins, ("P-003", "Jo Park", None, None, "person"))      # two people with no email do not clash

    def test_needs_details_and_archived_are_flags(self):
        run_step(self.path)
        for col in ("needs_details", "archived"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.con.execute(f"INSERT INTO people (id, name, source, {col}) VALUES ('P-001', 'A', 'test', 2)")

    def test_people_is_not_in_the_publish_inputs(self):
        self.assertNotIn("people", store_module.PUBLISH_TABLES)           # a person's name and email never reach a published file


class InTheOrderedTable(Base):
    """The step as entry 8 of the real table, and what a new file looks like beside an upgraded one."""

    def test_the_step_is_registered_as_8_and_the_version_matches(self):
        self.assertIn((8, store_module.migrate_people), store_module.MIGRATIONS)
        self.assertEqual(store_module.SCHEMA_VERSION, 8)
        self.assertEqual(max(n for n, _ in store_module.MIGRATIONS), store_module.SCHEMA_VERSION)

    def test_a_version_1_file_with_data_moves_up_to_the_current_version(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        path = make_v1(folder)
        c = sqlite3.connect(str(path), isolation_level=None)
        c.execute("INSERT INTO actions (id, project, description, owner, raised, source) VALUES ('ABC-A-001', 'ABC', 'Do it', 'Sam Reed', '2026-10-01', 'test')")
        c.close()
        open_store(path, onedrive_roots=[]).close()
        c = sqlite3.connect(str(path))
        self.addCleanup(c.close)
        self.assertEqual(c.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        self.assertEqual(c.execute("SELECT owner, owner_id FROM actions").fetchone(), ("Sam Reed", None))
        self.assertEqual(c.execute("SELECT count(*) FROM people").fetchone()[0], 0)

    def test_a_version_7_file_moves_to_8_and_a_second_open_changes_nothing(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        path = make_v1(folder)
        before7 = tuple(m for m in store_module.MIGRATIONS if m[0] < 8)
        with mock.patch.object(store_module, "SCHEMA_VERSION", 7), mock.patch.object(store_module, "MIGRATIONS", before7):
            open_store(path, onedrive_roots=[]).close()
        c = connect(path)
        self.addCleanup(c.close)
        self.assertEqual(c.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "7")
        self.assertNotIn("people", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")])
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(c.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "8")
        after = c.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(c.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall(), after)

    def test_an_upgraded_file_and_a_new_file_have_the_same_people_and_link_columns(self):
        fresh = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, fresh, True)
        open_store(fresh / "new.db", onedrive_roots=[]).close()
        new = connect(fresh / "new.db")
        self.addCleanup(new.close)
        for table in ("people",) + OWNER_TABLES:
            mine = [(r[1], r[2], r[3], r[4]) for r in new.execute(f"PRAGMA table_info({table})")]
            theirs = [(r[1], r[2], r[3], r[4]) for r in self.con.execute(f"PRAGMA table_info({table})")]
            self.assertEqual(mine, theirs, table)

    def test_an_older_clark_refuses_the_newer_file(self):
        with mock.patch.object(store_module, "SCHEMA_VERSION", 7), mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] < 8)):
            with self.assertRaises(Invalid) as caught:
                open_store(self.path, onedrive_roots=[])
        self.assertTrue(str(caught.exception))

    def test_a_failure_in_the_step_rolls_everything_back(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        path = make_v1(folder)

        def breaks(con):
            store_module.migrate_people(con)
            raise sqlite3.IntegrityError("boom")
        table = tuple(m for m in store_module.MIGRATIONS if m[0] < 8) + ((8, breaks),)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        c = connect(path)
        self.addCleanup(c.close)
        self.assertEqual(c.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "1")
        self.assertNotIn("people", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")])
        self.assertNotIn("owner_id", [r[1] for r in c.execute("PRAGMA table_info(actions)")])


if __name__ == "__main__":
    unittest.main()
