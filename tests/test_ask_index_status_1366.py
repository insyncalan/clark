"""Row 1366 slice (a): the per-folder status line, the background worker, the route and the question path (no browser).

Run: python3 dev/run_tests.py test_ask_index_status_1366
Every file is made in the test from made-up text.
"""
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_change_route import Base as RouteBase
from clark import ask, ask_folders, ask_index, ask_passages, ask_service, reach, store as st

FAKE_KEY = "password = " + "hunter2" * 3


class DoneLine(unittest.TestCase):
    def test_row_1371_the_words_of_a_finished_folder(self):
        self.assertEqual(ask_index.done_line({"indexed": 3}), "100% indexed")
        self.assertEqual(ask_index.done_line({"indexed": 3, "type": 1}), "100% indexed. 1 file could not be read")
        self.assertEqual(ask_index.done_line({"indexed": 3, "type": 2, "safety": 10}), "100% indexed. 12 files could not be read")
        self.assertEqual(ask_index.done_line({}), "No files to index")
        self.assertEqual(ask_index.done_line({"type": 2, "safety": 1}), "No files to index")      # files, but none readable: not "100% indexed"
        self.assertEqual(ask_index.done_line({"indexed": 0, "online_only": 4}), "No files to index")


class Words(unittest.TestCase):
    def test_the_approved_plural_lines(self):
        c = {"indexed": 180, "type": 242, "online_only": 8, "too_long": 2, "safety": 4}
        self.assertEqual(ask_index.line_for(c), "Indexed 180 of 436 files. 242 are of a type clark can't read yet. Online-only files not searched "
                                                "2 files are too long. 4 look like a password or a key and were left out.")
        self.assertEqual(ask_index.line_for(None, (180, 422)), "Indexing… 42%")

    def test_the_approved_singular_lines(self):
        c = {"indexed": 1, "type": 1, "online_only": 1, "too_long": 1, "safety": 1}
        self.assertEqual(ask_index.line_for(c), "Indexed 1 of 5 files. 1 is of a type clark can't read yet. Online-only files not searched "
                                                "1 file is too long. 1 looks like a password or a key and was left out.")
        self.assertEqual(ask_index.line_for(None, (1, 422)), "Indexing… 0%")
        self.assertEqual(ask_index.line_for(None, (422, 422)), "Indexing… 99%")
        self.assertEqual(ask_index.line_for(None, (0, 0)), "Indexing… 0%")
        self.assertEqual(ask_index.line_for(None, (1, 1)), "Indexing… 99%")   # one file, all read: still 99 (the 100 is the finished line)

    def test_only_the_reasons_above_zero_appear(self):
        self.assertEqual(ask_index.line_for({"indexed": 3, "type": 0, "safety": 2}), "Indexed 3 of 5 files. 2 look like a password or a key and were left out.")
        self.assertEqual(ask_index.line_for({"indexed": 3}), "Indexed 3 of 3 files.")


class Base(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)       # the never-read list is the Mac's
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.data = self.d / "data"
        self.home = self.d / "home"
        self.a, self.b = self.d / "alpha", self.d / "beta"
        for p in (self.data, self.home, self.a, self.b):
            p.mkdir(parents=True)

    def put(self, folder, name, text):
        (folder / name).write_text(text, encoding="utf-8")


class PerFolder(Base):
    def test_counts_are_per_folder_and_add_up_to_the_files_in_each(self):
        self.put(self.a, "one.txt", "alpha river")
        self.put(self.a, "two.md", "alpha lake")
        self.put(self.a, "pic.bin", "x")
        self.put(self.b, "three.txt", "beta ocean")
        self.put(self.b, "secret.txt", FAKE_KEY)
        self.assertTrue(ask_index.refresh(self.data, "ABC", [str(self.a), str(self.b)], self.home))
        got = ask_index.folder_status(self.data, "ABC", [str(self.a), str(self.b)])
        self.assertEqual(got[str(self.a)], {"state": "done", "line": "100% indexed. 1 file could not be read",
                                            "left": {"files": [["pic.bin", "of a type clark can't read yet"]], "more": 0}})
        self.assertEqual(got[str(self.b)], {"state": "done", "line": "100% indexed. 1 file could not be read",
                                            "left": {"files": [["secret.txt", "looks like a password or a key"]], "more": 0}})
        self.assertNotIn("hunter2", json.dumps(got))

    def test_a_folder_never_read_says_nothing(self):
        self.assertEqual(ask_index.folder_status(self.data, "ABC", [str(self.a)]), {})

    def test_current_only_for_the_same_folders_after_a_full_run(self):
        self.put(self.a, "one.txt", "alpha river")
        self.assertFalse(ask_index.current(self.data, "ABC", [str(self.a)]))
        ask_index.refresh(self.data, "ABC", [str(self.a)], self.home)
        self.assertTrue(ask_index.current(self.data, "ABC", [str(self.a)]))
        self.assertFalse(ask_index.current(self.data, "ABC", [str(self.a), str(self.b)]))

    def test_a_stopped_run_is_not_current_and_says_so_to_the_caller(self):
        for i in range(5):
            self.put(self.a, f"f{i}.txt", f"word{i}")
        stop = threading.Event()
        stop.set()
        self.assertFalse(ask_index.refresh(self.data, "ABC", [str(self.a)], self.home, stop=stop))
        self.assertFalse(ask_index.current(self.data, "ABC", [str(self.a)]))

    def test_progress_is_reported_per_folder_up_to_the_total(self):
        for i in range(4):
            self.put(self.a, f"f{i}.txt", f"word{i}")
        seen = []
        ask_index.refresh(self.data, "ABC", [str(self.a)], self.home, progress=lambda f, d, t: seen.append((f, d, t)))
        self.assertEqual(seen[0], (str(self.a), 0, 4))
        self.assertEqual(seen[-1], (str(self.a), 4, 4))


