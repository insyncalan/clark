"""Row 1366: three holes in the index of a project's documents. (1) two saved folders with the same name (a/docs, b/docs) give files
that share one label, so the second file was missing from answers; (2) text indexed under an older secret screen was still given out
after the screen got tighter; (3) with asking Off the index is neither built nor kept.

Run: python3 dev/run_tests.py test_ask_index_names_1366
Every file is made in the test from made-up text.
"""
import io
import os
import sqlite3
import threading
import time
import unittest
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import FAKE_KEY, Base, ix
from clark import __main__ as launcher
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


class RefusedFolder(Base):
    def refuse(self, bad):
        real = ask_index.reach.never_inside
        return mock.patch.object(ask_index.reach, "never_inside", side_effect=lambda f, d, h: "refused" if str(f) == str(bad) else real(f, d, h))

    def test_a_folder_refused_for_a_reason_is_never_usable_and_a_normal_one_is(self):
        good, bad = self.d / "good", self.d / "bad"
        good.mkdir()
        bad.mkdir()
        with self.refuse(bad):
            self.assertEqual(ask_index._unusable([good, bad], self.data, None), ([good], [bad]))
            self.assertEqual(ask_index._unusable([bad], self.data, None), ([], [bad]))
            self.assertEqual(ask_index._unusable([good], self.data, None), ([good], []))

    def test_a_refused_folder_gives_no_passage_and_counts_as_safety_while_the_other_is_searched(self):
        good, bad = self.d / "good", self.d / "bad"
        self.put("a.txt", "zqrefuse good words", folder=good)
        self.put("b.txt", "zqrefuse bad words", folder=bad)
        with self.refuse(bad):
            ix.refresh(self.data, "P1", [good, bad])
        got = self.found("zqrefuse")
        self.assertEqual(len(got), 1)
        self.assertIn("good", got[0][0])
        self.assertEqual(ask_index.status(self.data, "P1")["safety"], 1)


class RefusedFolderFailsClosed(Base):
    def test_a_folder_whose_check_raises_is_unusable_not_usable(self):
        f = self.d / "x"
        f.mkdir()
        for exc in (OSError("no"), ValueError("no"), RuntimeError("no")):
            with mock.patch.object(ask_index.reach, "never_inside", side_effect=exc):
                self.assertEqual(ask_index._unusable([f], self.data, None), ([], [f]), repr(exc))

    def test_such_a_folder_gives_no_passage(self):
        self.put("a.txt", "zqraise words")
        with mock.patch.object(ask_index.reach, "never_inside", side_effect=OSError("no")):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(self.found("zqraise"), [])


class RemovedText(Base):
    """A removed file's text is not left in the index file (it holds text of the user's documents)."""

    def test_the_index_is_opened_with_secure_delete_on(self):
        db = ask_index._open(self.data, "P1")
        self.addCleanup(db.close)
        self.assertEqual(db.execute("PRAGMA secure_delete").fetchone()[0], 1)

    def test_text_of_a_file_removed_from_the_folder_is_gone_from_the_index_bytes(self):
        word = "zqgone" + "x" * 40
        gone = self.put("gone.txt", (word + " filler words here ") * 200)
        self.put("keep.txt", "zqkeep stays " * 300)
        ix.build(self.data, "P1", [self.box])
        path = ix.path_for(self.data, "P1")
        gone.unlink()
        ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(self.found(word), [])
        self.assertNotIn(word.encode(), path.read_bytes())
        for suffix in ("-wal", "-journal"):
            side = path.with_name(path.name + suffix)
            self.assertFalse(side.exists() and word.encode() in side.read_bytes())

    def test_a_refresh_that_ends_runs_vacuum_on_the_index(self):
        seen = []
        real = ask_index.sqlite3.connect

        class Spy:
            def __init__(self, db):
                self.db = db

            def execute(self, sql, *a):
                seen.append(sql)
                return self.db.execute(sql, *a)

            def __getattr__(self, name):
                return getattr(self.db, name)

        self.put("a.txt", "zqvac words")
        with mock.patch.object(ask_index.sqlite3, "connect", side_effect=lambda *a, **k: Spy(real(*a, **k))):
            ix.build(self.data, "P1", [self.box])
        self.assertIn("VACUUM", seen)
        self.assertIn("PRAGMA secure_delete=ON", seen)


def small_zip(sizes):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        for i, n in enumerate(sizes):
            z.writestr(f"p{i}.xml", b"a" * n)
    return out.getvalue()


class Stream(io.RawIOBase):
    """A zip member that holds `n` bytes whatever its header says."""
    def __init__(self, n):
        self.left = n

    def readable(self):
        return True

    def read(self, k=-1):
        k = min(k if k and k > 0 else 1 << 20, self.left)
        self.left -= k
        return b"a" * k

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class GoneAfterListing:
    """`os` as ask_index sees it, where stat of one file fails (the file went after it was listed); everything else is the real os."""
    def __init__(self, ending):
        self.ending = ending

    def __getattr__(self, name):
        return getattr(os, name)

    def stat(self, p, *args, **kw):
        if str(p).endswith(self.ending):
            raise OSError("gone")
        return os.stat(p, *args, **kw)


class Pins(unittest.TestCase):
    """Row 1366: the approved limits and words (a changed value is a change someone must approve)."""

    def test_the_limits_and_words(self):
        m = ask_index
        self.assertEqual((m.MAX_PARTS_PER_FILE, m.STALE_POLL_SECONDS, m.SCREEN_VERSION, m.MAX_LEFT_OUT_SHOWN), (5000, 5, 2, 200))
        self.assertEqual((m.MAX_PPTX_BYTES, m.MAX_EXCEL_BYTES, m.MAX_EXCEL_ROWS, m.MAX_EXCEL_CELLS, m.MAX_EXCEL_MEMBERS),
                         (50 * 1024 * 1024, 25 * 1024 * 1024, 50000, 1000000, 2000))
        self.assertEqual((m.MAX_EXCEL_TOTAL, m.MAX_EXCEL_SHARED, m.MAX_EXCEL_PART, m.MAX_EXCEL_SECONDS), (50 * 1024 * 1024, 8 * 1024 * 1024, 30 * 1024 * 1024, 20))
        self.assertEqual(m.NAMES, ("indexed", "type", "online_only", "too_long", "safety", "picture", "not_yet"))
        self.assertEqual(m.COUNTED, ("indexed", "type", "too_long", "picture"))
        self.assertEqual((m.REASON_TYPE, m.REASON_SAFETY, m.REASON_TOO_LONG_PDF, m.REASON_TOO_LONG, m.REASON_PICTURE),
                         ("of a type clark can't read yet", "looks like a password or a key", "is a PDF that is too long", "is too long", "is a picture and this computer cannot read pictures"))
        self.assertEqual(m.MAX_RESULTS, m.ask.MAX_PASSAGES)

    def test_the_default_waits(self):
        import inspect
        self.assertEqual(inspect.signature(ask_index.Indexer.wait_idle).parameters["timeout"].default, 10)
        self.assertEqual(inspect.signature(ask_index.Indexer.shutdown).parameters["timeout"].default, 5)


