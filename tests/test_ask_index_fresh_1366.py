"""Row 1366, changes after the first read: a question never gets stale text (the index is checked against the folders and read again
in the background, the question is answered from the files meanwhile), and a hostile Excel file is refused before it is parsed.
Run: python3 dev/run_tests.py test_ask_index_fresh_1366. Every file is made in the test from made-up text."""
import io
import itertools
import os
import time
import unittest
import zipfile
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, FAKE_KEY, ix
from test_ask_index_types_1366 import xlsx
from clark import ask_index


class Fresh(Base):
    def setUp(self):
        super().setUp()
        self.ix = ask_index.Indexer(self.data, None)
        self.addCleanup(self.ix.shutdown)

    def settle(self, folders):
        self.assertTrue(self.ix.wait_idle(10))
        return self.ix.current("P1", [str(f) for f in folders])

    def first_build(self):
        folders = [str(self.box)]
        ix.build(self.data, "P1", folders)
        self.assertTrue(self.ix.current("P1", folders))
        return folders

    def test_an_unchanged_folder_stays_current_and_starts_no_run(self):
        self.put("a.txt", "zqstable")
        folders = self.first_build()
        self.assertFalse(ask_index.stale(self.data, "P1", folders))
        self.assertTrue(self.ix.current("P1", folders))
        self.assertEqual(self.ix.busy, 0)

    def test_an_edited_file_is_not_served_stale_and_is_read_again(self):
        p = self.put("a.txt", "zqoldtext here", mtime=1000)
        folders = self.first_build()
        self.put("a.txt", "zqnewtext here and more")
        self.assertTrue(ask_index.stale(self.data, "P1", folders))
        self.assertFalse(self.ix.current("P1", folders), "this question must read the files, not the old index")
        self.assertTrue(self.settle(folders))
        self.assertTrue(ix.search(self.data, "P1", "zqnewtext"))
        self.assertFalse(ix.search(self.data, "P1", "zqoldtext"))

    def test_a_same_size_edit_with_a_new_time_is_seen(self):
        p = self.put("a.txt", "zqoldtext", mtime=1000)
        folders = self.first_build()
        self.put("a.txt", "zqnewtext", mtime=2000)
        self.assertFalse(self.ix.current("P1", folders))
        self.assertTrue(self.settle(folders))
        self.assertFalse(ix.search(self.data, "P1", "zqoldtext"))
        self.assertTrue(ix.search(self.data, "P1", "zqnewtext"))

    def test_a_deleted_file_is_never_served_and_leaves_the_list(self):
        self.put("a.txt", "zqkeep")
        gone = self.put("gone.txt", "zqgonetext")
        self.put("pic.bin", b"x", binary=True)
        folders = self.first_build()
        gone.unlink()
        self.assertFalse(self.ix.current("P1", folders))
        self.assertTrue(self.settle(folders))
        self.assertFalse(ix.search(self.data, "P1", "zqgonetext"))
        self.assertTrue(ix.search(self.data, "P1", "zqkeep"))
        self.assertEqual(ix.status(self.data, "P1", folders)["indexed"], 1)
        self.assertNotIn(b"zqgonetext", ix.path_for(self.data, "P1").read_bytes())

    def test_a_file_edited_to_hold_a_secret_gives_no_passage_and_counts_safety(self):
        self.put("a.txt", "zqplain words", mtime=1000)
        folders = self.first_build()
        self.put("a.txt", "zqplain words\n" + FAKE_KEY, mtime=2000)
        self.assertFalse(self.ix.current("P1", folders))
        self.assertTrue(self.settle(folders))
        self.assertEqual(ix.search(self.data, "P1", "zqplain"), [])
        s = ix.status(self.data, "P1", folders)
        self.assertEqual((s["indexed"], s["safety"]), (0, 1))
        self.assertNotIn(b"hunter2", ix.path_for(self.data, "P1").read_bytes())

    def test_a_new_file_is_found_after_the_read(self):
        self.put("a.txt", "zqfirst")
        folders = self.first_build()
        self.put("b.txt", "zqsecondfile")
        self.assertFalse(self.ix.current("P1", folders))
        self.assertTrue(self.settle(folders))
        self.assertTrue(ix.search(self.data, "P1", "zqsecondfile"))

    def test_a_file_no_longer_readable_is_dropped(self):
        p = self.put("a.txt", "zqlinked")
        folders = self.first_build()
        os.link(p, p.with_name("b.txt"))                     # two names: reach refuses both
        self.assertTrue(ask_index.stale(self.data, "P1", folders))

    def test_while_stale_the_question_reads_the_files_through_the_service_choice(self):
        """ask_service takes the index only when Indexer.current is True: it is False for as long as the index is old."""
        self.put("a.txt", "zqwas")
        folders = self.first_build()
        gate = __import__("threading").Event()
        real = ask_index.refresh

        def held(*a, **k):
            gate.wait(5)
            return real(*a, **k)
        slow = ask_index.Indexer(self.data, None, refresh_fn=held)
        self.addCleanup(slow.shutdown)
        self.addCleanup(gate.set)
        self.put("a.txt", "zqnow longer text")
        self.assertFalse(slow.current("P1", folders))
        self.assertFalse(slow.current("P1", folders), "still False while the run is held")
        gate.set()
        self.assertTrue(slow.wait_idle(10))
        self.assertTrue(slow.current("P1", folders))

    def test_the_settings_poll_starts_a_run_when_a_file_changed(self):
        self.put("a.txt", "zqpollold", mtime=1000)
        folders = self.first_build()
        self.put("a.txt", "zqpollnew text", mtime=2000)
        self.ix.status_for("P1", folders)
        self.assertTrue(self.settle(folders))
        self.assertTrue(ix.search(self.data, "P1", "zqpollnew"))
        self.assertFalse(ix.search(self.data, "P1", "zqpollold"))

    def test_the_poll_looks_at_the_files_at_most_every_few_seconds(self):
        self.put("a.txt", "zqone")
        folders = self.first_build()
        with mock.patch.object(ask_index, "stale", wraps=ask_index.stale) as st:
            for _ in range(5):
                self.ix.status_for("P1", folders)
        self.assertEqual(st.call_count, 1)

    def test_a_same_size_same_time_edit_cannot_be_seen(self):
        """The stated limit: no content hash (it would read every file on every question)."""
        self.put("a.txt", "zqaaaa", mtime=1000)
        folders = self.first_build()
        self.put("a.txt", "zqbbbb", mtime=1000)
        self.assertFalse(ask_index.stale(self.data, "P1", folders))


