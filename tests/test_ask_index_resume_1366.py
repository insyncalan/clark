"""Row 1366: a first pass that was stopped or failed is started again (the index never stays half made), at most once every
STALE_POLL_SECONDS per project, so a run that keeps failing is not a loop. Run: python3 dev/run_tests.py test_ask_index_resume_1366.
Files are made from made-up text; the read is the real one."""
import os
import shutil
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

    def test_a_changed_folder_list_builds_the_index_for_the_new_folders(self):
        ix.build(self.data, "P1", self.folders)
        other = self.box.parent / "other"
        self.put("o.txt", "zqother text", folder=other)
        folders = self.folders + [str(other)]
        ixr = self.indexer()
        self.assertFalse(ixr.current("P1", folders), "this question reads the folders")
        self.assertTrue(ixr.wait_idle(10))
        self.assertTrue(ixr.current("P1", folders))
        self.assertTrue(ix.search(self.data, "P1", "zqother"), "the new folder is in")

    def complete_for_two_folders(self):
        """The index finished for [box, other]; returns the list and the second folder."""
        other = self.box.parent / "other"
        self.put("o.txt", "zqother text", folder=other)
        both = self.folders + [str(other)]
        ix.build(self.data, "P1", both)
        self.assertTrue(ask_index.current(self.data, "P1", both))
        return both, other

    def copy_of_box(self):
        """A second folder holding the same file names, sizes and modified times as `box`: no new file, nothing changed on disk."""
        twin = self.box.parent / "twin"
        shutil.copytree(self.box, twin)
        for src in self.box.iterdir():
            st = src.stat()
            os.utime(twin / src.name, ns=(st.st_atime_ns, st.st_mtime_ns))
        return twin

    def asked(self, folders):
        """What the poll and the question do for `folders` on an index finished for other folders: (current, reads started by the poll)."""
        calls = []
        ixr = self.indexer(lambda data, code, fs=None, *a, **k: calls.append(list(fs or ())))
        ixr.status_for("P1", folders)
        self.assertTrue(ixr.wait_idle(10))
        return ixr.current("P1", folders), calls

    def test_a_removed_folder_is_not_current_and_is_read_again(self):
        both, _other = self.complete_for_two_folders()
        self.assertFalse(ask_index.current(self.data, "P1", self.folders), "finished for two folders, asked with one: not current")
        now, calls = self.asked(self.folders)
        self.assertFalse(now, "a question reads the folders, not the index")
        self.assertEqual(calls, [self.folders], "the poll starts one read, for the one folder")

    def test_a_swapped_folder_with_the_same_files_is_not_current_and_is_read_again(self):
        ix.build(self.data, "P1", self.folders)
        twin = self.copy_of_box()
        swapped = [str(twin)]
        self.assertTrue(ask_index.current(self.data, "P1", self.folders))
        self.assertFalse(ask_index.current(self.data, "P1", swapped), "finished for box, asked with twin: not current")
        now, calls = self.asked(swapped)
        self.assertFalse(now)
        self.assertEqual(calls, [swapped], "the poll starts one read, for the new folder")

    def test_the_same_folders_in_another_order_are_still_current(self):
        both, _other = self.complete_for_two_folders()
        self.assertTrue(ask_index.current(self.data, "P1", list(reversed(both))))

    def blocked(self):
        """An Indexer whose reads wait on `go`; `calls` holds the codes it was asked to read, `entered` is set at the first one."""
        go, entered, calls = threading.Event(), threading.Event(), []

        def fn(data, code, *a, **k):
            calls.append(code)
            entered.set()
            go.wait(10)
        self.addCleanup(go.set)
        return self.indexer(fn), go, entered, calls

    def test_resume_says_whether_it_started_and_waits_the_whole_wait(self):
        self.stopped_pass()
        ixr = self.indexer(lambda *a, **k: None)
        self.assertIs(ixr.resume("P1", self.folders), True)
        self.assertTrue(ixr.wait_idle(10))
        self.assertIs(ixr.resume("P1", self.folders), False, "inside the wait")
        stamp = ixr.resumed["P1"]
        wait = ask_index.STALE_POLL_SECONDS
        with mock.patch.object(ask_index.time, "monotonic", return_value=stamp + wait):
            self.assertIs(ixr.resume("P1", self.folders), True, "exactly when the wait is over")
        self.assertTrue(ixr.wait_idle(10))
        with mock.patch.object(ask_index.time, "monotonic", return_value=ixr.resumed["P1"] + wait - 0.5):
            self.assertIs(ixr.resume("P1", self.folders), False, "half a second short")

    def test_a_run_going_is_not_started_again(self):
        self.stopped_pass()
        ixr, go, entered, calls = self.blocked()
        self.assertTrue(ixr.start("P1", self.folders))
        self.assertTrue(entered.wait(10))
        self.assertIs(ixr.resume("P1", self.folders), False, "its run is going")
        go.set()
        self.assertTrue(ixr.wait_idle(10))
        self.assertEqual(calls, ["P1"], "one run, not two")

    def test_a_run_waiting_in_the_queue_is_not_queued_again(self):
        self.stopped_pass()
        ixr, go, entered, calls = self.blocked()
        self.assertTrue(ixr.start("P2", self.folders))
        self.assertTrue(entered.wait(10))
        self.assertTrue(ixr.start("P1", self.folders))
        self.assertIs(ixr.resume("P1", self.folders), False, "it is already waiting its turn")
        self.assertEqual(ixr.busy, 2)
        go.set()
        self.assertTrue(ixr.wait_idle(10))
        self.assertEqual(sorted(calls), ["P1", "P2"])

    def test_two_threads_resuming_together_give_one_start(self):
        self.stopped_pass()
        starts = []
        ixr = self.indexer(lambda *a, **k: None)
        ixr.start = lambda code, folders: starts.append(code) or True
        meet = threading.Barrier(2, timeout=1)

        class Slow(dict):
            def get(self, *a):          # both threads read the stamp before either writes it, unless the lock keeps one out
                found = dict.get(self, *a)
                try:
                    meet.wait()
                except threading.BrokenBarrierError:
                    pass
                return found
        ixr.resumed = Slow()
        results = []
        threads = [threading.Thread(target=lambda: results.append(ixr.resume("P1", self.folders))) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(starts, ["P1"], "one start")
        self.assertEqual(sorted(results), [False, True])

    def test_a_poll_with_no_folder_starts_nothing_even_when_it_is_due(self):
        self.stopped_pass()
        calls = []
        ixr = self.indexer(lambda *a, **k: calls.append(1))
        ixr.status_for("P1", [])
        self.assertTrue(ixr.wait_idle(10))
        self.assertEqual(calls, [])

    def test_a_poll_inside_the_wait_after_a_poll_starts_nothing_more(self):
        self.stopped_pass()
        calls = []
        ixr = self.indexer(lambda *a, **k: calls.append(1))
        ixr.status_for("P1", self.folders)
        self.assertTrue(ixr.wait_idle(10))
        ixr.status_for("P1", self.folders)          # not due again yet: the poll itself waits too
        self.assertTrue(ixr.wait_idle(10))
        self.assertEqual(len(calls), 1)

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

    def refused(self):
        """A folder clark never reads (a secret folder name): the project has nothing but this."""
        bad = self.box / ".ssh"
        bad.mkdir()
        (bad / "k.txt").write_text("zqrefused text", encoding="utf-8")
        return [str(bad)]

    def test_an_index_of_only_refused_folders_is_current_and_not_read_again(self):
        folders = self.refused()
        self.assertTrue(ask_index.refresh(self.data, "P1", folders))
        self.assertTrue(ask_index.current(self.data, "P1", folders), "it carries the screen version")
        s = ix.status(self.data, "P1", folders)
        self.assertEqual(s["safety"], 1)
        self.assertEqual(s["indexed"], 0)
        self.assertFalse(ix.search(self.data, "P1", "zqrefused"))
        calls = []
        ixr = self.indexer(lambda *a, **k: calls.append(1))
        for step in range(3):
            later = ask_index.time.monotonic() + (step + 1) * (ask_index.STALE_POLL_SECONDS + 1)
            with mock.patch.object(ask_index.time, "monotonic", return_value=later):
                ixr.status_for("P1", folders)
                self.assertTrue(ixr.wait_idle(10))
        self.assertEqual(calls, [], "a finished index is not started again, poll after poll")
        self.assertTrue(ixr.current("P1", folders))


if __name__ == "__main__":
    unittest.main()