class LiveBeatsSaved(Base):
    def test_row_1371_a_folder_read_again_says_indexing_not_the_finished_line_of_its_last_read(self):
        self.put(self.a, "one.txt", "alpha river")
        self.put(self.b, "two.txt", "beta ocean")
        folders = [str(self.a), str(self.b)]
        self.assertTrue(ask_index.refresh(self.data, "ABC", folders, self.home))
        done = ask_index.folder_status(self.data, "ABC", folders)
        self.assertEqual(done[str(self.a)]["state"], "done")
        self.assertEqual(done[str(self.a)]["line"], "100% indexed")
        got = ask_index.folder_status(self.data, "ABC", folders, {str(self.a): (1, 4)})
        self.assertEqual(got[str(self.a)], {"state": "reading", "line": "Indexing\u2026 25%"})
        self.assertEqual(got[str(self.b)], done[str(self.b)])
        self.assertEqual(ask_index.folder_status(self.data, "ABC", folders, {}), done)


class Worker(Base):
    def test_a_run_in_the_background_shows_reading_then_indexed_and_busy_returns_to_zero(self):
        self.put(self.a, "one.txt", "alpha river")
        gate, entered = threading.Event(), threading.Event()
        real = ask_index.refresh

        def slow(data, code, folders, home=None, stop=None, progress=None):
            def held(f, d, t):
                progress(f, d, t)
                entered.set()
                gate.wait(5)
            return real(data, code, folders, home, stop=stop, progress=held)
        ix = ask_index.Indexer(self.data, self.home, refresh_fn=slow)
        self.addCleanup(ix.shutdown)
        self.assertTrue(ix.start("ABC", [str(self.a)]))
        self.assertTrue(entered.wait(5))
        self.assertEqual(ix.busy, 1)
        self.assertEqual(ix.status_for("ABC", [str(self.a)])[str(self.a)], {"state": "reading", "line": "Indexing… 0%"})
        self.assertFalse(ix.current("ABC", [str(self.a)]))
        gate.set()
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual(ix.busy, 0)
        self.assertEqual(ix.status_for("ABC", [str(self.a)])[str(self.a)]["line"], "100% indexed")
        self.assertTrue(ix.current("ABC", [str(self.a)]))

    def test_shutdown_stops_a_run_at_the_next_file_and_refuses_new_ones(self):
        for i in range(30):
            self.put(self.a, f"f{i}.txt", f"word{i}")
        entered, gate = threading.Event(), threading.Event()
        real = ask_index.refresh

        def slow(data, code, folders, home=None, stop=None, progress=None):
            def held(f, d, t):
                entered.set()
                gate.wait(5)
            return real(data, code, folders, home, stop=stop, progress=held)
        ix = ask_index.Indexer(self.data, self.home, refresh_fn=slow)
        ix.start("ABC", [str(self.a)])
        ix.start("OTH", [str(self.b)])
        self.assertEqual(ix.busy, 2)
        self.assertTrue(entered.wait(5))
        gate.set()
        ix.shutdown(5)
        self.assertEqual(ix.busy, 0)
        self.assertFalse(ix.current("ABC", [str(self.a)]))
        self.assertFalse(ix.start("ABC", [str(self.a)]))
        self.assertFalse(ix.thread and ix.thread.is_alive())

    def test_a_failing_run_leaves_busy_at_zero_and_the_worker_alive_for_the_next(self):
        calls = []

        def boom(data, code, folders, home=None, stop=None, progress=None):
            calls.append(code)
            raise RuntimeError("x")
        ix = ask_index.Indexer(self.data, self.home, refresh_fn=boom)
        self.addCleanup(ix.shutdown)
        ix.start("ABC", [])
        self.assertTrue(ix.wait_idle(5))
        ix.start("ABC", [])
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual((calls, ix.busy), (["ABC", "ABC"], 0))


