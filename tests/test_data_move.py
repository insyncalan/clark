"""#635: clark's data moved from a Mac to Windows (or any other computer), by its backup file.

Run: python3 dev/run_tests.py test_data_move
A backup made on a "Mac" (a demo store holding Mac paths in source_folders and publications) is restored into a clean folder,
and the restored database is compared with the one the backup was taken from: the whole .dump, the rows in every table and the
schema version. Then the doctor's saved-folders line is asked of the restored data: the Mac paths are not on this computer, so it
says so as advice, without a traceback. Fictional data only, in temporary folders; the real data folder is never read.
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import DemoStore
from clark import backup, doctor, launch, platform as pl, store as cs

SHA = "0" * 64
MAC_PATHS = ("/Users/alex/Clients/ABC/Workshop notes", "/Users/alex/Clients/ABC/reports/week-44.html",
             "/Users/alex/Library/CloudStorage/OneDrive-Fictional Ltd/ABC/week-44.html")


def dump(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return "\n".join(con.iterdump())
    finally:
        con.close()


def counts(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        return {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tables}
    finally:
        con.close()


def version(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0]
    finally:
        con.close()


class MacBackupMoved(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        s = self.demo.store
        s.con.execute("INSERT INTO source_folders (project, path, sort_order) VALUES ('ABC', ?, 0)", (MAC_PATHS[0],))
        s.con.execute("INSERT INTO publications (project, local_path, client_path, file_sha256, checks, by_user, number) "
                      "VALUES ('ABC', ?, ?, ?, 'not needed', 'Demo User', 1)", (MAC_PATHS[1], MAC_PATHS[2], SHA))
        self.made = backup.take(s, "changes")
        self.mac_dump, self.mac_counts, self.mac_version = dump(s.path), counts(s.path), version(s.path)
        self.clean = Path(tempfile.mkdtemp(prefix="clark-moved-"))
        self.addCleanup(shutil.rmtree, self.clean, True)
        (self.clean / "backups").mkdir()
        shutil.copy2(self.made, self.clean / "backups" / self.made.name)       # the backup file, carried to the new computer
        self.db = self.clean / "clark.db"
        self.done = backup.restore_path(self.db, self.made.name, onedrive_roots=[])

    def test_restored_into_a_clean_folder_is_the_same_data(self):
        self.assertEqual(Path(self.done["database"]), self.db)
        self.assertIsNone(self.done["replaced"])                            # nothing was there to move aside
        self.assertEqual(version(self.db), self.mac_version)
        self.assertEqual(version(self.db), str(cs.SCHEMA_VERSION))
        self.assertEqual(counts(self.db), self.mac_counts)
        self.assertEqual(self.mac_counts["source_folders"], 1)
        self.assertEqual(self.mac_counts["publications"], 1)
        self.assertEqual(dump(self.db), self.mac_dump)

    def test_restored_data_opens(self):
        store = cs.open_store(self.db, onedrive_roots=[])
        self.addCleanup(store.close)
        self.assertEqual(store.con.execute("SELECT path FROM source_folders").fetchone()[0], MAC_PATHS[0])

    def test_the_doctor_says_the_mac_folders_are_not_here_without_a_traceback(self):
        seen = doctor.Seen(data=str(self.clean), on=pl.MAC, home=self.clean, environ={}, exists=lambda p: False)
        check = doctor.Check("The check for saved folders", False, doctor.check_saved_folders)
        line = doctor.run_check(check, seen)
        self.assertEqual(line.kind, doctor.ADVICE)
        self.assertTrue(line.words.startswith("Folders saved in your data that do not exist here: 3, such as "), line.words)
        self.assertNotIn("alex", line.words)                               # the other computer's account name is never said
        self.assertNotIn("Traceback", line.words)

    def test_a_missing_source_folder_is_advice_not_a_fault(self):
        lines = []
        code = doctor.main(["--data", str(self.clean)], say=lines.append, on=pl.MAC, home=self.clean, environ={},
                           app=self.clean, version=(3, 9, 6), sqlite_version="3.37.0", onedrive_roots=lambda: [],
                           find_chrome=lambda: "/fictional/chrome", find_claude=lambda: "/fictional/bin/claude",
                           health=lambda port, mark: launch.NOTHING, free=lambda port: False)
        found = [line for line in lines if line.startswith("Worth knowing: Folders saved in your data")]
        self.assertEqual(len(found), 1, lines)
        self.assertNotIn("Traceback", "\n".join(lines))
        self.assertNotIn("To fix: Folders", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
