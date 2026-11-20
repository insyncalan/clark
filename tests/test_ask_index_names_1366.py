"""Row 1366: three holes in the index of a project's documents. (1) two saved folders with the same name (a/docs, b/docs) give files
that share one label, so the second file was missing from answers; (2) text indexed under an older secret screen was still given out
after the screen got tighter; (3) with asking Off the index is neither built nor kept.

Run: python3 dev/run_tests.py test_ask_index_names_1366
Every file is made in the test from made-up text.
"""
import sqlite3
import threading
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from clark import app_settings, ask_index, store as st


class SameName(Base):
    def files(self, word):
        return sorted(p[0].split(", ")[0] for p in self.found(word))

    def two(self):
        a, b = self.d / "a" / "docs", self.d / "b" / "docs"
        self.put("notes.txt", "zqsame alpha text", folder=a)
        self.put("notes.txt", "zqsame bravo text", folder=b)
        return [a, b]

    def test_the_same_file_name_in_two_folders_of_the_same_name_keeps_both_files_with_their_own_label(self):
        folders = self.build(folders=self.two())
        got = self.found("zqsame")
        self.assertEqual(sorted(p[0].split(", ")[0] for p in got), ["a/docs/notes.txt", "b/docs/notes.txt"])
        self.assertEqual(len({p[0] for p in got}), 2)
        self.assertEqual(ask_index.status(self.data, "P1")["indexed"], 2)
        self.assertFalse(ask_index.stale(self.data, "P1", folders), "and the check for changed files agrees with the labels")

    def test_a_folder_of_a_name_no_other_has_the_label_it_always_had(self):
        self.put("notes.txt", "zqplain text", folder=self.d / "x" / "docs")
        self.put("notes.txt", "zqplain more", folder=self.d / "y" / "other")
        self.build(folders=[self.d / "x" / "docs", self.d / "y" / "other"])
        self.assertEqual(self.files("zqplain"), ["docs/notes.txt", "other/notes.txt"])

    def test_folders_that_share_the_parent_name_too_are_told_apart_further_up(self):
        a, b = self.d / "p" / "a" / "docs", self.d / "q" / "a" / "docs"
        self.put("n.txt", "zqdeep one", folder=a)
        self.put("n.txt", "zqdeep two", folder=b)
        self.build(folders=[a, b])
        self.assertEqual(self.files("zqdeep"), ["p/a/docs/n.txt", "q/a/docs/n.txt"])

    def test_the_left_out_list_gives_each_same_name_folder_its_own_file(self):
        a, b = self.d / "a" / "docs", self.d / "b" / "docs"
        self.put("one.bin", "x", folder=a)
        self.put("two.bin", "x", folder=b)
        folders = self.build(folders=[a, b])
        left = ask_index._left_by_folder(self.data, "P1", [str(f) for f in folders])
        self.assertEqual({k: [n for n, _r in v["files"]] for k, v in left.items()}, {str(a): ["one.bin"], str(b): ["two.bin"]})


class ScreenVersion(Base):
    def setUp(self):
        super().setUp()
        self.put("a.txt", "zqscreen plain words")
        self.folders = self.build()

    def old_screen(self, value=None):
        con = sqlite3.connect(ask_index.path_for(self.data, "P1"))
        if value is None:
            con.execute("DELETE FROM meta WHERE k='screen'")
        else:
            con.execute("INSERT OR REPLACE INTO meta VALUES('screen', ?)", (value,))
        con.commit()
        con.close()

    def test_an_index_made_under_this_screen_is_read_as_before(self):
        self.assertEqual(len(self.found("zqscreen")), 1)
        self.assertTrue(ask_index.current(self.data, "P1", self.folders))
        self.assertFalse(ask_index.stale(self.data, "P1", self.folders))

    def test_text_screened_by_an_older_version_is_not_given_out_or_called_current(self):
        for old in (None, str(ask_index.SCREEN_VERSION - 1)):
            self.old_screen(old)
            self.assertEqual(self.found("zqscreen"), [], old)
            self.assertFalse(ask_index.current(self.data, "P1", self.folders), old)
            self.assertTrue(ask_index.stale(self.data, "P1", self.folders), old)
            ix.refresh(self.data, "P1", self.folders)
            self.assertEqual(len(self.found("zqscreen")), 1, "read again, it is given out again")

    def test_a_file_that_the_tighter_screen_refuses_is_left_out_though_it_did_not_change(self):
        self.old_screen(str(ask_index.SCREEN_VERSION - 1))
        with mock.patch.object(ask_index.secret_screen, "looks_like_secret", return_value=True):
            ix.refresh(self.data, "P1", self.folders)
        self.assertEqual(self.found("zqscreen"), [])
        self.assertEqual(ask_index.status(self.data, "P1")["safety"], 1)

    def test_an_unchanged_file_is_not_read_again_while_the_version_is_the_same(self):
        with mock.patch.object(ask_index, "_read_one", side_effect=AssertionError("read again")):
            ix.refresh(self.data, "P1", self.folders)