class Names(Base):
    def test_the_file_of_a_project_is_named_from_a_safe_code(self):
        d = self.data
        self.assertEqual(ask_index.path_for(d, "a/b").name, "a_b.db")
        self.assertEqual(ask_index.path_for(d, "..x").name, "x.db")
        self.assertEqual(ask_index.path_for(d, "...").name, "project.db")
        self.assertEqual(ask_index.path_for(d, "").name, "project.db")
        self.assertEqual(ask_index.path_for(d, "../../x").parent, d / "ask-index")

    def test_remove_all_deletes_every_index_file_and_nothing_else(self):
        folder = self.data / "ask-index"
        folder.mkdir()
        for n in ("a.db", "a.db-wal", "a.db-shm", "a.db-journal", "keep.txt"):
            (folder / n).write_bytes(b"x")
        ask_index.remove_all(self.data)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["keep.txt"])
        ask_index.remove_all(self.d / "none")                   # no folder: nothing to do

    def test_remove_takes_the_side_files_too_and_is_quiet_when_none(self):
        ix.build(self.data, "P1", [self.box])
        base = ix.path_for(self.data, "P1")
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(base) + suffix).write_bytes(b"x")
        ask_index.remove(self.data, "P1")
        self.assertEqual(list(base.parent.iterdir()), [])
        ask_index.remove(self.data, "P1")

    def test_the_folder_and_file_are_private_and_made_when_the_data_folder_has_no_such_path(self):
        data = self.d / "deep" / "er"
        db = ask_index._open(data, "P1")
        db.close()
        self.assertEqual(os.stat(data / "ask-index").st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(data / "ask-index" / "P1.db").st_mode & 0o777, 0o600)
        ask_index._open(data, "P1").close()
        self.assertIsNone(ask_index._open(self.d / "nope", "P1", create=False))


class LinesOf(unittest.TestCase):
    def test_a_word_file_is_read_as_word_and_a_cut_one_is_refused(self):
        with mock.patch.object(ask_index.ask_passages, "_lines_of_word", return_value=["w"]) as w:
            self.assertEqual(ask_index._lines(b"r", False, "a.docx", "a.docx"), ["w"])
            w.assert_called_once_with(b"r", "a.docx")
            with self.assertRaises(ask_index.docx_read.WordRefused) as c:
                ask_index._lines(b"r", True, "a.docx", "a.docx")
            self.assertEqual(str(c.exception), "too big")
        with mock.patch.object(ask_index.ask_passages, "_lines_of_text", return_value=["t"]) as t:
            self.assertEqual(ask_index._lines(b"r", True, "a.txt", "a.txt"), ["t"])
            t.assert_called_once_with(b"r", True)


