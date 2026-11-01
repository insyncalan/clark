"""#47: the store keeps the folders asking may read (source_folders): a step writes one, the history shows it, Undo takes it back.

Run: python3 dev/run_tests.py test_source_folders_store
"""
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from _paths import SRC  # noqa: F401

from clark import platform as pl, store as st


class Folders(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)       # the never-read list is the Mac's; a Linux runner has none
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(tempfile.mkdtemp())
        (self.d / "data").mkdir()
        self.store = st.open_store(self.d / "data" / "clark.db", onedrive_roots=[])
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Example Programme"})
        self.made = None
        self.docs = self.d / "docs"
        self.docs.mkdir()

    def tearDown(self):
        self.store.close()

    def add(self, path, order=0):
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.create("source_folders", {"project": "ABC", "path": str(path), "sort_order": order})
            self.made = s.peek_apply_id()
        return self.made

    def test_a_folder_is_saved_read_back_and_taken_off_again(self):
        self.add(self.docs)
        self.assertEqual([r["path"] for r in self.store.read("source_folders", "ABC")], [str(self.docs)])
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.cancel("source_folders", f"ABC|{self.docs}")
        self.assertEqual(self.store.read("source_folders", "ABC"), [])

    def test_refused_folders(self):
        piped = self.d / "a|b"
        piped.mkdir()
        for bad in ("relative/path", "/", "//", str(self.d / "data"), str(self.d / "data" / "x"), "/a\nb", str(piped)):
            with self.assertRaises(st.Invalid, msg=bad):
                self.add(bad)
        with self.assertRaises(st.Invalid):                       # a project that is not there
            with self.store.step("dashboard", "tester", place="menu") as s:
                s.create("source_folders", {"project": "ZZZ", "path": str(self.docs), "sort_order": 0})
        self.assertEqual(self.store.read("source_folders", "ABC"), [])

    def test_undo_takes_the_folder_back_and_the_history_shows_the_step(self):
        step = self.add(self.docs)
        self.assertTrue(self.store.step_rows(step), "the step is in the history")
        out = self.store.undo(step, "tester")
        self.assertEqual(self.store.read("source_folders", "ABC"), [], out)

    def test_a_removed_folder_comes_back_with_undo(self):
        self.add(self.docs)
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.cancel("source_folders", f"ABC|{self.docs}")
            gone = s.peek_apply_id()
        self.assertEqual(self.store.read("source_folders", "ABC"), [])
        self.store.undo(gone, "tester")
        self.assertEqual([r["path"] for r in self.store.read("source_folders", "ABC")], [str(self.docs)])


if __name__ == "__main__":
    unittest.main()
