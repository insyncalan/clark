"""#709: the migration step that gives a use case its commitment flag (use_cases.commitment, src/clark/store.py, guarded).

The step is ALTER TABLE ... ADD COLUMN of a nullable TEXT column with no default and no CHECK (the words are store.COMMITMENTS, so a fourth
is no layout step). A file from 1.0.0 (version 15) keeps every use case with no flag, a new file has the column from schema.sql. The step is
step 16 of MIGRATIONS (STEP below). Fictional data only.

Run: python3 dev/run_tests.py test_store_commitment_migration
"""
import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clark import backup, store as store_module
from clark.store import Invalid, connect, open_store
from test_store_migration import make_v1, version
from test_store_use_case_done_migration import every_row, make_at, schema_of

STEP = 16
BEFORE = str(STEP - 1)                              # the 1.0.0 layout
NOW = str(store_module.SCHEMA_VERSION)


def add_use_cases(path):
    """Use cases written raw as 1.0.0 left them: one shown, one hidden, one archived."""
    con = sqlite3.connect(str(path), isolation_level=None)
    for n, (ref, title, status, shown, archived) in enumerate((("1.1", "Invoice matching", "On track", 1, 0),
                                                                ("1.2", "Supplier portal", "Flag", 0, 0),
                                                                ("1.3", "Retired idea", "Done", 1, 1)), 1):
        con.execute("INSERT INTO use_cases (id, project, ref, title, status, headline, standing, sort_order, client_visible, archived, source, updated_at) "
                    "VALUES (?, 'ABC', ?, ?, ?, 'A headline', '<p>Standing</p>', ?, ?, ?, 'test', '2026-10-30 09:00:00')",
                    (f"ABC-U-00{n}", ref, title, status, n, shown, archived))
    con.close()


def use_case_columns(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("PRAGMA table_info(use_cases)").fetchall()
    finally:
        con.close()


def flags(path):
    con = sqlite3.connect(str(path))
    try:
        return dict(con.execute("SELECT id, commitment FROM use_cases ORDER BY id").fetchall())
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
        self.assertIn((STEP, store_module.migrate_use_case_commitment), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_the_step_changes_no_other_table_index_or_trigger(self):
        path = make_at(self.dir, STEP - 1)
        before = {k: v for k, v in schema_of(path).items() if k != ("table", "use_cases")}
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= STEP)):     # this step alone (a later one, row 811's, changes actions and raid)
            open_store(path, onedrive_roots=[]).close()
        after = {k: v for k, v in schema_of(path).items() if k != ("table", "use_cases")}
        self.assertEqual(after, before)

    def test_the_words_are_the_owners_and_in_one_tuple(self):
        self.assertEqual(store_module.COMMITMENTS, ("Planned 2026", "Committed", "Planned 2027"))
        self.assertEqual(store_module.ALLOWED[("use_cases", "commitment")], store_module.COMMITMENTS)