class ExcelLimits(Base):
    def test_a_damaged_zip_is_an_excel_error_with_its_word(self):
        with self.assertRaises(ValueError) as c:
            ask_index._check_excel_zip(b"not a zip")
        self.assertEqual(str(c.exception), "excel")

    def test_too_many_parts_and_the_words_of_each_refusal(self):
        with mock.patch.object(ask_index, "MAX_EXCEL_MEMBERS", 2):
            with self.assertRaises(ask_index.TooLong) as c:
                ask_index._check_excel_zip(small_zip([1, 1, 1]))
            self.assertEqual(str(c.exception), "too many parts")
            ask_index._check_excel_zip(small_zip([1, 1]))
        with mock.patch.object(ask_index, "MAX_EXCEL_TOTAL", 10), mock.patch.object(ask_index, "MAX_EXCEL_PART", 100):
            with self.assertRaises(ask_index.TooLong) as c:
                ask_index._check_excel_zip(small_zip([6, 6]))
            self.assertEqual(str(c.exception), "too big once unpacked")
            ask_index._check_excel_zip(small_zip([5, 5]))           # exactly the total: allowed

    def test_one_part_over_its_cap_alone_refuses_and_exactly_the_cap_does_not(self):
        with mock.patch.object(ask_index, "MAX_EXCEL_PART", 10), mock.patch.object(ask_index, "MAX_EXCEL_TOTAL", 1000):
            with self.assertRaises(ask_index.TooLong):
                ask_index._check_excel_zip(small_zip([11]))
            ask_index._check_excel_zip(small_zip([10]))
        shared = io.BytesIO()
        with zipfile.ZipFile(shared, "w") as z:
            z.writestr("xl/sharedStrings.xml", b"a" * 11)
        with mock.patch.object(ask_index, "MAX_EXCEL_SHARED", 10), mock.patch.object(ask_index, "MAX_EXCEL_PART", 1000):
            with self.assertRaises(ask_index.TooLong):
                ask_index._check_excel_zip(shared.getvalue())

    def test_unpacked_bytes_over_a_cap_stop_it_though_the_headers_say_less(self):
        one, two = small_zip([1]), small_zip([1, 1])
        with mock.patch("zipfile.ZipFile.open", side_effect=lambda *a, **k: Stream(11)):
            with mock.patch.object(ask_index, "MAX_EXCEL_PART", 10), mock.patch.object(ask_index, "MAX_EXCEL_TOTAL", 1000):
                with self.assertRaises(ask_index.TooLong) as c:
                    ask_index._check_excel_zip(one)
                self.assertEqual(str(c.exception), "too big once unpacked")
        with mock.patch("zipfile.ZipFile.open", side_effect=lambda *a, **k: Stream(8)):
            with mock.patch.object(ask_index, "MAX_EXCEL_PART", 10), mock.patch.object(ask_index, "MAX_EXCEL_TOTAL", 15):
                with self.assertRaises(ask_index.TooLong):              # each part is under its cap, together they are over the total
                    ask_index._check_excel_zip(two)
        with mock.patch("zipfile.ZipFile.open", side_effect=lambda *a, **k: Stream(8)):
            with mock.patch.object(ask_index, "MAX_EXCEL_PART", 10), mock.patch.object(ask_index, "MAX_EXCEL_TOTAL", 16):
                ask_index._check_excel_zip(two)           # exactly the total: allowed
        with mock.patch("zipfile.ZipFile.open", side_effect=lambda *a, **k: Stream(10)):
            with mock.patch.object(ask_index, "MAX_EXCEL_PART", 10), mock.patch.object(ask_index, "MAX_EXCEL_TOTAL", 1000):
                ask_index._check_excel_zip(one)              # exactly the cap: allowed

    def test_a_broken_stream_is_an_excel_error(self):
        raw = small_zip([1])
        with mock.patch("zipfile.ZipFile.open", side_effect=EOFError("x")):
            with self.assertRaises(ValueError) as c:
                ask_index._check_excel_zip(raw)
        self.assertEqual(str(c.exception), "excel")

    def test_a_cut_or_too_big_workbook_is_too_long(self):
        from test_ask_index_types_1366 import xlsx
        raw = xlsx({"S": [["a"]]})
        with self.assertRaises(ask_index.TooLong) as c:
            ask_index._excel_groups(raw, True)
        self.assertEqual(str(c.exception), "too big")
        with mock.patch.object(ask_index, "MAX_EXCEL_BYTES", len(raw) - 1):
            with self.assertRaises(ask_index.TooLong):
                ask_index._excel_groups(raw, False)
        with mock.patch.object(ask_index, "MAX_EXCEL_BYTES", len(raw)):
            self.assertEqual(len(ask_index._excel_groups(raw, False)), 1)

    def test_a_workbook_openpyxl_cannot_open_is_an_excel_error(self):
        from test_ask_index_types_1366 import xlsx
        with mock.patch("openpyxl.load_workbook", side_effect=RuntimeError("x")):
            with self.assertRaises(ValueError) as c:
                ask_index._excel_groups(xlsx({"S": [["a"]]}), False)
        self.assertEqual(str(c.exception), "excel")

    def test_the_row_limit_and_the_cell_limit_each_refuse_a_sheet_alone(self):
        from test_ask_index_types_1366 import xlsx
        raw = xlsx({"S": [[f"w{i}", f"v{i}"] for i in range(6)]})
        with mock.patch.object(ask_index, "MAX_EXCEL_ROWS", 3):
            with self.assertRaises(ask_index.TooLong):
                ask_index._excel_groups(raw, False)
        with mock.patch.object(ask_index, "MAX_EXCEL_ROWS", 6):
            self.assertEqual(len(ask_index._excel_groups(raw, False)[0][1]), 6)
        with mock.patch.object(ask_index, "MAX_EXCEL_CELLS", 4):
            with self.assertRaises(ask_index.TooLong):
                ask_index._excel_groups(raw, False)
        with mock.patch.object(ask_index, "MAX_EXCEL_CELLS", 12):
            self.assertEqual(len(ask_index._excel_groups(raw, False)[0][1]), 6)
        self.assertEqual(len(ask_index._excel_groups(raw, False)[0][1]), 6)

    def test_a_workbook_that_takes_too_long_says_so(self):
        from test_ask_index_types_1366 import xlsx
        ticks = iter(range(0, 1000, 30))
        with mock.patch.object(ask_index, "CLOCK", lambda: next(ticks)):
            with self.assertRaises(ask_index.TooLong) as c:
                ask_index._excel_groups(xlsx({"S": [["a"], ["b"]]}), False)
        self.assertEqual(str(c.exception), "too slow")

    def test_cells_keep_their_words_whatever_their_type(self):
        from test_ask_index_types_1366 import xlsx
        raw = xlsx({"S": [["name", None, "note"], ["x", None, "two\nlines"], ["y", 5, "z"]]})
        lines = ask_index._excel_groups(raw, False)[0][1]
        self.assertEqual(lines, ["name | note", "name: x | note: two lines", "name: y | 5 | note: z"])

    def test_a_first_row_with_a_number_gives_no_column_names_and_a_longer_row_is_read(self):
        from test_ask_index_types_1366 import xlsx
        lines = ask_index._excel_groups(xlsx({"S": [["a", 5], ["x", 6]]}), False)[0][1]
        self.assertEqual(lines, ["a | 5", "x | 6"])
        lines = ask_index._excel_groups(xlsx({"S": [["h1", "h2"], ["a", "b", "c"]]}), False)[0][1]
        self.assertEqual(lines, ["h1 | h2", "h1: a | h2: b | c"])
        lines = ask_index._excel_groups(xlsx({"S": [["h1", None, "h3"], ["a", "b", "c"]]}), False)[0][1]
        self.assertEqual(lines, ["h1 | h3", "h1: a | b | h3: c"])
        self.assertEqual(ask_index._excel_groups(xlsx({"S": [[None, None], ["a", "b"]]}), False)[0][1], ["a | b"])


class Prefixes(unittest.TestCase):
    def test_same_name_folders_get_the_fewest_trailing_parts_that_tell_them_apart(self):
        a, b = Path("/r/a/x/docs"), Path("/r/b/y/docs")
        self.assertEqual(ask_index._prefixes([a, b]), {a: "x/docs", b: "y/docs"})

    def test_the_root_slash_is_never_a_part_of_a_prefix(self):
        a, b = Path("/docs"), Path("/x/docs")
        self.assertEqual(ask_index._prefixes([a, b]), {a: "docs", b: "x/docs"})

    def test_a_repeated_folder_counts_once(self):
        a = Path("/r/a/docs")
        self.assertEqual(ask_index._prefixes([a, a]), {a: "docs"})


