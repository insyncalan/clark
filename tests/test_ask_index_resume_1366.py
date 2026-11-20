"""Row 1366: a first pass that was stopped or failed is started again (the index never stays half made), at most once every
STALE_POLL_SECONDS per project, so a run that keeps failing is not a loop. Run: python3 dev/run_tests.py test_ask_index_resume_1366.
Files are made from made-up text; the read is the real one."""
import threading
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from clark import ask_index


class Resume(Base):
    def setUp(self):
        super().setUp()
        for i in range(3):
            self.put(f"f{i}.txt", f"zqresume{i} text")
        self.folders = [str(self.box)]

    def stopped_pass(self):
        """A first pass cut off after its first file, as a stop (clark closing, a minute with no window) does."""
        stop = threading.Event()
        done = ask_index.refresh(self.data, "P1", self.folders, None, stop=stop, progress=lambda f, d, t: stop.set() if d else None)
        self.assertFalse(done)
        self.assertFalse(ask_index.current(self.data, "P1", self.folders), "a stopped pass is not complete")

    def indexer(self, fn=None):
        ixr = ask_index.Indexer(self.data, None, refresh_fn=fn)
        self.addCleanup(ixr.shutdown)
        return ixr

    def test_stop_then_poll_then_complete(self):
        self.stopped_pass()
        ixr = self.indexer()
        self.assertTrue(ixr.wait_idle(10))
        ixr.checked.clear()
        ixr.status_for("P1", self.folders)
        self.assertTrue(ixr.wait_idle(10))
        self.assertTrue(ixr.current("P1", self.folders), "complete after the poll")
        self.assertTrue(ix.search(self.data, "P1", "zqresume2"), "every file is in")

    def test_a_poll_alone_restarts_a_stopped_first_pass(self):
        self.stopped_pass()
        ixr = self.indexer()
        ixr.status_for("P1", self.folders)
        self.assertTrue(ixr.wait_idle(10))
        self.assertTrue(ask_index.current(self.data, "P1", self.folders))

    def test_a_question_alone_restarts_a_stopped_first_pass_and_is_answered_from_the_folders_meanwhile(self):
        self.stopped_pass()
        ixr = self.indexer()
        self.assertFalse(ixr.current("P1", self.folders), "this question reads the folders")
        self.assertTrue(ixr.wait_idle(10))
        self.assertTrue(ixr.current("P1", self.folders))

    def test_a_failing_pass_is_started_again_at_most_once_in_the_wait_and_never_in_a_loop(self):
        self.stopped_pass()
        calls = []

        def fails(*a, **k):
            calls.append(1)
            raise OSError("zq")
        ixr = self.indexer(fails)
        for _ in range(4):
            ixr.status_for("P1", self.folders)
            ixr.current("P1", self.folders)
            self.assertTrue(ixr.wait_idle(10))
        self.assertEqual(len(calls), 1, "four polls and four questions: one start")
        later = ask_index.time.monotonic() + ask_index.STALE_POLL_SECONDS + 1
        with mock.patch.object(ask_index.time, "monotonic", return_value=later):
            ixr.status_for("P1", self.folders)
            self.assertTrue(ixr.wait_idle(10))
            ixr.current("P1", self.folders)
            self.assertTrue(ixr.wait_idle(10))
        self.assertEqual(len(calls), 2, "once more when the wait is over, not once per call")

    def test_a_complete_index_is_not_restarted(self):
        ix.build(self.data, "P1", self.folders)
        calls = []
        ixr = self.indexer(lambda *a, **k: calls.append(1))
        for _ in range(3):
            ixr.status_for("P1", self.folders)
            self.assertTrue(ixr.current("P1", self.folders))
        self.assertTrue(ixr.wait_idle(10))
        self.assertEqual(calls, [])

    def test_a_clark_that_is_closing_does_not_start_it_again(self):
        self.stopped_pass()
        ixr = self.indexer(lambda *a, **k: self.fail("a run was started after shutdown"))
        ixr.shutdown()
        ixr.status_for("P1", self.folders)
        self.assertFalse(ixr.current("P1", self.folders))
        self.assertEqual(ixr.busy, 0)

    def test_no_folders_starts_nothing(self):
        self.stopped_pass()
        ixr = self.indexer(lambda *a, **k: self.fail("started with no folder"))
        ixr.status_for("P1", [])
        self.assertFalse(ixr.current("P1", []))
        self.assertEqual(ixr.busy, 0)


if __name__ == "__main__":
    unittest.main()
