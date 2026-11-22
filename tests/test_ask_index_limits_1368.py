"""Row 1368: background index runs skip a PDF over 2,000 pages, 100 MB or 120 s and list it as 'is a PDF that is too long'; the question path keeps its limits.
Real pdf_reader, its child process and the index; a stand-in pypdf; made-up files only."""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from test_ask_pdf_passages import FAKE_PYPDF, pdf
from clark import ask_passages, pdf_reader, platform


class Limits(Base):
    def setUp(self):
        super().setUp()
        v = self.d / "vendor"
        (v / "pypdf").mkdir(parents=True)
        (v / "pypdf" / "__init__.py").write_text(FAKE_PYPDF, encoding="utf-8")
        p = mock.patch.object(pdf_reader, "VENDOR", v)
        p.start()
        self.addCleanup(p.stop)

    def left(self):
        return dict(ix.mod().files_left_out(self.data, "P1", 200)["files"])

    def test_the_limits_are_the_ruled_numbers_and_the_question_path_keeps_its_own(self):
        m = ix.mod()
        self.assertEqual((m.INDEX_PDF_PAGES, m.INDEX_PDF_BYTES, m.INDEX_PDF_SECONDS), (2000, 100 * 1024 * 1024, 120))
        self.assertEqual((pdf_reader.MAX_PAGES, pdf_reader.MAX_BYTES, pdf_reader.SECONDS), (200, 20 * 1024 * 1024, 20.0))

    def test_the_words_are_exactly_too_long_to_read(self):
        self.assertEqual(ix.mod().REASON_TOO_LONG_PDF, "is a PDF that is too long")
        self.assertEqual(ix.mod().REASON_TOO_LONG, "is too long")      # any other file (approved words 22-11)

    def test_a_pdf_over_the_question_page_limit_is_indexed_but_not_read_for_a_question(self):
        raw = pdf([f"zqpage{i}" for i in range(1, 202)])
        self.assertEqual(pdf_reader.read(raw).reason, "too_many_pages")
        self.put("long.pdf", raw, binary=True)
        self.build()
        self.assertEqual(ix.status(self.data, "P1", None)["indexed"], 1)
        self.assertTrue(self.found("zqpage201"))

    def test_the_question_path_passes_no_limits_to_the_pdf_reader(self):
        self.put("long.pdf", pdf([f"zqpage{i}" for i in range(1, 202)]), binary=True)
        real = pdf_reader.read
        with mock.patch.object(pdf_reader, "read", side_effect=real) as spy:
            found = ask_passages.folder_data([str(self.box)], self.data, "zqpage1", home=None)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(set(spy.call_args.kwargs), {"truncated"})
        self.assertEqual(len(spy.call_args.args), 1)
        self.assertEqual((found.pdf, found.pdf_reasons), (1, (("saved/long.pdf", "too_many_pages"),)))

    def test_the_page_limit_is_the_index_constant_and_a_file_at_it_is_kept(self):
        self.put("four.pdf", pdf(["zqa", "zqb", "zqc", "zqd"]), binary=True)
        self.put("three.pdf", pdf(["zqe", "zqf", "zqg"]), binary=True)
        with mock.patch.object(ix.mod(), "INDEX_PDF_PAGES", 3):
            self.build()
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["indexed"], c["too_long"], c["type"]), (1, 1, 0))
        self.assertEqual(self.left(), {"saved/four.pdf": "is a PDF that is too long"})
        self.assertTrue(self.found("zqf"))
        self.assertFalse(self.found("zqa"))

    def test_the_size_limit_is_the_index_constant_and_a_file_at_it_is_kept(self):
        a, b = pdf(["zqone"]), pdf(["zqtwo", "zqmore"])
        self.put("at.pdf", a, binary=True)
        self.put("over.pdf", b, binary=True)
        self.assertGreater(len(b), len(a))
        with mock.patch.object(ix.mod(), "INDEX_PDF_BYTES", len(a)):
            self.build()
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["indexed"], c["too_long"]), (1, 1))
        self.assertEqual(self.left(), {"saved/over.pdf": "is a PDF that is too long"})

    def test_the_time_limit_is_the_index_constant_and_a_slow_file_is_too_long(self):
        self.put("slow.pdf", pdf(["HANG"]), binary=True)
        self.put("fast.pdf", pdf(["zqfast"]), binary=True)
        with mock.patch.object(ix.mod(), "INDEX_PDF_SECONDS", 1):
            self.build()
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["indexed"], c["too_long"], c["type"]), (1, 1, 0))
        self.assertEqual(self.left(), {"saved/slow.pdf": "is a PDF that is too long"})

    def test_the_index_run_gives_the_reader_all_three_limits_and_the_question_path_none(self):
        seen = []
        real = platform.run_stoppable

        def spy(args, data, env, limit, max_out, **k):
            seen.append((list(args), limit))
            return real(args, data, env, limit, max_out, **k)
        self.put("a.pdf", pdf(["zqone"]), binary=True)
        with mock.patch.object(platform, "run_stoppable", spy):
            self.build()
            args, limit = seen[-1]
            self.assertEqual((args[5], limit, args[-1], len(args)), ("2000", 120, "125", 9))
            pdf_reader.read(pdf(["zqone"]))
            args, limit = seen[-1]
            self.assertEqual((args[5], limit, len(args)), ("200", 20.0, 8))

    def test_an_index_run_reads_a_pdf_the_question_path_would_call_too_big(self):
        raw = pdf(["zqbig"])
        self.put("mid.pdf", raw, binary=True)
        with mock.patch.object(pdf_reader, "MAX_BYTES", len(raw) - 1):
            self.assertEqual(pdf_reader.read(raw).reason, "too_big")
            self.build()
        self.assertEqual(ix.status(self.data, "P1", None)["indexed"], 1)
        self.assertTrue(self.found("zqbig"))

    def test_the_child_gets_its_cpu_limit_from_the_wall_clock_given_and_15_otherwise(self):
        probe = FAKE_PYPDF.replace("return self.t.decode(\"latin-1\")", "import resource; return str(resource.getrlimit(resource.RLIMIT_CPU)[0])")
        self.assertNotEqual(probe, FAKE_PYPDF)
        (self.d / "vendor" / "pypdf" / "__init__.py").write_text(probe, encoding="utf-8")
        raw = pdf(["x"])
        self.assertEqual(pdf_reader.read(raw, seconds=72).pages, ((1, "77"),))
        self.assertEqual(pdf_reader.read(raw).pages, ((1, "15"),))

    def test_a_pdf_read_only_to_its_first_pages_is_too_long_not_indexed(self):
        self.put("cut.pdf", pdf(["zqlead" + "x" * 300, "zqlate" + "y" * 300, "zqlast" + "z" * 300]), binary=True)
        self.put("whole.pdf", pdf(["zqwhole"]), binary=True)
        with mock.patch.object(pdf_reader, "OUT_BUDGET", 700):
            self.assertEqual(pdf_reader.read(pdf(["a" * 300] * 3), vendor=pdf_reader.VENDOR).left_out, 1)
            self.build()
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["indexed"], c["too_long"], c["type"]), (1, 1, 0))
        self.assertEqual(self.left(), {"saved/cut.pdf": "is a PDF that is too long"})
        self.assertTrue(self.found("zqwhole"))
        self.assertFalse(self.found("zqlead"))

    def test_a_scanned_pdf_is_still_a_type_not_too_long(self):
        self.put("scan.pdf", pdf([None, None]), binary=True)
        self.build()
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["type"], c["too_long"]), (1, 0))

    def _zip3(self):
        import io
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            for n in ("a", "b", "c"):
                z.writestr(n, "x")
        return b.getvalue()

    def _line(self, *names):
        for n in names:
            self.put(n, self._zip3() if n.endswith(".xlsx") else pdf(["zqa", "zqb", "zqc", "zqd"]), binary=True)
        with mock.patch.object(ix.mod(), "INDEX_PDF_PAGES", 3), mock.patch.object(ix.mod(), "MAX_EXCEL_MEMBERS", 2):
            self.build()
        return ix.mod().line_for(ix.status(self.data, "P1", None))

    def test_the_status_line_names_no_file_type_for_a_pdf_only(self):
        self.assertEqual(self._line("a.pdf"), "Indexed 0 of 1 file. 1 file is too long.")

    def test_the_status_line_names_no_file_type_for_a_workbook_only(self):
        self.assertEqual(self._line("a.xlsx", "b.xlsx"), "Indexed 0 of 2 files. 2 files are too long.")

    def test_the_status_line_is_true_for_a_pdf_and_a_workbook_together(self):
        self.assertEqual(self._line("a.pdf", "b.xlsx"), "Indexed 0 of 2 files. 2 files are too long.")

    def test_the_pdf_time_limit_is_120_seconds_and_is_the_one_handed_to_the_reader(self):
        # Known limit (Row 1368): Stop is checked between files, so one PDF in progress runs to its end or to this limit (120 s).
        self.assertEqual(ix.mod().INDEX_PDF_SECONDS, 120)
        self.put("a.pdf", pdf(["zqa"]), binary=True)
        seen = []
        real = pdf_reader.read

        def spy(*a, **k):
            seen.append(k.get("seconds"))
            return real(*a, **k)
        with mock.patch.object(pdf_reader, "read", spy):
            self.build()
        self.assertEqual(seen, [120])

    def test_stop_is_checked_between_files_not_inside_one(self):
        import threading
        self.put("a.pdf", pdf(["zqa"]), binary=True)
        self.put("b.pdf", pdf(["zqb"]), binary=True)
        stop = threading.Event()
        reads = []
        real = pdf_reader.read

        def spy(*a, **k):
            reads.append(1)
            stop.set()      # Stop arrives while the first PDF is being read
            return real(*a, **k)
        with mock.patch.object(pdf_reader, "read", spy):
            done = ix.mod().refresh(self.data, "P1", [self.box], stop=stop)
        self.assertFalse(done)
        self.assertEqual(len(reads), 1)   # the one in progress was read to its end; the next file was never started


if __name__ == "__main__":
    unittest.main()
