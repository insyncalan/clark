"""Row 1371 part 2, server side: the states of the line under a source folder (waiting, updating, paused, failed, cleared), the
Try again / Index again action, and the count of projects for a folder for all projects (no browser).

Run: python3 dev/run_tests.py test_ask_index_states_1371
Every file is made in the test from made-up text.
"""
import threading
import unittest

from _paths import SRC  # noqa: F401

from test_ask_index_status_1366 import Base
from clark import ask_folders, ask_index, store as st

TRY = "Could not index this folder. Try again"
AGAIN = "Not indexed. Index again"


class Lines(Base):
    def lines(self, **kw):
        return ask_index.folder_status(self.data, "ABC", [str(self.a)], **kw)

    def test_a_folder_whose_run_is_queued_or_has_not_reached_it_says_waiting(self):
        self.assertEqual(self.lines(queued=True), {str(self.a): {"state": "waiting", "line": "Waiting to index"}})
        self.assertEqual(self.lines(live={}), {str(self.a): {"state": "waiting", "line": "Waiting to index"}})

    def test_a_folder_with_no_run_and_no_index_still_says_nothing(self):
        self.assertEqual(self.lines(), {})

    def test_updating_counts_the_files_changed_in_that_folder_singular_and_plural(self):
        self.assertEqual(self.lines(live={str(self.a): (1, 4)}, changed={str(self.a): 1}), {str(self.a): {"state": "updating", "line": "Updating… 1 file changed"}})
        self.assertEqual(self.lines(live={str(self.a): (1, 4)}, changed={str(self.a): 3}), {str(self.a): {"state": "updating", "line": "Updating… 3 files changed"}})
        self.assertEqual(self.lines(live={str(self.a): (1, 4)}, changed={str(self.b): 3})[str(self.a)]["state"], "reading")

    def test_changes_names_the_folder_of_each_changed_file(self):
        self.put(self.a, "one.txt", "alpha")
        self.put(self.b, "two.txt", "beta")
        folders = [str(self.a), str(self.b)]
        ask_index.refresh(self.data, "ABC", folders, self.home)
        self.assertEqual(ask_index.changes(self.data, "ABC", folders, self.home), {})
        self.put(self.a, "one.txt", "alpha longer")
        self.put(self.a, "new.txt", "new")
        self.assertEqual(ask_index.changes(self.data, "ABC", folders, self.home), {str(self.a): 2})
        self.assertTrue(ask_index.stale(self.data, "ABC", folders, self.home))

    def test_a_file_gone_counts_for_no_folder(self):
        self.put(self.a, "one.txt", "alpha")
        ask_index.refresh(self.data, "ABC", [str(self.a)], self.home)
        (self.a / "one.txt").unlink()
        self.assertTrue(ask_index.stale(self.data, "ABC", [str(self.a)], self.home))
        self.assertEqual(ask_index.changes(self.data, "ABC", [str(self.a)], self.home), {})

    def test_paused_failed_and_cleared_words(self):
        self.assertEqual(self.lines(paused=True), {str(self.a): {"state": "paused", "line": "Indexing paused. It carries on when clark is open"}})
        self.assertEqual(self.lines(failed=True), {str(self.a): {"state": "failed", "line": TRY}})
        self.assertEqual(self.lines(cleared=True), {str(self.a): {"state": "cleared", "line": AGAIN}})