class Migrating(Base):
    def test_a_1_0_0_file_with_use_cases_migrates_to_16_keeps_every_row_with_no_flag_and_takes_a_copy(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        self.assertEqual(version(path), BEFORE)
        self.assertNotIn("commitment", [c[1] for c in use_case_columns(path)])
        before = every_row(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)        # a migration is not a step
        finally:
            s.close()
        self.assertEqual(flags(path), {"ABC-U-001": None, "ABC-U-002": None, "ABC-U-003": None})
        after = every_row(path)
        self.assertEqual({t: after[t] for t in before}, before)
        self.assertEqual(len(after["use_cases"]), 3)
        self.assertEqual(len(self.copies()), 1)

    def test_a_version_1_file_goes_through_every_step_and_ends_with_the_column(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)
        self.assertIn("commitment", [c[1] for c in use_case_columns(path)])

    def test_the_safety_copy_is_taken_first_and_holds_the_old_version_without_the_column(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        found = []
        real = store_module.migrate_use_case_commitment

        def look_first(con):
            found.extend(self.copies())
            real(con)
        table = tuple((n, look_first if n == STEP else fn) for n, fn in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            open_store(path, onedrive_roots=[]).close()
        self.assertEqual(len(found), 1)
        (copy,) = self.copies()
        self.assertEqual(version(copy), BEFORE)
        self.assertNotIn("commitment", [c[1] for c in use_case_columns(copy)])

    def test_a_failed_copy_refuses_the_open_and_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        was = dump(path)
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("Nothing was changed", str(e.exception))
        self.assertEqual(dump(path), was)
        self.assertEqual(version(path), BEFORE)

    def test_a_brought_up_file_and_a_new_file_have_the_same_use_case_table(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir)))
        open_store(fresh / "clark.db", onedrive_roots=[]).close()
        self.assertEqual(use_case_columns(path), use_case_columns(fresh / "clark.db"))
        self.assertEqual(use_case_columns(path)[-1][1:], ("commitment", "TEXT", 0, None, 0))
        self.assertEqual(schema_of(path, "use_cases"), schema_of(fresh / "clark.db", "use_cases"))
        self.assertEqual(set(schema_of(path)), set(schema_of(fresh / "clark.db")))

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        open_store(path, onedrive_roots=[]).close()
        for old in self.copies():
            old.unlink()
        was = dump(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), [])

    def test_the_step_is_safe_to_run_twice_and_keeps_a_set_flag(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_use_case_commitment(con)
            con.execute("UPDATE use_cases SET commitment = 'Committed' WHERE id = 'ABC-U-001'")
            store_module.migrate_use_case_commitment(con)            # the column is there: nothing happens, the flag stays
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(flags(path), {"ABC-U-001": "Committed", "ABC-U-002": None, "ABC-U-003": None})

    def test_the_step_on_a_new_database_does_nothing(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        was = dump(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_use_case_commitment(con)
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(dump(path), was)

    def test_an_older_clark_refuses_the_migrated_file_and_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        was = dump(path)
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("newer clark", str(e.exception))
        self.assertEqual(dump(path), was)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def integrity(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


class FailingCommit:
    """A connection that does everything the real one does except that COMMIT fails (the disk, a lock): the real one is untouched."""

    def __init__(self, con):
        self._con = con

    def __getattr__(self, name):
        return getattr(self._con, name)

    def execute(self, sql, *args):
        if sql.strip().upper() == "COMMIT":
            raise sqlite3.OperationalError("disk I/O error")
        return self._con.execute(sql, *args)


class AFailureAtTheStepLeavesTheOldFileUsable(Base):
    """The step fails after its ALTER (or the commit fails): the 1.0.0 file is whole, at 15, with no column, and opens fine later."""

    def broken_step(self):
        def step(con):
            store_module.migrate_use_case_commitment(con)            # the ALTER is done ...
            raise RuntimeError("the step stopped")                   # ... and then the step fails
        return tuple((n, step if n == STEP else fn) for n, fn in store_module.MIGRATIONS)

    def assert_still_the_old_file(self, path, rows, text):
        self.assertIn("Nothing was changed", text)
        self.assertEqual(version(path), BEFORE)
        self.assertEqual(integrity(path), "ok")
        self.assertNotIn("commitment", [c[1] for c in use_case_columns(path)])
        self.assertEqual(every_row(path), rows)
        (copy,) = self.copies()                                   # the safety copy was taken first, and is a whole version-15 database
        self.assertEqual(version(copy), BEFORE)
        self.assertEqual(integrity(copy), "ok")
        self.assertNotIn("commitment", [c[1] for c in use_case_columns(copy)])
        self.assertEqual(every_row(copy), rows)

    def assert_a_second_open_migrates(self, path, rows):
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            s.close()
        self.assertEqual(integrity(path), "ok")
        self.assertEqual(flags(path), {"ABC-U-001": None, "ABC-U-002": None, "ABC-U-003": None})
        after = every_row(path)
        self.assertEqual({t: after[t] for t in rows}, rows)
        self.assertEqual(use_case_columns(path)[-1][1:], ("commitment", "TEXT", 0, None, 0))

    def test_a_step_that_fails_after_its_alter_rolls_back_and_the_second_open_migrates(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        rows = every_row(path)
        with mock.patch.object(store_module, "MIGRATIONS", self.broken_step()):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.MIGRATE_FAILED)
        self.assert_still_the_old_file(path, rows, str(e.exception))
        self.assert_a_second_open_migrates(path, rows)

    def test_a_failure_in_the_step_is_the_plain_refusal_for_bring_up_to_date_too(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        rows = every_row(path)
        con = connect(path)
        try:
            with mock.patch.object(store_module, "MIGRATIONS", self.broken_step()):
                with self.assertRaises(Invalid) as e:
                    store_module.bring_up_to_date(con, path, [])
            self.assertFalse(con.in_transaction)
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)         # switched back on after the failure
        finally:
            con.close()
        self.assert_still_the_old_file(path, rows, str(e.exception))
        self.assert_a_second_open_migrates(path, rows)

    def test_a_commit_that_fails_leaves_the_old_file_and_the_second_open_migrates(self):
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        rows = every_row(path)
        con = connect(path)
        try:
            with self.assertRaises(Invalid) as e:
                store_module.bring_up_to_date(FailingCommit(con), path, [])
            self.assertFalse(con.in_transaction)                       # rolled back, not left open
        finally:
            con.close()
        self.assert_still_the_old_file(path, rows, str(e.exception))
        self.assert_a_second_open_migrates(path, rows)


class AnOlderClarkRefusesAVersion16Backup(Base):
    """A clark of the previous release (SCHEMA_VERSION 15, no step 16) is given a version-16 file or backup: it refuses, changes nothing."""

    def older(self):
        return mock.patch.multiple(store_module, SCHEMA_VERSION=STEP - 1,
                                   MIGRATIONS=tuple(m for m in store_module.MIGRATIONS if m[0] < STEP))

    def made(self):
        """A live version-15 file with data, and a version-16 backup of it in its backups folder."""
        path = make_at(self.dir, STEP - 1)
        add_use_cases(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), NOW)
            copy = backup.make(path, self.dir / "backups", [], "undo")
        finally:
            s.close()
        self.assertEqual(version(copy), NOW)
        return path, copy

    def refused_by_the_older_clark(self, target):
        with self.older():
            with self.assertRaises(Invalid) as e:
                open_store(target, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.NEWER_DATA)
        self.assertEqual(str(e.exception), "This data needs a newer clark. Nothing was changed. Install the latest clark, then try again.")

    def test_opening_a_version_16_file_by_the_older_logic_is_refused_and_the_bytes_are_the_same(self):
        path, _ = self.made()
        was = sha(path)
        self.refused_by_the_older_clark(path)
        self.assertEqual(sha(path), was)
        self.assertEqual(version(path), NOW)

    def test_a_version_16_backup_copied_in_as_the_database_is_refused_by_the_older_logic_and_its_rows_stay(self):
        # not byte for byte: a connection to a backup (journal mode DELETE) switches it to WAL, a header flag; the rows and version are what is checked
        _, copy = self.made()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir)))
        shutil.copyfile(str(copy), str(fresh / "clark.db"))
        was = dump(fresh / "clark.db")
        self.refused_by_the_older_clark(fresh / "clark.db")
        self.assertEqual(dump(fresh / "clark.db"), was)
        self.assertEqual(version(fresh / "clark.db"), NOW)
        self.assertEqual(integrity(fresh / "clark.db"), "ok")

    def test_the_restore_of_a_version_16_backup_by_the_older_logic_refuses_and_changes_nothing(self):
        path, copy = self.made()
        # the live file is a different, older state: the restore would replace it if it were allowed
        with self.older():
            was_backups = sorted(p.name for p in copy.parent.iterdir())
            was_copy, was_live = sha(copy), sha(path)
            with self.assertRaises(Invalid) as e:
                backup.restore_path(path, copy.name, copy.parent, [])
        self.assertIn("newer clark", str(e.exception))
        self.assertIn("update clark", str(e.exception))
        self.assertEqual(sha(copy), was_copy)
        self.assertEqual(sha(path), was_live)
        self.assertEqual(sorted(p.name for p in copy.parent.iterdir()), was_backups)         # no restore copy, no replaced- folder
        self.assertFalse(list(path.parent.glob("*.restoring*")))
        self.assertEqual(version(path), NOW)

    def test_the_restore_into_a_fresh_folder_by_the_older_logic_refuses_too(self):
        path, copy = self.made()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir)))
        was = sha(copy)
        with self.older():
            with self.assertRaises(Invalid) as e:
                backup.restore_path(fresh / "clark.db", copy.name, copy.parent, [])
        self.assertIn("newer clark", str(e.exception))
        self.assertEqual(sha(copy), was)
        self.assertFalse((fresh / "clark.db").exists())


class TheColumnTakesNoCheck(Base):
    def test_the_column_holds_a_fourth_word_without_a_layout_step(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO projects (code, name) VALUES ('ABC', 'Example Programme')")
        con.execute("INSERT INTO use_cases (id, project, title, status, source, commitment) VALUES ('ABC-U-001', 'ABC', 'T', 'Flag', 't', 'Planned 2028')")
        self.assertEqual(con.execute("SELECT commitment FROM use_cases").fetchone()[0], "Planned 2028")
        con.close()


if __name__ == "__main__":
    unittest.main()