class AskingOff(Base):
    def setUp(self):
        super().setUp()
        self.put("a.txt", "zqoff plain words")
        self.folders = [str(self.box)]
        self.on = True
        self.ix = ask_index.Indexer(self.data, None, allowed=lambda: self.on)
        self.addCleanup(self.ix.shutdown)

    def exists(self):
        return ask_index.path_for(self.data, "P1").exists()

    def test_with_asking_on_the_index_is_built(self):
        self.ix.start("P1", self.folders)
        self.assertTrue(self.ix.wait_idle(10))
        self.assertTrue(self.exists())

    def test_with_asking_off_nothing_is_built_by_a_start_a_poll_or_a_question(self):
        self.on = False
        self.assertFalse(self.ix.start("P1", self.folders))
        self.assertEqual(self.ix.status_for("P1", self.folders), {})
        self.assertFalse(self.ix.current("P1", self.folders))
        self.assertFalse(self.ix.resume("P1", self.folders))
        self.assertTrue(self.ix.wait_idle(10))
        self.assertFalse(self.exists())

    def test_with_asking_off_an_index_made_earlier_is_deleted(self):
        self.build()
        self.assertTrue(self.exists())
        self.on = False
        self.ix.status_for("P1", self.folders)
        self.assertFalse(self.exists())

    def test_a_run_waiting_when_asking_is_turned_off_builds_nothing(self):
        calls, hold, begun = [], threading.Event(), threading.Event()

        def refresh(data_dir, code, *a, **k):
            calls.append(code)
            begun.set()
            hold.wait(10)
        ix2 = ask_index.Indexer(self.data, None, refresh_fn=refresh, allowed=lambda: self.on)
        self.addCleanup(ix2.shutdown)
        self.addCleanup(hold.set)
        ix2.start("P1", self.folders)
        self.assertTrue(begun.wait(10))
        ix2.start("P2", self.folders)                      # waits behind P1
        self.on = False                                    # asking is turned Off while P1 runs and P2 waits
        hold.set()
        self.assertTrue(ix2.wait_idle(10))
        self.assertEqual(calls, ["P1"], "P2 is not built")

    def test_a_switch_that_cannot_be_read_is_off(self):
        def boom():
            raise OSError("no")
        ix2 = ask_index.Indexer(self.data, None, allowed=boom)
        self.addCleanup(ix2.shutdown)
        self.assertFalse(ix2.start("P1", self.folders))
        self.assertFalse(self.exists())

    def test_turning_asking_off_in_settings_deletes_every_index(self):
        db = self.d / "clark.db"
        store = st.open_store(db, onedrive_roots=[])
        store.close()
        service = app_settings.AppSettings(db, [], by_user=lambda: "tester")
        data = db.parent
        self.build(code="P1")
        self.build(code="P2")
        # the indexes live beside the data file
        for c in ("P1", "P2"):
            ix.build(data, c, [self.box])
        self.assertTrue(ask_index.path_for(data, "P1").exists())
        status, _ = service.change_ask({"enabled": False})
        self.assertEqual(status, 200)
        self.assertFalse(ask_index.path_for(data, "P1").exists())
        self.assertFalse(ask_index.path_for(data, "P2").exists())
        self.assertFalse((data / "ask-index").exists() and any((data / "ask-index").iterdir()))


if __name__ == "__main__":
    unittest.main()