class Worker(Base):
    def test_a_failed_run_says_try_again_and_is_not_started_again_by_itself(self):
        calls = []

        def boom(data, code, folders, home=None, stop=None, progress=None):
            calls.append(1)
            raise RuntimeError("x")
        self.put(self.a, "one.txt", "alpha")
        ix = ask_index.Indexer(self.data, self.home, refresh_fn=boom)
        self.addCleanup(ix.shutdown)
        ix.start("ABC", [str(self.a)])
        self.assertTrue(ix.wait_idle(5))
        for _ in range(3):
            self.assertEqual(ix.status_for("ABC", [str(self.a)]), {str(self.a): {"state": "failed", "line": TRY}})
        self.assertEqual(len(calls), 1)
        self.assertTrue(ix.again("ABC", [str(self.a)]))
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual(len(calls), 2)

    def test_a_cleared_index_says_index_again_and_is_built_only_when_asked(self):
        self.put(self.a, "one.txt", "alpha river")
        ix = ask_index.Indexer(self.data, self.home)
        self.addCleanup(ix.shutdown)
        ix.start("ABC", [str(self.a)])
        self.assertTrue(ix.wait_idle(5))
        ix.clear("ABC")
        for _ in range(2):
            self.assertEqual(ix.status_for("ABC", [str(self.a)]), {str(self.a): {"state": "cleared", "line": AGAIN}})
        self.assertFalse(ask_index.path_for(self.data, "ABC").exists())
        self.assertTrue(ix.again("ABC", [str(self.a)]))
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual(ix.status_for("ABC", [str(self.a)])[str(self.a)]["line"], "100% indexed")

    def test_a_run_waiting_for_the_worker_says_waiting_and_an_unfinished_index_nobody_runs_says_paused(self):
        self.put(self.a, "one.txt", "alpha river")
        gate = threading.Event()

        def slow(data, code, folders, home=None, stop=None, progress=None):
            gate.wait(10)
        ix = ask_index.Indexer(self.data, self.home, refresh_fn=slow)
        self.addCleanup(ix.shutdown)
        self.addCleanup(gate.set)
        ix.start("ABC", [str(self.a)])
        self.assertEqual(ix.status_for("ABC", [str(self.a)])[str(self.a)]["state"], "waiting")
        gate.set()
        self.assertTrue(ix.wait_idle(5))
        db = ask_index._open(self.data, "ABC")
        db.close()
        ix.checked["ABC"] = 10 ** 12                    # the poll just looked: nothing starts a run now
        self.assertEqual(ix.status_for("ABC", [str(self.a)]), {str(self.a): {"state": "paused", "line": "Indexing paused. It carries on when clark is open"}})

    def test_a_changed_file_says_updating_while_the_run_reads_again(self):
        self.put(self.a, "one.txt", "alpha river")
        self.put(self.a, "two.txt", "beta river")
        ix = ask_index.Indexer(self.data, self.home)
        self.addCleanup(ix.shutdown)
        ix.start("ABC", [str(self.a)])
        self.assertTrue(ix.wait_idle(5))
        gate = threading.Event()
        self.addCleanup(gate.set)

        def held(data, code, folders, home=None, stop=None, progress=None):
            gate.wait(10)
            return True
        ix.refresh = held
        self.put(self.a, "one.txt", "alpha river longer")
        self.put(self.a, "two.txt", "beta river longer")
        got = ix.status_for("ABC", [str(self.a)])
        self.assertEqual(got[str(self.a)]["state"], "done")           # the held run has no progress for the folder yet: its finished line stays
        ix.live["ABC"] = {str(self.a): (1, 2)}
        self.assertEqual(ix.status_for("ABC", [str(self.a)])[str(self.a)], {"state": "updating", "line": "Updating\u2026 2 files changed"})
        gate.set()


class Route(Base):
    def setUp(self):
        super().setUp()
        self.db = self.data / "clark.db"
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "One"})
            s.create("projects", {"code": "DEF", "name": "Two"})
        store.close()
        self.ix = ask_index.Indexer(self.data, self.home)
        self.addCleanup(self.ix.shutdown)
        self.svc = ask_folders.AskFolders(self.db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester", indexer=self.ix)

    def test_the_reindex_action_starts_a_read_and_takes_no_other_field(self):
        self.put(self.a, "one.txt", "alpha river")
        self.assertEqual(self.svc.change({"project": "ABC", "action": "reindex"}), (200, {"ok": True, "started": True}))
        self.assertTrue(self.ix.wait_idle(5))
        self.assertEqual(self.svc.change({"project": "ABC", "action": "reindex", "path": "x"})[0], 400)
        self.assertEqual(self.svc.change({"project": "NOPE", "action": "reindex"})[0], 404)

    def test_the_all_projects_note_counts_the_projects_whose_index_holds_the_folder(self):
        self.put(self.a, "one.txt", "alpha river")
        self.svc.change_all({"scope": "all", "action": "add", "path": str(self.a)})
        self.assertTrue(self.ix.wait_idle(5))
        got = self.svc.read_all("ABC")[1]["projects"][str(self.a)]
        self.assertEqual((got["done"], got["all"], got["line"]), (2, 2, "Indexed for 2 of 2 projects"))
        ask_index.remove(self.data, "DEF")
        got = self.svc.read_all("ABC")[1]["projects"][str(self.a)]
        self.assertEqual((got["done"], got["all"], got["line"]), (1, 2, "Indexed for 1 of 2 projects"))
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.archive("projects", "DEF")
        store.close()
        got = self.svc.read_all("ABC")[1]["projects"][str(self.a)]
        self.assertEqual((got["done"], got["all"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
