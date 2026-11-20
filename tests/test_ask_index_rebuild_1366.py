"""Row 1366: a missing index file (deleted, never made) is built again in the background when folders are listed; the question that finds
it missing is still answered from the folders. Run: python3 dev/run_tests.py test_ask_index_rebuild_1366. Files are made from made-up text."""
import unittest
from unittest import mock

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

    def test_the_settings_poll_starts_no_run_on_each_tick_when_a_run_leaves_no_index(self):
        """The poll reads the status; a rebuild is started at most once every STALE_POLL_SECONDS, even if the run makes no index file."""
        calls = []
        ix2 = ask_index.Indexer(self.data, None, refresh_fn=lambda *a, **k: calls.append(1))
        self.addCleanup(ix2.shutdown)
        for _ in range(6):                                 # the page asks about every 2 seconds
            ix2.status_for("P1", self.folders)
            self.assertTrue(ix2.wait_idle(10))
        self.assertEqual(len(calls), 1)
        clock = ask_index.time.monotonic() + ask_index.STALE_POLL_SECONDS + 1
        with mock.patch.object(ask_index.time, "monotonic", return_value=clock):
            ix2.status_for("P1", self.folders)
            self.assertTrue(ix2.wait_idle(10))
        self.assertEqual(len(calls), 2, "and again once the wait is over")

    def test_a_current_index_is_not_rebuilt_by_the_poll(self):
        ix.build(self.data, "P1", self.folders)
        calls = []
        ix2 = ask_index.Indexer(self.data, None, refresh_fn=lambda *a, **k: calls.append(1))
        self.addCleanup(ix2.shutdown)
        for _ in range(4):
            ix2.status_for("P1", self.folders)
        self.assertTrue(ix2.wait_idle(10))
        self.assertEqual(calls, [])

    def test_no_run_when_no_folders_are_listed(self):
        self.assertFalse(self.ix.current("P1", []))
        self.ix.status_for("P1", [])
        self.assertEqual(self.ix.busy, 0)
        self.assertFalse(ask_index.path_for(self.data, "P1").exists())


if __name__ == "__main__":
    unittest.main()