def sst_xlsx(shared_bytes):
    """A real workbook whose shared strings part unpacks to about `shared_bytes` of one repeated short string (it compresses to a few KB)."""
    src = zipfile.ZipFile(io.BytesIO(xlsx({"S": [["zqxlhost"]]})))
    unit = b"<si><t>ab</t></si>"
    sst = b'<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + unit * (shared_bytes // len(unit)) + b"</sst>"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in src.namelist():
            z.writestr(n, src.read(n))
        z.writestr("xl/sharedStrings.xml", sst)
    return out.getvalue()


class ExcelBomb(Base):
    def counts(self):
        return ix.status(self.data, "P1", [self.box])

    def test_a_huge_shared_strings_part_is_refused_before_parsing_and_counted_too_long(self):
        raw = sst_xlsx(60 * 1024 * 1024)
        self.assertLess(len(raw), 4 * 1024 * 1024)
        self.put("bomb.xlsx", raw, binary=True)
        began = time.monotonic()
        with mock.patch("openpyxl.load_workbook", side_effect=AssertionError("parsed")):
            self.build()
        self.assertLess(time.monotonic() - began, 10)
        c = self.counts()
        self.assertEqual((c["too_long"], c["indexed"], c["type"]), (1, 0, 0))
        left = ask_index.files_left_out(self.data, "P1")["files"]
        self.assertEqual(left, [("saved/bomb.xlsx", ask_index.REASON_TOO_LONG)])

    def test_a_shared_strings_part_just_over_its_own_cap_is_refused(self):
        self.put("b.xlsx", sst_xlsx(ask_index.MAX_EXCEL_SHARED + 4096), binary=True)
        self.build()
        self.assertEqual(self.counts()["too_long"], 1)

    def test_too_many_parts_is_too_long(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for i in range(ask_index.MAX_EXCEL_MEMBERS + 1):
                z.writestr(f"p{i}.xml", b"x")
        self.put("many.xlsx", out.getvalue(), binary=True)
        self.build()
        self.assertEqual(self.counts()["too_long"], 1)

    def test_parts_that_add_up_over_the_total_are_too_long(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for i in range(3):
                z.writestr(f"p{i}.xml", b"a" * (20 * 1024 * 1024))
        self.put("sum.xlsx", out.getvalue(), binary=True)
        self.build()
        self.assertEqual(self.counts()["too_long"], 1)

    def test_a_forged_header_cannot_get_past(self):
        """The size in the headers is made smaller than the data: the unpacked bytes are counted too, so it is never indexed and never slow."""
        raw = bytearray(sst_xlsx(5000))
        z = zipfile.ZipFile(io.BytesIO(bytes(raw)))
        info = z.getinfo("xl/sharedStrings.xml")
        import struct
        struct.pack_into("<I", raw, info.header_offset + 22, 10)
        pos = 0
        while True:
            pos = bytes(raw).find(b"PK\x01\x02", pos)
            if pos < 0:
                break
            if bytes(raw[pos + 46:pos + 46 + len(info.filename)]) == info.filename.encode():
                struct.pack_into("<I", raw, pos + 24, 10)
            pos += 4
        self.put("forged.xlsx", bytes(raw), binary=True)
        began = time.monotonic()
        self.build()
        self.assertLess(time.monotonic() - began, 10)
        c = self.counts()
        self.assertEqual(c["indexed"], 0)
        self.assertEqual(c["too_long"] + c["type"], 1)

    def test_the_unpacked_bytes_are_counted_even_when_the_headers_say_less(self):
        """A stream that holds more than its header declares (as a forged header would with a reader that trusts it) is stopped."""
        class Lying(io.RawIOBase):
            def __init__(self):
                self.left = 40 * 1024 * 1024

            def readable(self):
                return True

            def read(self, n=-1):
                n = min(n if n and n > 0 else 1 << 20, self.left)
                self.left -= n
                return b"a" * n

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        raw = sst_xlsx(5000)
        with mock.patch("zipfile.ZipFile.open", side_effect=lambda *a, **k: Lying()):
            with self.assertRaises(ask_index.TooLong):
                ask_index._check_excel_zip(raw)

    def test_a_workbook_that_runs_past_the_time_limit_is_too_long(self):
        self.put("slow.xlsx", xlsx({"S": [[f"zqrow{i}"] for i in range(50)]}), binary=True)
        ticks = itertools.count(0, ask_index.MAX_EXCEL_SECONDS)       # every look at the clock is a whole limit later
        with mock.patch.object(ask_index, "CLOCK", lambda: next(ticks)):
            self.build()
        c = self.counts()
        self.assertEqual((c["too_long"], c["indexed"]), (1, 0))
        self.assertEqual(ix.search(self.data, "P1", "zqrow3"), [])

    def test_an_ordinary_workbook_is_still_read(self):
        self.put("ok.xlsx", xlsx({"S": [["zqxlfine", 3]]}), binary=True)
        self.build()
        self.assertTrue(self.found("zqxlfine"))
        self.assertEqual(self.counts()["too_long"], 0)

    def test_a_workbook_over_the_file_size_cap_is_too_long(self):
        self.put("big.xlsx", xlsx({"S": [["zqxlbig"]]}), binary=True)
        with mock.patch.object(ask_index, "MAX_EXCEL_BYTES", 100):
            self.build()
        self.assertEqual(self.counts()["too_long"], 1)


if __name__ == "__main__":
    unittest.main()
