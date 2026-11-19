"""Row 1366: a missing index file (deleted, never made) is built again in the background when folders are listed; the question that finds
it missing is still answered from the folders. Run: python3 dev/run_tests.py test_ask_index_rebuild_1366. Files are made from made-up text."""
import unittest

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from clark import ask_index


class Rebuild(Base):
    def setUp(self):
        super().setUp()
        self.ix = ask_index.Indexer(self.data, None)
        self.addCleanup(self.ix.shutdown)
        self.put("a.txt", "zqrebuild text")
        self.folders = [str(self.box)]

    def test_a_deleted_index_is_built_again_and_the_question_meanwhile_reads_the_folders(self):
        ix.build(self.data, "P1", self.folders)
        self.assertTrue(self.ix.current("P1", self.folders))
        ask_index.path_for(self.data, "P1").unlink()
        self.assertFalse(self.ix.current("P1", self.folders), "never answer from a missing index")
        self.assertTrue(self.ix.wait_idle(10))
        self.assertTrue(ask_index.path_for(self.data, "P1").exists())
        self.assertTrue(self.ix.current("P1", self.folders))

    def test_status_for_starts_a_run_when_the_index_is_missing(self):
        self.assertFalse(ask_index.path_for(self.data, "P1").exists())
        self.ix.status_for("P1", self.folders)
        self.assertTrue(self.ix.wait_idle(10))
        self.assertTrue(self.ix.current("P1", self.folders))

    def test_no_run_when_no_folders_are_listed(self):
        self.assertFalse(self.ix.current("P1", []))
        self.ix.status_for("P1", [])
        self.assertEqual(self.ix.busy, 0)
        self.assertFalse(ask_index.path_for(self.data, "P1").exists())


if __name__ == "__main__":
    unittest.main()