class NoFolders(Base):
    def test_no_folder_list_at_all_is_no_folder(self):
        self.assertEqual(ask_index._unusable(None, self.data, None), ([], []))
        self.assertIs(ask_index.refresh(self.data, "P1", None), True)
        self.assertFalse(ix.path_for(self.data, "P1").exists())
        self.assertEqual(ask_index.folder_status(self.data, "P1", None), {})
        self.assertEqual(ask_index._left_by_folder(self.data, "P1", None), {})
        self.assertIs(ask_index.current(self.data, "P1", None), False)

    def test_when_every_folder_is_refused_the_old_text_goes_and_the_counts_say_so(self):
        a, b = self.d / "a", self.d / "b"
        self.put("n.txt", "zqold words", folder=a)
        self.put("m.txt", "zqold more", folder=b)
        ix.refresh(self.data, "P1", [a, b])
        self.assertEqual(len(self.found("zqold")), 2)
        with mock.patch.object(ask_index.reach, "never_inside", return_value="refused"):
            self.assertIs(ix.mod().refresh(self.data, "P1", [a, b]), True)
            self.assertEqual(self.found("zqold"), [])
            self.assertEqual(ask_index.status(self.data, "P1")["safety"], 2)
            self.assertEqual(ask_index.status(self.data, "P1")["indexed"], 0)
            got = ask_index.folder_status(self.data, "P1", [a, b])
        self.assertEqual({k: v["state"] for k, v in got.items()}, {str(a): "done", str(b): "done"})
        self.assertEqual(got[str(a)]["line"], "No files to index")
        meta = dict(sqlite3.connect(ix.path_for(self.data, "P1")).execute("SELECT k, v FROM meta").fetchall())
        self.assertEqual(sorted(meta), ["complete", "counts", "folders", "listed", "screen"])
        self.assertEqual(meta["complete"], "1")
        self.assertEqual(meta["screen"], str(ask_index.SCREEN_VERSION))


class Ledger(Base):
    def test_the_index_is_marked_unfinished_while_it_runs_and_finished_after(self):
        self.put("a.txt", "zqled words")
        seen = []

        def progress(f, d, t):
            c = sqlite3.connect(ix.path_for(self.data, "P1"))
            seen.append((c.execute("SELECT v FROM meta WHERE k='complete'").fetchone(), ask_index.current(self.data, "P1", [self.box])))
            c.close()
        self.assertIs(ask_index.refresh(self.data, "P1", [self.box], progress=progress), True)
        self.assertEqual(seen[0], (("0",), False))
        self.assertTrue(ask_index.current(self.data, "P1", [self.box]))
        self.assertIs(ask_index.status(self.data, "P1")["stopped"], False)

    def test_a_run_that_is_stopped_returns_false_and_is_not_current(self):
        self.put("a.txt", "zqled words")
        stop = threading.Event()
        stop.set()
        self.assertIs(ask_index.refresh(self.data, "P1", [self.box], stop=stop), False)
        self.assertIs(ask_index.current(self.data, "P1", [self.box]), False)

    def test_a_listing_cut_short_in_any_folder_is_said_whatever_the_folders_after_it(self):
        a, b = self.d / "a", self.d / "b"
        self.put("n.txt", "zqcut one", folder=a)
        self.put("m.txt", "zqcut two", folder=b)
        real = ask_index.reach.readable_files
        for stopped, expected in (((True, False), True), ((False, True), True), ((False, False), False)):
            flags = iter(stopped)

            def listing(folders, *args, **kw):
                got = real(folders, *args, **kw)
                return ask_index.reach.Listing(got.files, got.skipped, next(flags))
            with mock.patch.object(ask_index.reach, "readable_files", listing):
                ask_index.refresh(self.data, "P1", [a, b])
            self.assertIs(ask_index.status(self.data, "P1")["stopped"], expected, stopped)

    def test_a_file_gone_before_it_is_opened_or_outside_every_root_counts_as_safety_not_an_error(self):
        a = self.put("a.txt", "zqgone words")
        self.put("b.txt", "zqlive words")
        with mock.patch.object(ask_index, "os", GoneAfterListing("a.txt")):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index.status(self.data, "P1")["safety"], 1)
        self.assertEqual(ask_index.status(self.data, "P1")["indexed"], 1)
        self.assertEqual(len(self.found("zqlive")), 1)
        self.assertEqual(self.found("zqgone"), [])
        self.assertEqual(ask_index.folder_status(self.data, "P1", [self.box])[str(self.box)]["line"], "100% indexed. 1 file could not be read")
        with mock.patch.object(ask_index.ask_passages, "_label", return_value=None):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index.status(self.data, "P1")["safety"], 2)
        self.assertEqual(ask_index.status(self.data, "P1")["indexed"], 0)

    def test_a_file_listed_twice_is_counted_in_its_own_state_each_time(self):
        self.put("a.txt", "zqtwice words")
        real = ask_index.reach.readable_files

        def listing(folders, *args, **kw):
            got = real(folders, *args, **kw)
            return ask_index.reach.Listing(got.files + got.files, got.skipped, got.stopped)
        with mock.patch.object(ask_index.reach, "readable_files", listing):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index.folder_status(self.data, "P1", [self.box])[str(self.box)]["line"], "100% indexed")
        self.assertEqual(len(self.found("zqtwice")), 1)

    def test_a_file_that_is_refused_on_read_is_safety_and_the_limit_per_type_is_the_one_of_its_reader(self):
        got = {}
        real = ask_index.reach.read_bytes

        def spy(path, usable, data_dir, limit, home=None):
            got[os.path.splitext(str(path))[1]] = limit
            raise ask_index.reach.Never("no")
        for name in ("a.txt", "a.pdf", "a.xlsx", "a.docx", "a.pptx", "a.html", "a.png"):
            self.put(name, "zqlim")
        with mock.patch.object(ask_index.reach, "read_bytes", spy), mock.patch.object(ask_index.ask_picture, "reader", return_value=lambda raw: ""):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(got, {".txt": ask_index.ask_passages.MAX_TEXT_BYTES, ".pdf": ask_index.INDEX_PDF_BYTES, ".xlsx": ask_index.MAX_EXCEL_BYTES,
                               ".docx": ask_index.docx_read.MAX_FILE_BYTES, ".pptx": ask_index.MAX_PPTX_BYTES, ".html": ask_index.ask_extract.MAX_HTML_BYTES,
                               ".png": ask_index.ask_picture.MAX_PICTURE_BYTES})
        self.assertEqual(ask_index.status(self.data, "P1")["safety"], 7)
        self.assertEqual(ask_index.status(self.data, "P1")["indexed"], 0)
        del real

    def test_a_secret_name_alone_leaves_a_file_out_and_the_text_of_all_parts_is_screened_together(self):
        self.put("plain.txt", "zqname words")
        with mock.patch.object(ask_index.secret_screen, "name_looks_like_secret", return_value=True):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index.status(self.data, "P1")["safety"], 1)
        self.assertEqual(self.found("zqname"), [])
        from test_ask_index_types_1366 import xlsx
        self.put("two.xlsx", xlsx({"A": [["one"]], "B": [["two"]]}), binary=True)
        seen = []
        with mock.patch.object(ask_index.secret_screen, "looks_like_secret", side_effect=lambda t: seen.append(t) or False):
            ix.refresh(self.data, "P2", [self.box])
        self.assertIn("one\ntwo", seen)

    def test_a_picture_with_no_reader_is_said_in_its_folder_line(self):
        self.put("p.png", "x")
        with mock.patch.object(ask_index.ask_picture, "reader", return_value=None):
            ix.refresh(self.data, "P1", [self.box])
            line = ask_index.folder_status(self.data, "P1", [self.box])[str(self.box)]["line"]
            self.assertEqual(line, "No files to index")
            for low, state, expected in (("a.txt", "picture", False), ("a.txt", "indexed", False), ("a.png", "picture", False), ("a.png", "indexed", True)):
                self.assertIs(bool(ask_index._picture_reader_changed(low, state)), expected, (low, state))
        with mock.patch.object(ask_index.ask_picture, "reader", return_value=lambda raw: ""):
            for low, state, expected in (("a.txt", "picture", False), ("a.txt", "indexed", False), ("a.png", "picture", True), ("a.png", "indexed", False)):
                self.assertIs(bool(ask_index._picture_reader_changed(low, state)), expected, (low, state))

    def test_one_part_of_a_sheet_is_named_by_the_sheet_and_several_by_sheet_and_part(self):
        from test_ask_index_types_1366 import xlsx
        self.put("one.xlsx", xlsx({"Short": [["zqshort words"]]}), binary=True)
        self.put("many.xlsx", xlsx({"Long": [[f"zqlong {'word ' * 40} {i}"] for i in range(400)]}), binary=True)
        ix.refresh(self.data, "P1", [self.box])
        short = [p[0] for p in self.found("zqshort")]
        self.assertEqual(len(short), 1)
        self.assertIn("one.xlsx, sheet Short, modified", short[0])
        many = [p.label for p in ask_index.search(self.data, "P1", "zqlong", 100)]
        self.assertTrue(many)
        self.assertTrue(all(", sheet Long, part " in m for m in many), many[:2])


