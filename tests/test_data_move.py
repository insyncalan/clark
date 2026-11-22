"""Issue 635: moving clark's data to another computer.

Run: python3 tests/test_data_move.py
A backup is portable, but the folder paths saved inside it are the other computer's. A backup made with Mac-style paths is
restored into a clean folder; the dump, the row counts and the schema version must match, and the doctor's line for saved
folders that do not exist here is advice, with no traceback. Fictional data, temporary folders only.
"""
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from _demo import DemoStore  # noqa: E402
from clark import backup, doctor  # noqa: E402
from clark.store import SCHEMA_VERSION, open_store  # noqa: E402

MAC_SOURCE = "/Users/sam/Documents/Example Programme/Source"
MAC_LOCAL = "/Users/sam/Documents/Example Programme/Published/ABC-1.html"
MAC_CLIENT = "/Users/sam/Library/CloudStorage/Client/ABC-1.html"
TABLES = ("projects", "workstreams", "use_cases", "milestones", "source_folders", "publications", "meta")


def dump(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return "\n".join(con.iterdump())
    finally:
        con.close()


def counts(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    finally:
        con.close()


def version(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0]
    finally:
        con.close()


class DataMove(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.new = Path(tempfile.mkdtemp(prefix="clark-move-"))
        self.addCleanup(shutil.rmtree, self.new, True)
        con = sqlite3.connect(self.demo.dir / "clark.db")        # raw rows: the store's own folder rules need a Mac
        try:
            con.execute("INSERT INTO source_folders (project, path, sort_order) VALUES ('ABC', ?, 0)", (MAC_SOURCE,))
            con.execute("INSERT INTO publications (project, local_path, client_path, word, file_sha256, checks, by_user, number) "
                        "VALUES ('ABC', ?, ?, 0, ?, 'passed', 'Sam Example', 1)", (MAC_LOCAL, MAC_CLIENT, "0" * 64))
            con.commit()
        finally:
            con.close()
        self.made = backup.make(self.demo.dir / "clark.db", self.demo.dir / "backups", [], tag="daily")
        self.backups = self.new / "backups"
        self.backups.mkdir()
        shutil.copy(self.made, self.backups / Path(self.made).name)
        self.db = self.new / "clark.db"
        backup.restore_path(self.db, Path(self.made).name, self.backups, [])

    def test_the_restored_data_matches_the_backup(self):
        self.assertEqual(dump(self.db), dump(self.made))
        self.assertEqual(counts(self.db), counts(self.made))
        self.assertEqual(counts(self.db)["source_folders"], 1)
        self.assertEqual(counts(self.db)["publications"], 1)
        self.assertEqual(version(self.db), version(self.made))
        self.assertEqual(version(self.db), str(SCHEMA_VERSION))

    def test_the_restored_data_opens_with_the_other_computers_paths_unchanged(self):
        store = open_store(self.db, onedrive_roots=[])
        store.close()
        self.assertEqual(doctor.saved_paths(self.new), sorted({MAC_SOURCE, MAC_LOCAL, MAC_CLIENT}))

    def test_missing_folders_are_advice_and_never_a_traceback(self):
        seen = doctor.Seen(data=str(self.new), home="/home/nobody", on="windows")
        line = doctor.run_check(doctor.Check("The check for saved folders", False, doctor.check_saved_folders), seen)
        self.assertEqual(line.kind, doctor.ADVICE)
        self.assertTrue(line.words.startswith("Folders saved in your data that do not exist here: "))
        self.assertIn(MAC_SOURCE, line.words)
        self.assertNotIn("Traceback", line.words)
        out = []
        code = doctor.doctor(seen, out.append, (doctor.Check("The check for saved folders", False, doctor.check_saved_folders),))
        self.assertEqual(code, 0, "advice does not stop clark")
        self.assertTrue(any(l.startswith("Worth knowing: Folders saved") for l in out), out)

    def test_folders_that_exist_here_are_ready(self):
        here = Path(tempfile.mkdtemp(prefix="clark-here-"))
        self.addCleanup(shutil.rmtree, here, True)
        con = sqlite3.connect(self.db)
        try:
            con.execute("UPDATE source_folders SET path = ?", (str(here),))
            con.execute("DROP TRIGGER publications_number_fixed")
            con.execute("UPDATE publications SET local_path = ?, client_path = ?", (str(here), str(here)))
            con.commit()
        finally:
            con.close()
        line = doctor.check_saved_folders(doctor.Seen(data=str(self.new), home="/home/nobody"))
        self.assertEqual((line.kind, line.words), (doctor.READY, "Every folder saved in your data is here."))

    def test_no_database_or_no_folders_is_ready(self):
        empty = Path(tempfile.mkdtemp(prefix="clark-empty-"))
        self.addCleanup(shutil.rmtree, empty, True)
        line = doctor.check_saved_folders(doctor.Seen(data=str(empty), home="/home/nobody"))
        self.assertEqual((line.kind, line.words), (doctor.READY, "No folders are saved in your data yet."))

    def test_an_unreadable_database_is_not_checked_without_a_traceback(self):
        bad = Path(tempfile.mkdtemp(prefix="clark-bad-"))
        self.addCleanup(shutil.rmtree, bad, True)
        (bad / "clark.db").write_bytes(b"not a database" * 50)
        seen = doctor.Seen(data=str(bad), home="/home/nobody")
        line = doctor.run_check(doctor.Check("The check for saved folders", False, doctor.check_saved_folders), seen)
        self.assertEqual(line.kind, doctor.NOT_CHECKED)
        self.assertNotIn("Traceback", line.words)

    def test_a_database_without_the_publications_table_still_gives_its_folders(self):
        old = Path(tempfile.mkdtemp(prefix="clark-old-"))
        self.addCleanup(shutil.rmtree, old, True)
        con = sqlite3.connect(old / "clark.db")
        try:
            con.execute("CREATE TABLE source_folders (path TEXT)")
            con.execute("INSERT INTO source_folders VALUES (?)", (MAC_SOURCE,))
            con.commit()
        finally:
            con.close()
        self.assertEqual(doctor.saved_paths(old), [MAC_SOURCE])

    def test_a_table_that_cannot_be_read_for_another_reason_is_not_swallowed(self):
        bad = Path(tempfile.mkdtemp(prefix="clark-nocol-"))
        self.addCleanup(shutil.rmtree, bad, True)
        con = sqlite3.connect(bad / "clark.db")
        try:
            con.execute("CREATE TABLE source_folders (other TEXT)")        # the table is there, the column is not
            con.commit()
        finally:
            con.close()
        with self.assertRaises(sqlite3.OperationalError):
            doctor.saved_paths(bad)

    def test_each_folder_is_listed_once_and_an_empty_path_is_not_a_folder(self):
        same = Path(tempfile.mkdtemp(prefix="clark-same-"))
        self.addCleanup(shutil.rmtree, same, True)
        con = sqlite3.connect(same / "clark.db")
        try:
            con.execute("CREATE TABLE source_folders (path TEXT)")
            con.execute("CREATE TABLE publications (local_path TEXT, client_path TEXT)")
            con.executemany("INSERT INTO source_folders VALUES (?)", [(MAC_SOURCE,), (MAC_SOURCE,), ("",), (None,)])
            con.execute("INSERT INTO publications VALUES (?, ?)", (MAC_SOURCE, ""))
            con.commit()
        finally:
            con.close()
        self.assertEqual(doctor.saved_paths(same), [MAC_SOURCE])

    def test_only_three_missing_folders_are_named_and_the_rest_are_counted(self):
        many = Path(tempfile.mkdtemp(prefix="clark-many-"))
        self.addCleanup(shutil.rmtree, many, True)
        names = [f"/Users/sam/Documents/Missing {n}" for n in "ABCDE"]
        con = sqlite3.connect(many / "clark.db")
        try:
            con.execute("CREATE TABLE source_folders (path TEXT)")
            con.executemany("INSERT INTO source_folders VALUES (?)", [(n,) for n in names])
            con.commit()
        finally:
            con.close()
        line = doctor.check_saved_folders(doctor.Seen(data=str(many), home="/home/nobody"))
        for n in names[:3]:
            self.assertIn(n, line.words)
        for n in names[3:]:
            self.assertNotIn(n, line.words)
        self.assertIn("and 2 more", line.words)
        three = Path(tempfile.mkdtemp(prefix="clark-three-"))
        self.addCleanup(shutil.rmtree, three, True)
        con = sqlite3.connect(three / "clark.db")
        try:
            con.execute("CREATE TABLE source_folders (path TEXT)")
            con.executemany("INSERT INTO source_folders VALUES (?)", [(n,) for n in names[:3]])
            con.commit()
        finally:
            con.close()
        self.assertNotIn(" more", doctor.check_saved_folders(doctor.Seen(data=str(three), home="/home/nobody")).words)

    def test_a_folder_name_with_a_question_mark_hash_or_percent_is_read(self):
        odd = Path(tempfile.mkdtemp(prefix="clark-odd?#%41-"))
        self.addCleanup(shutil.rmtree, odd, True)
        shutil.copy(self.db, odd / "clark.db")
        self.assertEqual(doctor.saved_paths(odd), sorted({MAC_SOURCE, MAC_LOCAL, MAC_CLIENT}))

    def test_inside_the_container_the_check_says_it_was_not_made(self):
        from unittest import mock
        with mock.patch.object(doctor.platform, "container_mode", return_value=True):
            line = doctor.check_saved_folders(doctor.Seen(data=str(self.new), home="/home/nobody"))
        self.assertEqual(line.kind, doctor.NOT_CHECKED)
        self.assertIn("inside Docker", line.words)
        self.assertNotIn(MAC_SOURCE, line.words)

    def test_the_check_is_in_the_doctor_and_is_not_required(self):
        ours = [c for c in doctor.CHECKS if c.run is doctor.check_saved_folders]
        self.assertEqual(len(ours), 1)
        self.assertFalse(ours[0].required)


if __name__ == "__main__":
    unittest.main()
