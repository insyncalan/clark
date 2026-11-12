"""#633: `python3 -m clark check-data --data FOLDER`, the check run before the server starts in Docker: the data is at this
version (nothing happens), older (a copy is taken, then it is brought up to date) or newer (refused, nothing changed, exit 2).

Run: python3 dev/run_tests.py test_check_data
Every folder is a temporary one. No server, no Docker, no browser.
"""
import hashlib
import io
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import __main__ as launcher, backup, store as store_module
from test_migration_chain import chain, copies, dump
from test_store_migration import make_v1, version

NEWER_FOLDER = store_module.NEWER_FOLDER


def run(folder):
    out, err = io.StringIO(), io.StringIO()
    code = launcher.main(["check-data", "--data", str(folder)], out=out, err=err, onedrive_roots=[])
    return code, out.getvalue(), err.getvalue()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def names(folder):
    """The raw listing of every file under the folder. A read-only look at a WAL-mode database may leave SQLite's -shm index and an EMPTY
    -wal behind (no data in them): those two are left out. A -wal with anything in it, or any other new file, shows."""
    out = []
    for p in sorted(Path(folder).rglob("*")):
        if p.name.endswith("-shm") or (p.name.endswith("-wal") and p.stat().st_size == 0):
            continue
        out.append(str(p.relative_to(folder)))
    return out


def set_version(path, v):
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(v),))
    con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)


class OlderData(Base):
    def test_an_older_file_is_copied_then_brought_up_to_date_and_exit_is_0(self):
        path = make_v1(self.dir)
        original = dump(path)
        code, out, err = run(self.dir)
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
        made = copies(self.dir, "migrate")
        self.assertEqual(len(made), 1)
        self.assertEqual(version(made[0].path), "1")           # the copy is of the data as it was
        self.assertEqual(dump(made[0].path), original)
        con = sqlite3.connect(str(path))
        try:
            self.assertEqual(con.execute("SELECT code FROM projects").fetchall(), [("ABC",)])    # the data survived
        finally:
            con.close()
        self.assertIn(made[0].name, out)

    def test_a_forced_failure_rolls_back_and_exits_1_in_plain_words(self):
        path = make_v1(self.dir)
        before = dump(path)
        with mock.patch.object(store_module, "MIGRATIONS", chain([], 5, 3)), mock.patch.object(store_module, "SCHEMA_VERSION", 5):
            code, out, err = run(self.dir)
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("The database could not be updated. Nothing was changed."), err)
        self.assertFalse(re.search(r"Traceback|migration|schema", err))
        self.assertEqual(dump(path), before)
        self.assertEqual(version(path), "1")


class SameData(Base):
    def test_the_same_version_exits_0_and_changes_nothing(self):
        path = make_v1(self.dir)
        self.assertEqual(run(self.dir)[0], 0)
        before, files = sha(path), names(self.dir)
        code, out, err = run(self.dir)
        self.assertEqual((code, err, out), (0, "", "The data is up to date.\n"))
        self.assertEqual((sha(path), names(self.dir)), (before, files))
        self.assertEqual(len(copies(self.dir, "migrate")), 1)       # still the one from the first run

    def test_no_data_yet_exits_0_and_makes_nothing(self):
        code, out, err = run(self.dir)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(list(self.dir.iterdir()), [])


class LockedData(Base):
    def test_a_lock_is_said_as_in_use_not_as_a_database_clark_cannot_read(self):
        path = make_v1(self.dir)
        before, files = sha(path), names(self.dir)
        with mock.patch.object(store_module, "connect", side_effect=sqlite3.OperationalError("database is locked")):
            code, out, err = run(self.dir)
        self.assertEqual(out, "")
        self.assertEqual((sha(path), names(self.dir)), (before, files))
        self.assertEqual(code, 1)
        self.assertIn("in use by another program", err)
        self.assertNotIn("not a database clark can read", err)
        self.assertTrue(path.is_file())


class NewerData(Base):
    def test_a_newer_file_exits_2_with_the_plain_sentence_and_changes_nothing(self):
        path = make_v1(self.dir)
        set_version(path, store_module.SCHEMA_VERSION + 1)
        before, files = sha(path), names(self.dir)
        code, out, err = run(self.dir)
        self.assertEqual(code, 2)
        self.assertEqual(err.strip(), NEWER_FOLDER)
        self.assertIn("Start from the newer clark folder.", err)
        self.assertTrue(err.startswith("This data needs a newer clark."))
        self.assertTrue(err.strip().endswith("Nothing was changed."))
        self.assertEqual(out, "")
        self.assertEqual((sha(path), names(self.dir)), (before, files))
        self.assertEqual(copies(self.dir), [])

    def test_a_newer_file_in_wal_mode_keeps_its_bytes_and_makes_no_copy(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("UPDATE meta SET v = '99' WHERE k = 'schema_version'")
        con.close()
        before = sha(path)
        code, out, err = run(self.dir)
        self.assertEqual((code, err.strip()), (2, NEWER_FOLDER))
        self.assertEqual(sha(path), before)
        self.assertEqual(names(self.dir), ["clark.db"])

    def test_the_shared_sentence_the_mac_shows_is_unchanged(self):
        self.assertEqual(store_module.NEWER_DATA,
                         "This data needs a newer clark. Nothing was changed. Install the latest clark, then try again.")

    def test_the_check_does_not_write_even_the_journal_files(self):
        path = make_v1(self.dir)
        set_version(path, 99)
        run(self.dir)
        self.assertEqual(names(self.dir), ["clark.db"])


class TwoFolders(Base):
    def test_new_code_migrates_shared_data_then_older_code_is_refused_and_the_copy_restores(self):
        path = make_v1(self.dir)
        self.assertEqual(run(self.dir)[0], 0)                        # the newer clark folder
        migrated = sha(path)
        with mock.patch.object(store_module, "SCHEMA_VERSION", store_module.SCHEMA_VERSION - 1):      # the older clark folder
            code, out, err = run(self.dir)
        self.assertEqual((code, err.strip()), (2, NEWER_FOLDER))
        self.assertEqual(sha(path), migrated)
        copy = copies(self.dir, "migrate")[0]
        self.assertEqual(version(copy.path), "1")
        con = sqlite3.connect(str(copy.path))
        try:
            self.assertEqual(con.execute("SELECT code FROM projects").fetchall(), [("ABC",)])
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