class Reading(Base):
    def test_search_words_and_the_broken_index(self):
        self.put("a.txt", "zqone alone")
        self.put("b.txt", "zqtwo alone")
        ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index.search(self.data, "P1", None), [])
        self.assertEqual(ask_index.search(self.data, "P1", ""), [])
        self.assertEqual(len(ask_index.search(self.data, "P1", "zqone zqtwo")), 2)            # a word of the question is enough
        words = " ".join(f"zqw{i}" for i in range(45))
        self.put("c.txt", "zqw39 here", )
        self.put("d.txt", "zqw40 here")
        ix.refresh(self.data, "P1", [self.box])
        got = [p.label.split(",")[0] for p in ask_index.search(self.data, "P1", words, 100)]
        self.assertEqual(got, ["saved/c.txt"])                                                # only the first 40 words are asked
        ix.path_for(self.data, "P1").write_bytes(b"not a database at all" * 50)
        self.assertEqual(ask_index.search(self.data, "P1", "zqone"), [])
        self.assertEqual(ask_index.files_left_out(self.data, "P1"), {"files": [], "more": 0})
        self.assertEqual(ask_index.files_left_out(self.data, "NOPE"), {"files": [], "more": 0})
        self.assertIs(ask_index.current(self.data, "P1", [self.box]), False)
        self.assertIs(ask_index.stale(self.data, "P1", [self.box]), True)
        self.assertEqual(ask_index.status(self.data, "P1")["indexed"], 0)

    def test_the_note_under_an_answer_and_a_missing_count(self):
        self.assertEqual(ask_index.answer_note(None), "")
        self.assertEqual(ask_index.answer_note({"not_yet": 1}), "Still reading 1 file, so this answer may miss some.")

    def test_the_passages_of_a_question_are_cut_to_the_most_asked_for_and_the_rest_counted(self):
        for i in range(6):
            self.put(f"f{i}.txt", f"zqmany words {i}")
        self.put("secret.txt", FAKE_KEY)
        self.put("x.bin", "x")
        ix.refresh(self.data, "P1", [self.box])
        got = ask_index.folder_data(self.data, "P1", "zqmany", max_passages=2)
        self.assertEqual((len(got.passages), got.left_out), (2, 4))
        got = ask_index.folder_data(self.data, "P1", "zqmany", max_passages=1)
        self.assertEqual((len(got.passages), got.left_out), (1, 3))
        got = ask_index.folder_data(self.data, "P1", "zqmany", max_passages=6)
        self.assertEqual((len(got.passages), got.left_out), (6, 0))
        self.assertEqual((got.safety, got.pdf, got.other, got.stopped), (1, 0, 1, False))

    def test_the_left_out_list_of_a_folder_with_a_name_clash_or_a_vanished_folder(self):
        self.put("one.bin", "x")
        ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index._left_by_folder(self.data, "P1", [self.box]), {str(self.box): {"files": [["one.bin", ask_index.REASON_TYPE]], "more": 0}})
        (self.box / "one.bin").unlink()
        self.assertEqual(list(ask_index._left_by_folder(self.data, "P1", [self.box])), [str(self.box)], "a file gone since the read is still listed (the index is stale, not wrong)")
        self.assertEqual(ask_index._left_by_folder(self.data, "P1", [self.d / "missing"]), {})

    def test_status_of_a_folder_with_no_run_and_one_with_a_run(self):
        self.put("a.txt", "zqfs words")
        ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index.folder_status(self.data, "P1", [self.box])[str(self.box)], {"state": "done", "line": "100% indexed"})
        got = ask_index.folder_status(self.data, "P1", [self.box], live={str(self.box): (1, 4)})
        self.assertEqual(got[str(self.box)], {"state": "reading", "line": "Indexing… 25%"})
        got = ask_index.folder_status(self.data, "P1", [self.box], live={})
        self.assertEqual(got[str(self.box)]["state"], "done")

    def test_an_unfinished_index_is_not_current_and_the_checks_say_true_or_false_plainly(self):
        self.put("a.txt", "zqcur words")
        ix.refresh(self.data, "P1", [self.box])
        c = sqlite3.connect(ix.path_for(self.data, "P1"))
        c.execute("INSERT OR REPLACE INTO meta VALUES('complete','0')")
        c.commit()
        c.close()
        self.assertIs(ask_index.current(self.data, "P1", [self.box]), False)
        ix.refresh(self.data, "P1", [self.box])
        self.assertIs(ask_index.current(self.data, "P1", [self.box]), True)
        self.assertIs(ask_index.stale(self.data, "P1", [self.box]), False)
        self.put("b.txt", "zqnew words")
        self.assertIs(ask_index.stale(self.data, "P1", [self.box]), True)
        (self.box / "b.txt").unlink()
        (self.box / "a.txt").unlink()
        self.assertIs(ask_index.stale(self.data, "P1", [self.box]), True)
        self.assertIs(ask_index.stale(self.data, "P2", [self.box]), True)

    def test_the_screen_check_is_false_when_the_table_is_missing(self):
        con = sqlite3.connect(":memory:")
        self.assertIs(ask_index._screen_ok(con), False)
        con.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")
        self.assertIs(ask_index._screen_ok(con), False)
        con.execute("INSERT INTO meta VALUES('screen', ?)", (str(ask_index.SCREEN_VERSION),))
        self.assertIs(ask_index._screen_ok(con), True)


