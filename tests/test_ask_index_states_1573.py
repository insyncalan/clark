"""Row 1573 (parent row 1371, AP10 to AP15): the states of the status line under a source folder that are not reading and done:
waiting, updating, paused, failed, cleared and "Indexed for N of N projects". The server states (no browser), then the page at 1400 and 900 (Classic).

Run: python3 dev/run_tests.py test_ask_index_states_1573
Every file is made in the test from made-up text.
"""
import time
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_page_1366 import Fixture, WIDTHS
from test_server import chrome
from clark import ask_folders, ask_index


class Server(Fixture):
    def test_a_folder_not_yet_read_waits_while_a_run_is_queued_or_on_another_folder(self):
        got = ask_index.folder_status(self.data, "ABC", [str(self.own)], pending=True)
        self.assertEqual(got[str(self.own)], {"state": "waiting", "line": "Waiting to index"})
        self.assertEqual(ask_index.folder_status(self.data, "ABC", [str(self.own)]), {})

    def test_a_run_that_raised_says_failed_until_it_is_started_again(self):
        def boom(*a, **k):
            raise RuntimeError("no")
        ix = ask_index.Indexer(self.data, self.home, refresh_fn=boom)
        self.addCleanup(ix.shutdown)
        ix.start("ABC", [str(self.own)])
        self.assertTrue(ix.wait_idle(10))
        ix.checked["ABC"] = time.monotonic()
        self.assertEqual(ix.status_for("ABC", [str(self.own)])[str(self.own)]["state"], "failed")
        ix.start("ABC", [str(self.own)])
        self.assertNotIn("ABC", ix.failed)

    def test_a_read_that_was_begun_and_is_not_going_says_paused(self):
        import threading
        stop = threading.Event()
        stop.set()
        self.assertFalse(ask_index.refresh(self.data, "ABC", [str(self.own)], self.home, stop=stop))
        self.ix.checked["ABC"] = time.monotonic()
        self.ix.resumed["ABC"] = time.monotonic()
        self.assertEqual(self.ix.status_for("ABC", [str(self.own)])[str(self.own)]["state"], "paused")

    def test_a_change_found_counts_the_files_new_or_changed_in_each_folder(self):
        folders = [str(self.own)]
        self.assertTrue(ask_index.refresh(self.data, "ABC", folders, self.home))
        self.assertEqual(ask_index.changes(self.data, "ABC", folders, self.home), (False, {}))
        (self.own / "new.txt").write_text("gamma", encoding="utf-8")
        (self.own / "a.txt").write_text("alpha river and more", encoding="utf-8")
        self.assertEqual(ask_index.changes(self.data, "ABC", folders, self.home), (True, {str(self.own): 2}))
        got = ask_index.folder_status(self.data, "ABC", folders, {str(self.own): (1, 2)}, changed={str(self.own): 2})
        self.assertEqual((got[str(self.own)]["state"], got[str(self.own)]["changed"]), ("updating", 2))

    def test_the_reindex_action_starts_the_read_and_takes_no_path(self):
        with mock.patch.object(self.ix, "start") as start:
            status, out = self.svc.change({"project": "ABC", "action": "reindex"})
        self.assertEqual((status, out["ok"]), (200, True))
        start.assert_called_once()
        self.assertEqual(self.svc.change({"project": "ABC", "action": "reindex", "path": "/x"})[0], 400)

    def test_the_all_projects_count_is_the_projects_whose_index_is_finished(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.assertTrue(self.ix.wait_idle(10))
        done, every = self.svc.read_all()[1]["projects"][str(self.shared)]
        self.assertTrue(0 < done <= every)


class Page(Fixture):
    def canned(self, folder, line):
        return mock.patch.object(self.ix, "status_for", return_value={folder: line})

    def test_each_state_shows_its_words_at_both_widths(self):
        own = str(self.own)
        cases = [({"state": "waiting", "line": "x"}, "Waiting to index"),
                 ({"state": "updating", "line": "x", "changed": 3}, "Updating… 3 files changed"),
                 ({"state": "updating", "line": "x", "changed": 1}, "Updating… 1 file changed"),
                 ({"state": "paused", "line": "x"}, "Indexing paused. It carries on when clark is open"),
                 ({"state": "failed", "line": "x"}, "Could not index this folder. Try again"),
                 ({"state": "cleared", "line": "x"}, "Not indexed. Index again")]
        self.svc.change({"project": "ABC", "action": "add", "path": own})
        self.assertTrue(self.ix.wait_idle(10))
        for line, want in cases:
            with self.canned(own, line), chrome() as cdp:
                js = self.show(cdp, "project")
                for w in WIDTHS:
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    self.until(js, "document.querySelector('#ask-folders .ask-folder-line').innerText === %r" % want, f"{want} at {w}")

    def test_try_again_and_index_again_are_real_controls_that_ask_for_the_read(self):
        own = str(self.own)
        self.svc.change({"project": "ABC", "action": "add", "path": own})
        self.assertTrue(self.ix.wait_idle(10))
        for state, name in (("failed", "Try again"), ("cleared", "Index again")):
            with self.canned(own, {"state": state, "line": "x"}), mock.patch.object(self.svc, "reindex") as again, chrome() as cdp:
                js = self.show(cdp, "project")
                self.until(js, "!!document.querySelector('#ask-folders .ask-folder-line button')", "the link")
                self.assertEqual(js("(() => { const b = document.querySelector('#ask-folders .ask-folder-line button'); return [b.tagName, b.innerText]; })()"), ["BUTTON", name])
                js("document.querySelector('#ask-folders .ask-folder-line button').click()")
                self.until(js, "true", "clicked")
                self.assertTrue(__import__("test_server").wait(lambda: again.called, 10))


if __name__ == "__main__":
    unittest.main()