class Route(Base):
    def setUp(self):
        super().setUp()
        self.db = self.data / "clark.db"
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Example Programme"})
        store.close()
        self.ix = ask_index.Indexer(self.data, self.home)
        self.addCleanup(self.ix.shutdown)
        self.svc = ask_folders.AskFolders(self.db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester", indexer=self.ix,
                                          choose_folder=lambda prompt, start=None: None)

    def test_adding_a_folder_starts_the_read_and_the_route_returns_its_line_and_removing_drops_the_index(self):
        self.put(self.a, "one.txt", "alpha river")
        status, body = self.svc.change({"project": "ABC", "action": "add", "path": str(self.a)})
        self.assertEqual(status, 200, body)
        self.assertTrue(self.ix.wait_idle(10))
        status, body = self.svc.read("ABC")
        self.assertEqual(body["index"], {str(self.a): {"state": "done", "line": "100% indexed"}})
        self.assertTrue(ask_index.path_for(self.data, "ABC").exists())
        self.svc.change({"project": "ABC", "action": "remove", "path": str(self.a)})
        self.assertTrue(self.ix.wait_idle(10))
        self.assertFalse(ask_index.path_for(self.data, "ABC").exists())
        self.assertEqual(self.svc.read("ABC")[1]["index"], {})

    def test_a_folder_for_all_projects_is_read_for_the_project_and_shown_with_it(self):
        self.put(self.b, "two.txt", "beta ocean")
        self.svc.change_all({"scope": "all", "action": "add", "path": str(self.b)})
        self.assertTrue(self.ix.wait_idle(10))
        self.assertEqual(self.svc.read_all("ABC")[1]["index"], {str(self.b): {"state": "done", "line": "100% indexed"}})
        self.assertEqual(self.svc.read("ABC")[1]["index"][str(self.b)]["state"], "done")
        self.assertNotIn("index", self.svc.read_all()[1])

    def test_without_a_worker_the_answers_have_no_index_key(self):
        plain = ask_folders.AskFolders(self.db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester")
        self.assertNotIn("index", plain.read("ABC")[1])


class Question(Base):
    def test_a_current_index_answers_with_no_file_read_and_a_missing_one_falls_back_to_the_raw_path(self):
        self.put(self.a, "plan.txt", "The zebrafish tank is cleaned on Tuesdays.")
        ix = ask_index.Indexer(self.data, self.home)
        self.addCleanup(ix.shutdown)
        ix.start("ABC", [str(self.a)])
        self.assertTrue(ix.wait_idle(10))
        self.assertTrue(ix.current("ABC", [str(self.a)]))
        with mock.patch.object(reach, "read_bytes", side_effect=AssertionError("a question opened a file")), \
                mock.patch.object(reach, "readable_files", side_effect=AssertionError("a question listed a folder")):
            found = ask_index.folder_data(self.data, "ABC", "when is the zebrafish tank cleaned")
        self.assertEqual(len(found.passages), 1)
        self.assertIn("zebrafish", found.passages[0].text)
        other = ask_index.Indexer(self.data, self.home)
        self.assertFalse(other.current("NEW", [str(self.a)]))
        raw = ask_passages.folder_data([str(self.a)], self.data, "zebrafish tank", ask.BUDGET, self.home)
        self.assertIn("zebrafish", raw.passages[0].text)


class AskPath(RouteBase):
    """POST /api/ask: a current index answers with the raw reader never called; a missing one calls it."""

    def asked(self, indexer):
        self.s.httpd.ask.indexer = indexer
        self.provider.reply = "Here is what I found."
        seen = []

        def raw(folders, *_a, **_kw):
            seen.append(list(folders))
            return ask_passages.FolderData(passages=())
        with mock.patch.object(ask_folders, "shared_folders", lambda _dir: ["/shared/one"]), \
                mock.patch.object(ask_service.ask_passages, "folder_data", raw), \
                mock.patch.object(ask_service.ask_index, "folder_data", return_value=ask_passages.FolderData(passages=())) as idx:
            status, got = self.s.api("POST", "/api/ask", {"project": "ABC", "question": "What should change?"})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        return seen, idx.call_count

    def test_a_current_index_is_used_and_the_raw_reader_is_not(self):
        seen, used = self.asked(mock.Mock(current=mock.Mock(return_value=True)))
        self.assertEqual((seen, used), ([], 1))

    def test_an_index_that_is_not_current_falls_back_to_the_raw_reader(self):
        seen, used = self.asked(mock.Mock(current=mock.Mock(return_value=False)))
        self.assertEqual((seen, used), ([["/shared/one"]], 0))


class FiveStates(Base):
    """Row 1371 (AP7): the server reports waiting, updating, paused, failed and cleared besides reading and done."""

    def held(self, gate, entered):
        real = ask_index.refresh

        def slow(data, code, folders, home=None, stop=None, progress=None):
            def hold(f, d, t):
                progress(f, d, t)
                entered.set()
                gate.wait(5)
            return real(data, code, folders, home, stop=stop, progress=hold)
        return slow

    def test_folder_status_reports_the_five_new_states(self):
        self.put(self.a, "one.txt", "alpha river")
        self.put(self.b, "two.txt", "beta ocean")
        a, b = str(self.a), str(self.b)
        # waiting: a run is going and has not reached a folder that has no index yet
        gate, entered = threading.Event(), threading.Event()
        ix = ask_index.Indexer(self.data, self.home, refresh_fn=self.held(gate, entered))
        self.addCleanup(ix.shutdown)
        ix.start("ABC", [a, b])
        self.assertTrue(entered.wait(5))
        got = ix.status_for("ABC", [a, b])
        self.assertEqual(got[a]["state"], "reading")
        self.assertEqual(got[b], {"state": "waiting", "line": "Waiting to index"})
        self.assertEqual(ix.peek("ABC", [a, b])[b]["state"], "waiting")      # the count of indexed projects reads the same states and starts nothing
        gate.set()
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual({v["state"] for v in ix.status_for("ABC", [a, b]).values()}, {"done"})
        # updating: a file of the folder not yet reached has changed since its last read
        self.put(self.b, "three.txt", "beta lake")
        self.put(self.b, "four.txt", "beta sea")
        gate.clear()
        entered.clear()
        ix.start("ABC", [a, b])
        self.assertTrue(entered.wait(5))
        got = ix.status_for("ABC", [a, b])
        self.assertEqual(got[b], {"state": "updating", "line": "Updating\u2026 2 files changed", "changed": 2})
        self.assertEqual(got[a]["state"], "reading")
        gate.set()
        self.assertTrue(ix.wait_idle(5))
        # cleared: the index file was deleted after the line had shown it; nothing starts by itself
        ask_index.remove(self.data, "ABC")
        got = ix.status_for("ABC", [a, b])
        self.assertEqual({v["state"] for v in got.values()}, {"cleared"})
        self.assertEqual(got[a]["line"], "Not indexed.")
        self.assertFalse(ask_index.path_for(self.data, "ABC").exists())
        self.assertEqual(ix.busy, 0)

    def test_one_changed_file_says_1_file(self):
        self.put(self.a, "one.txt", "alpha river")
        self.put(self.b, "two.txt", "beta ocean")
        a, b = str(self.a), str(self.b)
        self.assertTrue(ask_index.refresh(self.data, "ABC", [a, b], self.home))
        self.put(self.b, "three.txt", "beta lake")
        self.assertEqual(ask_index.changed_by_folder(self.data, "ABC", [a, b], self.home), {b: 1})
        (self.b / "three.txt").unlink()
        (self.b / "two.txt").unlink()
        self.assertEqual(ask_index.changed_by_folder(self.data, "ABC", [a, b], self.home), {b: 1})      # a file gone counts too
        self.put(self.b, "three.txt", "beta lake")
        got = ask_index.folder_status(self.data, "ABC", [a, b], {a: (0, 1)}, busy=True, changed={b: 1})
        self.assertEqual(got[b]["line"], "Updating\u2026 1 file changed")

    def test_a_stopped_first_pass_says_paused_and_a_failed_run_says_failed_until_started_again(self):
        self.put(self.a, "one.txt", "alpha river")
        a = str(self.a)
        stop = threading.Event()
        stop.set()
        ask_index.refresh(self.data, "ABC", [a], self.home, stop=stop)
        ix = ask_index.Indexer(self.data, self.home)
        self.addCleanup(ix.shutdown)
        ix.stop.set()                                   # clark is closing: the read cannot carry on now
        self.assertEqual(ix.status_for("ABC", [a])[a], {"state": "paused", "line": "Indexing paused. It carries on when clark is open"})
        calls = []

        def boom(data, code, folders, home=None, stop=None, progress=None):
            calls.append(code)
            raise RuntimeError("x")
        bad = ask_index.Indexer(self.data, self.home, refresh_fn=boom)
        self.addCleanup(bad.shutdown)
        bad.start("ABC", [a])
        self.assertTrue(bad.wait_idle(5))
        self.assertEqual(bad.status_for("ABC", [a])[a], {"state": "failed", "line": "Could not index this folder."})
        self.assertEqual(bad.status_for("ABC", [a])[a]["state"], "failed")
        self.assertEqual(calls, ["ABC"])                # the poll does not start it again
        bad.start("ABC", [a])                           # the link: Try again
        self.assertTrue(bad.wait_idle(5))
        self.assertEqual(calls, ["ABC", "ABC"])

    def test_a_read_started_again_clears_failed_and_cleared_and_asking_off_forgets_the_index(self):
        self.put(self.a, "one.txt", "alpha river")
        a = str(self.a)
        flag = {"fail": True, "on": True}
        real = ask_index.refresh

        def once(data, code, folders, home=None, stop=None, progress=None):
            if flag["fail"]:
                raise RuntimeError("x")
            return real(data, code, folders, home, stop=stop, progress=progress)
        ix = ask_index.Indexer(self.data, self.home, refresh_fn=once, allowed=lambda: flag["on"])
        self.addCleanup(ix.shutdown)
        ix.start("ABC", [a])
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual(ix.status_for("ABC", [a])[a]["state"], "failed")
        flag["fail"] = False
        ix.start("ABC", [a])                            # Try again
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual(ix.status_for("ABC", [a])[a]["state"], "done")
        ask_index.remove(self.data, "ABC")
        self.assertEqual(ix.status_for("ABC", [a])[a]["state"], "cleared")
        ix.start("ABC", [a])                            # Index again
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual(ix.status_for("ABC", [a])[a]["state"], "done")
        flag["on"] = False                              # asking Off deletes the index; On again builds it, it is not "cleared"
        self.assertEqual(ix.status_for("ABC", [a]), {})
        flag["on"] = True
        ix.checked.clear()                              # the poll looks at most once every few seconds
        self.assertNotEqual(ix.status_for("ABC", [a]).get(a, {}).get("state"), "cleared")
        self.assertTrue(ix.wait_idle(5))
        self.assertEqual(ix.status_for("ABC", [a])[a]["state"], "done")


class IndexAgain(Route):
    """Row 1371: the Try again and Index again links ask the server to read the folders again (action "reindex", nothing saved)."""

    def test_reindex_starts_the_read_once_and_takes_no_path(self):
        self.put(self.a, "one.txt", "alpha river")
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.a)})
        self.assertTrue(self.ix.wait_idle(10))
        with mock.patch.object(self.svc, "reindex") as re:
            status, body = self.svc.change({"project": "ABC", "action": "reindex"})
        self.assertEqual((status, body["ok"], re.call_count), (200, True, 1))
        self.assertEqual(self.svc.change({"project": "ABC", "action": "reindex", "path": str(self.a)})[0], 400)
        with mock.patch.object(self.svc, "reindex") as re:
            status, body = self.svc.change_all({"scope": "all", "action": "reindex"})
        self.assertEqual((status, body["ok"], re.call_count), (200, True, 1))

    def test_the_all_projects_read_counts_the_projects_indexed(self):
        self.put(self.a, "one.txt", "alpha river")
        self.svc.change_all({"scope": "all", "action": "add", "path": str(self.a)})
        self.assertTrue(self.ix.wait_idle(10))
        self.assertEqual(self.svc.read_all("ABC")[1]["projects"], {str(self.a): [1, 1]})

    def test_the_count_leaves_out_archived_projects_and_counts_only_finished_ones(self):
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "NEW", "name": "Second"})
            step.create("projects", {"code": "OLD", "name": "Old"})
        with store.step("dashboard", "tester", place="menu") as step:
            step.archive("projects", "OLD")
        store.close()
        self.put(self.a, "one.txt", "alpha river")
        with mock.patch.object(self.svc, "reindex"):
            self.svc.change_all({"scope": "all", "action": "add", "path": str(self.a)})
        self.ix.start("ABC", [str(self.a)])
        self.assertTrue(self.ix.wait_idle(10))
        self.assertEqual(self.svc.read_all("ABC")[1]["projects"], {str(self.a): [1, 2]})      # NEW has no index yet; OLD is archived


if __name__ == "__main__":
    unittest.main()