class Worker(Base):
    def make(self, **kw):
        ix2 = ask_index.Indexer(self.data, None, **kw)
        self.addCleanup(ix2.shutdown)
        return ix2

    def hold(self):
        gate, begun, calls = threading.Event(), threading.Event(), []
        self.addCleanup(gate.set)

        def refresh(data_dir, code, folders, home=None, stop=None, progress=None):
            calls.append(code)
            begun.set()
            gate.wait(10)
        return refresh, gate, begun, calls

    def test_the_switch_and_start_say_true_or_false_plainly(self):
        self.assertIs(self.make()._on(), True)
        self.assertIs(self.make(allowed=lambda: True)._on(), True)
        self.assertIs(self.make(allowed=lambda: False)._on(), False)
        self.assertIs(self.make(allowed=lambda: 1)._on(), False)

        def boom():
            raise OSError("x")
        self.assertIs(self.make(allowed=boom)._on(), False)
        off = self.make(allowed=lambda: False)
        self.assertIs(off.start("P1", [self.box]), False)
        self.assertIs(off.current("P1", [self.box]), False)
        self.assertEqual(off.status_for("P1", [self.box]), {})
        on = self.make()
        self.assertIs(on.start("P1", [self.box]), True)
        on.shutdown()
        self.assertIs(on.start("P2", [self.box]), False)

    def test_a_dead_worker_is_started_again_and_a_live_one_is_not_doubled(self):
        refresh, gate, begun, calls = self.hold()
        w = self.make(refresh_fn=refresh)
        dead = threading.Thread(target=lambda: None)
        dead.start()
        dead.join()
        w.thread = dead
        w.start("P1", [self.box])
        self.assertTrue(begun.wait(10))
        first = w.thread
        self.assertIsNot(first, dead)
        w.start("P2", [self.box])
        self.assertIs(w.thread, first)
        gate.set()
        self.assertTrue(w.wait_idle(10))
        self.assertEqual(calls, ["P1", "P2"])

    def test_shutdown_ends_an_idle_worker_at_once(self):
        w = self.make(refresh_fn=lambda *a, **k: None)
        w.start("P1", [self.box])
        self.assertTrue(w.wait_idle(10))
        t = w.thread
        began = time.monotonic()
        w.shutdown(timeout=3)
        self.assertFalse(t.is_alive())
        self.assertLess(time.monotonic() - began, 2.5)

    def test_waiting_for_idle_returns_at_once_when_nothing_runs_and_after_the_time_when_something_does(self):
        w = self.make()
        began = time.monotonic()
        self.assertIs(w.wait_idle(5), True)
        self.assertLess(time.monotonic() - began, 1)
        refresh, gate, begun, calls = self.hold()
        w2 = self.make(refresh_fn=refresh)
        w2.start("P1", [self.box])
        self.assertTrue(begun.wait(10))
        self.assertIs(w2.wait_idle(0.2), False)

    def test_a_poll_never_starts_a_second_run_for_a_project_that_is_queued_or_running(self):
        refresh, gate, begun, calls = self.hold()
        w = self.make(refresh_fn=refresh)
        w.start("P1", [self.box])
        self.assertTrue(begun.wait(10))
        w.start("P2", [self.box])                                   # queued behind P1
        for code in ("P1", "P2"):
            w.checked.clear()
            w.status_for(code, [self.box])
            self.assertEqual(w.checked, {}, code)
            self.assertIs(w.current(code, [self.box]), False)
            self.assertIs(w.resume(code, [self.box]), False)
        self.assertEqual(w.checked, {})
        self.assertEqual(w.not_yet("P9"), 0)
        w.live["P1"] = {"f": (2, 5), "g": (5, 3)}
        self.assertEqual(w.not_yet("P1"), 3)
        gate.set()
        self.assertTrue(w.wait_idle(10))
        self.assertEqual(calls, ["P1", "P2"])

    def test_a_queued_project_with_a_finished_index_is_still_not_current_and_a_running_one_too(self):
        refresh, gate, begun, calls = self.hold()
        ix.build(self.data, "P1", [self.box])
        ix.build(self.data, "P2", [self.box])
        w = self.make(refresh_fn=refresh)
        w.start("P1", [self.box])
        self.assertTrue(begun.wait(10))
        w.start("P2", [self.box])
        self.assertIs(w.current("P1", [self.box]), False)              # running
        self.assertIs(w.current("P2", [self.box]), False)              # queued
        self.assertIs(w.resume("P1", [self.box]), False)
        self.assertIs(w.resume("P2", [self.box]), False)
        gate.set()
        self.assertTrue(w.wait_idle(10))
        self.assertIs(w.current("P1", [self.box]), True)

    def test_a_poll_with_no_folder_starts_nothing_and_the_second_poll_inside_the_wait_starts_nothing(self):
        calls = []
        w = self.make(refresh_fn=lambda d, c, f, *a, **k: calls.append(c))
        w.status_for("P1", [])
        self.assertTrue(w.wait_idle(10))
        self.assertEqual(calls, [])
        w.checked.clear()
        w.status_for("P1", [self.box])
        self.assertTrue(w.wait_idle(10))
        w.status_for("P1", [self.box])
        self.assertTrue(w.wait_idle(10))
        self.assertEqual(calls, ["P1"])


