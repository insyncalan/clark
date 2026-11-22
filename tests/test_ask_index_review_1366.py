"""Row 1366 review fixes: modes of a folder made earlier, the worker's connection on a failed read, and the reasons given for files left out.
Made-up files only. Run: python3 dev/run_tests.py test_ask_index_review_1366"""
import os
import stat
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, FAKE_KEY, ix


class Modes(Base):
    def test_an_index_folder_and_file_made_looser_are_put_back_to_0700_and_0600(self):
        d = self.data / "ask-index"
        d.mkdir()
        os.chmod(d, 0o755)
        f = ix.path_for(self.data, "P1")
        f.write_bytes(b"")
        os.chmod(f, 0o644)
        self.put("a.txt", "zqone")
        ix.build(self.data, "P1", [self.box])
        self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)


class Closes(Base):
    def test_a_read_that_fails_half_way_does_not_leave_the_connection_open(self):
        import sqlite3
        from clark import ask_index
        self.put("a.txt", "zqone")
        opened = []
        real = ask_index._open

        def spy(*a, **k):
            db = real(*a, **k)
            opened.append(db)
            return db
        with mock.patch.object(ask_index, "_open", spy), mock.patch.object(ask_index, "_read_one", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                ask_index.refresh(self.data, "P1", [self.box])
        self.assertTrue(opened)
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute("SELECT 1")

    def test_a_stopped_run_closes_too(self):
        import sqlite3
        import threading
        from clark import ask_index
        self.put("a.txt", "zqone")
        opened = []
        real = ask_index._open
        ask_index_open = lambda *a, **k: opened.append(real(*a, **k)) or opened[-1]
        stop = threading.Event()
        stop.set()
        with mock.patch.object(ask_index, "_open", ask_index_open):
            self.assertFalse(ask_index.refresh(self.data, "P1", [self.box], stop=stop))
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute("SELECT 1")


class Reasons(Base):
    def test_a_damaged_workbook_is_not_said_to_look_like_a_password(self):
        self.put("bad.xlsx", b"not a workbook", binary=True)
        self.put("keys.txt", "zqnote\n" + FAKE_KEY)
        ix.build(self.data, "P1", [self.box])
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["type"], c["safety"]), (1, 1))
        names = dict(ix.mod().files_left_out(self.data, "P1", 200)["files"])
        self.assertEqual(names["saved/bad.xlsx"], ix.mod().REASON_TYPE)
        self.assertEqual(names["saved/keys.txt"], ix.mod().REASON_SAFETY)

    def test_a_pdf_over_the_page_limit_is_counted_too_long_and_listed(self):
        from clark import pdf_reader
        self.put("big.pdf", b"%PDF-1.4 x", binary=True)
        self.put("scan.pdf", b"%PDF-1.4 y", binary=True)
        results = {b"%PDF-1.4 x": pdf_reader.Result("not_read", "too_many_pages"), b"%PDF-1.4 y": pdf_reader.Result("not_read", "scanned")}
        with mock.patch.object(pdf_reader, "read", lambda raw, truncated=False, **k: results[bytes(raw)]):
            ix.build(self.data, "P1", [self.box])
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["too_long"], c["type"], c["indexed"], c["safety"]), (1, 1, 0, 0))
        self.assertEqual(sum(c.get(n, 0) for n in ix.mod().NAMES), 2)
        self.assertEqual(ix.mod().line_for(c), "Indexed 0 of 2 files. 1 is of a type clark can't read yet. 1 PDF is too long.")
        self.assertEqual(dict(ix.mod().files_left_out(self.data, "P1", 200)["files"])["saved/big.pdf"], ix.mod().REASON_TOO_LONG)
        self.assertEqual(ix.mod().REASON_TOO_LONG, "is a PDF that is too long")


class Readers(Base):
    def test_a_reader_gets_an_empty_answer_not_an_error_when_the_index_cannot_be_opened(self):
        import sqlite3
        from clark import ask_index
        self.put("a.txt", "zqone")
        ix.build(self.data, "P1", [self.box])
        with mock.patch.object(ask_index, "_open", side_effect=sqlite3.OperationalError("database is locked")):
            self.assertEqual(ask_index.search(self.data, "P1", "zqone"), [])
            self.assertEqual(ask_index.status(self.data, "P1")["indexed"], 0)
            self.assertEqual(ask_index.files_left_out(self.data, "P1"), {"files": [], "more": 0})
            self.assertEqual(ask_index.folder_status(self.data, "P1", [self.box]), {})
            self.assertFalse(ask_index.current(self.data, "P1", [self.box]))


class StoppedRun(Base):
    def test_a_stopped_run_keeps_the_whole_list_of_files_left_out(self):
        import threading
        self.put("a.txt", "zqone")
        self.put("p.bin", b"x", binary=True)
        self.put("q.bin", b"x", binary=True)
        ix.build(self.data, "P1", [self.box])
        before = ix.mod().files_left_out(self.data, "P1", 200)
        self.assertEqual(len(before["files"]), 2)
        stop = threading.Event()
        stop.set()
        self.assertFalse(ix.mod().refresh(self.data, "P1", [self.box], stop=stop))
        self.assertEqual(ix.mod().files_left_out(self.data, "P1", 200), before)