class More(Base):
    def test_a_prefix_list_whose_parts_run_out_stops(self):
        a, b = Path("/a/docs"), Path("a/docs")
        self.assertEqual(ask_index._prefixes([a, b]), {a: "a/docs", b: "a/docs"})

    def test_online_only_files_are_counted_in_their_own_folder(self):
        self.put("a.txt", "zqon words")
        real = ask_index.reach.readable_files

        def listing(folders, data_dir, reasons=None, home=None):
            got = real(folders, data_dir, reasons, home)
            reasons[ask_index.reach.ONLINE] = 2
            return ask_index.reach.Listing(got.files, got.skipped + 3, got.stopped)
        with mock.patch.object(ask_index.reach, "readable_files", listing):
            ix.refresh(self.data, "P1", [self.box])
        c = ask_index.status(self.data, "P1")
        self.assertEqual((c["online_only"], c["safety"], c["indexed"]), (2, 1, 1))
        self.assertEqual(ask_index.folder_status(self.data, "P1", [self.box])[str(self.box)]["line"],
                         "100% indexed. 3 files could not be read")

    def test_a_secret_file_listed_twice_is_safety_both_times(self):
        self.put("k.txt", FAKE_KEY)
        real = ask_index.reach.readable_files

        def listing(folders, *args, **kw):
            got = real(folders, *args, **kw)
            return ask_index.reach.Listing(got.files + got.files, got.skipped, got.stopped)
        with mock.patch.object(ask_index.reach, "readable_files", listing):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index.folder_status(self.data, "P1", [self.box])[str(self.box)]["line"], "No files to index")

    def test_a_pdf_that_cannot_be_read_is_too_long_only_for_its_size_or_pages(self):
        self.put("a.pdf", "x")
        for reason, state in (("too_big", "too_long"), ("too_many_pages", "too_long"), ("encrypted", "type"), ("", "type")):
            with mock.patch.object(ask_index.pdf_reader, "read", return_value=mock.Mock(status="bad", reason=reason)):
                ix.refresh(self.data, "P1", [self.box])
                (self.box / "a.pdf").write_text("x" * (3 + len(reason)), encoding="utf-8")
            c = ask_index.status(self.data, "P1")
            self.assertEqual((c["too_long"], c["type"]), (1, 0) if state == "too_long" else (0, 1), reason)

    def test_the_lines_of_a_file_are_screened_joined_by_line_breaks(self):
        self.put("a.txt", "first\nsecond")
        seen = []
        with mock.patch.object(ask_index.secret_screen, "looks_like_secret", side_effect=lambda t: seen.append(t) or False):
            ix.refresh(self.data, "P1", [self.box])
        self.assertIn("first\nsecond", seen)

    def test_the_parts_of_a_long_file_are_numbered_from_one_and_a_short_one_has_no_part(self):
        self.put("short.txt", "zqshortone words")
        self.put("two.txt", "\n".join(f"zqtwoparts line {i} " + "word " * 10 for i in range(20)))
        ix.refresh(self.data, "P1", [self.box])
        self.assertEqual([p.label.split(", modified")[0] for p in ask_index.search(self.data, "P1", "zqshortone")], ["saved/short.txt"])
        labels = sorted(p.label.split(", modified")[0] for p in ask_index.search(self.data, "P1", "zqtwoparts", 100))
        self.assertEqual(labels, ["saved/two.txt (part 1)", "saved/two.txt (part 2)"])

    def test_the_parts_of_one_file_stop_at_the_limit(self):
        self.put("big.txt", "\n".join(f"zqcap line {i} " + "word " * 10 for i in range(60)))
        with mock.patch.object(ask_index, "MAX_PARTS_PER_FILE", 3):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(len(ask_index.search(self.data, "P1", "zqcap", 100)), 3)

    def test_a_query_that_fails_on_a_readable_index_gives_nothing_and_counts_as_changed(self):
        self.put("a.txt", "zqfail words")
        ix.refresh(self.data, "P1", [self.box])

        class Failing:
            """The index as a reader gets it, where a query on one table fails."""
            def __init__(self, db, table):
                self.db, self.table = db, table

            def execute(self, sql, *a):
                if self.table in sql:
                    raise sqlite3.OperationalError("broken")
                return self.db.execute(sql, *a)

            def close(self):
                self.db.close()
        for table, check in (("FROM p ", lambda: self.assertEqual(ask_index.search(self.data, "P1", "zqfail"), [])),
                             ("FROM left", lambda: self.assertEqual(ask_index.files_left_out(self.data, "P1"), {"files": [], "more": 0})),
                             ("FROM files", lambda: self.assertIs(ask_index.stale(self.data, "P1", [self.box]), True)),
                             ("FROM meta WHERE k='counts'", lambda: self.assertEqual(ask_index.status(self.data, "P1")["indexed"], 0))):
            real = ask_index._open_read
            with mock.patch.object(ask_index, "_open_read", lambda d, c: Failing(real(d, c), table)):
                check()

    def test_the_left_out_list_with_a_limit_of_nothing_still_counts_the_rest(self):
        self.put("a.bin", "x")
        self.put("b.bin", "x")
        ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ask_index.files_left_out(self.data, "P1", 0), {"files": [], "more": 2})
        self.assertEqual(ask_index.files_left_out(self.data, "P1", -4), {"files": [], "more": 2})
        self.assertEqual(ask_index.files_left_out(self.data, "P1", 1)["more"], 1)

    def test_a_saved_folder_that_is_gone_keeps_its_name_from_its_path_even_with_a_trailing_slash(self):
        ix.refresh(self.data, "P1", [self.box])
        con = sqlite3.connect(ix.path_for(self.data, "P1"))
        con.execute("INSERT INTO left VALUES('gone/x.bin', ?)", (ask_index.REASON_TYPE,))
        con.commit()
        con.close()
        gone = str(self.d / "gone") + "/"
        self.assertEqual(ask_index._left_by_folder(self.data, "P1", [gone]), {gone: {"files": [["x.bin", ask_index.REASON_TYPE]], "more": 0}})

    def test_the_status_of_folders_when_the_run_is_in_only_one_of_them(self):
        other = self.d / "other"
        self.put("a.txt", "zqone words")
        self.put("b.txt", "zqtwo words", folder=other)
        ix.refresh(self.data, "P1", [self.box, other])
        got = ask_index.folder_status(self.data, "P1", [self.box, other], live={str(other): (0, 3)})
        self.assertEqual((got[str(self.box)]["state"], got[str(other)]["state"]), ("done", "reading"))

    def test_the_checks_on_a_damaged_or_changing_index(self):
        self.put("a.txt", "zqchk words")
        ix.refresh(self.data, "P1", [self.box])
        self.assertIs(ask_index.current(self.data, "P1", None), False)
        path = ix.path_for(self.data, "P1")

        def meta(k, v):
            con = sqlite3.connect(path)
            con.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", (k, v))
            con.commit()
            con.close()
        meta("listed", "{not json")
        self.assertIs(ask_index.current(self.data, "P1", [self.box]), False)
        ix.refresh(self.data, "P1", [self.box])
        with mock.patch.object(ask_index, "os", GoneAfterListing("a.txt")):
            self.assertIs(ask_index.stale(self.data, "P1", [self.box]), True)
        con = sqlite3.connect(path)
        con.execute("DROP TABLE files")
        con.commit()
        con.close()
        self.assertIs(ask_index.stale(self.data, "P1", [self.box]), True)

    def test_no_index_gives_nothing_to_read_and_a_count_of_nothing(self):
        got = ask_index.folder_data(self.data, "NONE", "zqany")
        self.assertEqual((got.passages, got.left_out, got.safety, got.pdf, got.other, got.stopped), ((), 0, 0, 0, 0, False))
        with mock.patch.object(ask_index, "status", return_value={"picture": 3, "safety": 4, "stopped": True}):
            got = ask_index.folder_data(self.data, "NONE", "zqany")
        self.assertEqual((got.safety, got.pdf, got.other, got.stopped), (4, 0, 3, True))
        with mock.patch.object(ask_index, "status", return_value={"type": 2}):
            got = ask_index.folder_data(self.data, "NONE", "zqany")
        self.assertEqual((got.safety, got.pdf, got.other, got.stopped), (0, 0, 2, False))
        with mock.patch.object(ask_index, "status", return_value={}):
            got = ask_index.folder_data(self.data, "NONE", "zqany")
        self.assertEqual((got.safety, got.pdf, got.other, got.stopped), (0, 0, 0, False))


class WorkerMore(Base):
    def test_the_worker_thread_is_named_and_does_not_hold_clark_open(self):
        w = ask_index.Indexer(self.data, None, refresh_fn=lambda *a, **k: None)
        self.addCleanup(w.shutdown)
        w.start("P1", [self.box])
        self.assertEqual(w.thread.name, "ask-index")
        self.assertTrue(w.thread.daemon)

    def test_resume_is_once_a_wait_and_current_says_false_for_a_missing_stopped_or_changed_index(self):
        calls = []
        w = ask_index.Indexer(self.data, None, refresh_fn=lambda d, c, f, *a, **k: calls.append(c))
        self.addCleanup(w.shutdown)
        self.assertIs(w.resume("P1", [self.box]), True)
        self.assertTrue(w.wait_idle(10))
        self.assertIs(w.resume("P1", [self.box]), False)                      # inside the wait
        self.assertIs(w.current("P1", [self.box]), False)                    # no index file: a run is started
        self.assertTrue(w.wait_idle(10))
        ix.build(self.data, "P1", [self.box])
        con = sqlite3.connect(ix.path_for(self.data, "P1"))
        con.execute("INSERT OR REPLACE INTO meta VALUES('complete','0')")
        con.commit()
        con.close()
        w.resumed.clear()
        self.assertIs(w.current("P1", [self.box]), False)                    # not finished: carried on
        self.assertTrue(w.wait_idle(10))
        ix.build(self.data, "P1", [self.box])
        self.put("late.txt", "zqlate words")
        self.assertIs(w.current("P1", [self.box]), False)                    # a file changed
        self.assertTrue(w.wait_idle(10))
        self.assertEqual(calls, ["P1", "P1", "P1", "P1"])
        ix.build(self.data, "P1", [self.box])
        self.assertIs(w.current("P1", [self.box]), True)


class LauncherWiring(unittest.TestCase):
    """The one line of the launcher that builds the Indexer: it is told whether asking is On, from the real switch."""

    def built(self, switch):
        tmp = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        made = []
        real = ask_index.Indexer

        def spy(*a, **kw):
            made.append(real(*a, **kw))
            return made[-1]

        def serve(**kw):
            print("Open http://127.0.0.1:%d/ to use the report editor." % kw["port"], file=kw["out"], flush=True)
            return 0

        with mock.patch.object(launcher.ask_index, "Indexer", spy), \
                mock.patch.object(launcher.platform, "container_on_host_network", lambda: False), \
                mock.patch.object(st.Store, "ask_enabled", lambda self: switch):
            code = launcher.main(["--data", str(tmp / "data"), "--port", "8123"], out=io.StringIO(), err=io.StringIO(), serve=serve,
                                 home=tmp, onedrive_roots=[], environ={}, is_free=lambda port: True)
            self.assertEqual(code, 0)
            (ix,) = made
            self.assertIsNotNone(ix.allowed, "the launcher gives the indexer the asking switch")
            return ix.allowed(), ix._on()

    def test_with_asking_off_the_indexer_the_launcher_builds_is_not_allowed_to_build(self):
        allowed, on = self.built(False)
        self.assertIsNot(allowed, True)
        self.assertFalse(on)

    def test_with_asking_on_the_indexer_the_launcher_builds_is_allowed(self):
        allowed, on = self.built(True)
        self.assertIs(allowed, True)
        self.assertTrue(on)


if __name__ == "__main__":
    unittest.main()
