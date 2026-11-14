"""#891: ask clark reads PDFs (src/clark/pdf_reader.py, pdf_reader_child.py, wired in ask_passages.py).

Run: python3 dev/run_tests.py test_ask_pdf_passages
The PDFs are made in the test. The reader is checked twice: against a small stand-in `pypdf` written into a temporary vendor
folder (so the process, limits and outcomes are tested on every machine, even before the real library is vendored), and, when the
real vendored pypdf is present in vendor/, against it. What is asserted: a text PDF gives passages that keep their page number;
encrypted, scanned, corrupt, oversize, over-the-page-cap and slow PDFs are each reported (own code), never raise, and never give
a passage; the reading is done by another process (not the test's own) that is gone afterwards; no new words are shown."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask_passages, pdf_reader, platform, reach

FAKE_PYPDF = r'''
import os, re, sys, time
class PdfReader:
    def __init__(self, stream, strict=True):
        data = stream.read()
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data:
            raise ValueError("not a pdf")
        if strict and b"LOOSE" in data:             # a real strict reader refuses a slightly damaged file; clark asks for the forgiving read
            raise ValueError("strict")
        open(os.environ.get("TMPDIR", "/nonexistent") + "/pid", "w").write(str(os.getpid()))
        self.is_encrypted = b"/Encrypt" in data
        bodies = re.findall(rb"/Type /Page /Contents.*?stream\n(.*?)\nendstream", data, re.S)
        self.pages = [_Page((re.search(rb"\((.*?)\) Tj", b) or re.search(rb"()", b)).group(1)) for b in bodies]
class _Page:
    def __init__(self, t): self.t = t
    def extract_text(self):
        if self.t == b"HANG":
            time.sleep(60)
        return self.t.decode("latin-1")
'''


def pdf(pages, encrypted=False):
    """A tiny valid-looking PDF with one line of text on each page (a page that is None has no text, as a scan)."""
    out = [b"%PDF-1.4\n"]
    for i, text in enumerate(pages, 1):
        body = b"BT (" + text.encode() + b") Tj ET" if text else b""
        out.append(b"%d 0 obj\n<< /Type /Page /Contents 9 0 R >>\nstream\n%s\nendstream\nendobj\n" % (i, body))
    out.append(b"trailer\n<< /Root 1 0 R %s >>\n%%%%EOF\n" % (b"/Encrypt 8 0 R" if encrypted else b""))
    return b"".join(out)


class Fake(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.vendor = self.d / "vendor"
        (self.vendor / "pypdf").mkdir(parents=True)
        (self.vendor / "pypdf" / "__init__.py").write_text(FAKE_PYPDF, encoding="utf-8")

    def read(self, raw):
        return pdf_reader.read(raw, vendor=self.vendor)


class Outcomes(Fake):
    def test_text_pdf_keeps_every_page_number(self):
        got = self.read(pdf(["ZQ first page", "ZQ second page", "ZQ third page"]))
        self.assertEqual((got.status, got.reason), ("ok", ""))
        self.assertEqual(got.pages, ((1, "ZQ first page"), (2, "ZQ second page"), (3, "ZQ third page")))

    def test_empty_pages_are_skipped_but_numbers_stay(self):
        got = self.read(pdf(["", "ZQ only text", ""]))
        self.assertEqual(got.pages, ((2, "ZQ only text"),))

    def test_scanned_pdf_has_its_own_code(self):
        got = self.read(pdf(["", ""]))
        self.assertEqual((got.status, got.reason, got.pages), ("scanned", "scanned", ()))

    def test_encrypted_pdf_has_its_own_code(self):
        got = self.read(pdf(["ZQ secret"], encrypted=True))
        self.assertEqual((got.status, got.reason, got.pages), ("encrypted", "encrypted", ()))

    def test_corrupt_bytes_are_not_read(self):
        for raw in (b"", b"just some words", b"%PDF-1.4 cut off", os.urandom(300)):
            got = self.read(raw)
            self.assertEqual((got.status, got.reason, got.pages), ("not_read", "corrupt", ()), raw[:20])

    def test_oversize_is_not_read_and_nothing_is_started(self):
        with mock.patch.object(pdf_reader, "MAX_BYTES", 100), mock.patch.object(platform, "run_stoppable") as run:
            got = self.read(pdf(["ZQ " + "x" * 200]))
        self.assertEqual((got.status, got.reason), ("not_read", "too_big"))
        run.assert_not_called()

    def test_truncated_read_is_too_big(self):
        with mock.patch.object(platform, "run_stoppable") as run:
            got = pdf_reader.read(pdf(["ZQ a"]), vendor=self.vendor, truncated=True)
        self.assertEqual((got.status, got.reason), ("not_read", "too_big"))
        run.assert_not_called()

    def test_over_the_page_cap_is_not_read(self):
        with mock.patch.object(pdf_reader, "MAX_PAGES", 2):
            got = self.read(pdf(["ZQ a", "ZQ b", "ZQ c"]))
        self.assertEqual((got.status, got.reason, got.pages), ("not_read", "too_many_pages", ()))

    def test_a_hanging_pdf_is_stopped_at_the_limit(self):
        with mock.patch.object(pdf_reader, "SECONDS", 1.5):
            got = self.read(pdf(["HANG"]))
        self.assertEqual((got.status, got.reason, got.pages), ("not_read", "timeout", ()))

    def test_missing_library_is_not_read(self):
        got = pdf_reader.read(pdf(["ZQ a"]), vendor=self.d / "nothing-here")
        self.assertEqual((got.status, got.reason), ("not_read", "unavailable"))

    def test_a_crash_or_an_odd_answer_never_raises(self):
        for answer in (("failed", b"", 1), ("ok", b"not json", 0), ("ok", b'{"status": "ok", "pages": [["x", 1]]}', 0), ("too_much", b"", None)):
            with mock.patch.object(platform, "run_stoppable", return_value=answer):
                got = self.read(pdf(["ZQ a"]))
            self.assertEqual((got.status, got.reason, got.pages), ("not_read", "crash", ()), answer)
        with mock.patch.object(platform, "run_stoppable", side_effect=RuntimeError("boom")):
            self.assertEqual(self.read(pdf(["ZQ a"])).reason, "crash")

    # mutation hunt (item 1182): the size edge, odd answers, the forgiving read and the child's trimming were not pinned
    def test_a_file_of_exactly_the_size_cap_is_read_and_one_byte_more_is_not(self):
        raw = pdf(["ZQ edge"])
        with mock.patch.object(pdf_reader, "MAX_BYTES", len(raw)):
            self.assertEqual(self.read(raw).status, "ok")
        with mock.patch.object(pdf_reader, "MAX_BYTES", len(raw) - 1):
            self.assertEqual(self.read(raw).reason, "too_big")

    def test_something_that_is_not_bytes_is_too_big_and_nothing_is_started(self):
        with mock.patch.object(platform, "run_stoppable") as run:
            for raw in ("text", None, 12):
                self.assertEqual(pdf_reader.read(raw, vendor=self.vendor).reason, "too_big", raw)
        run.assert_not_called()

    def test_a_page_count_equal_to_the_cap_is_read(self):
        with mock.patch.object(pdf_reader, "MAX_PAGES", 2):
            got = self.read(pdf(["ZQ a", "ZQ b"]))
        self.assertEqual((got.status, len(got.pages)), ("ok", 2))

    def test_the_reader_asks_for_the_forgiving_read(self):
        got = self.read(pdf(["ZQ LOOSE words"]))
        self.assertEqual((got.status, got.pages), ("ok", ((1, "ZQ LOOSE words"),)))

    def test_the_child_trims_the_text_of_a_page(self):
        self.assertEqual(self.read(pdf(["  ZQ padded  "])).pages, ((1, "ZQ padded"),))

    def test_odd_answers_from_the_child_are_sorted_out(self):
        def answer(said):
            with mock.patch.object(platform, "run_stoppable", return_value=("ok", json.dumps(said).encode(), 0)):
                return self.read(pdf(["ZQ a"]))
        got = answer({"status": "ok", "pages": [[0, "ZQ zero"], [2, "   "], [3, "ZQ real"]]})
        self.assertEqual((got.status, got.pages), ("ok", ((3, "ZQ real"),)))
        got = answer({"status": "ok", "pages": []})
        self.assertEqual((got.status, got.reason), ("scanned", "scanned"))
        got = answer({"status": "weird", "pages": []})
        self.assertEqual((got.status, got.reason), ("not_read", "crash"))
        with mock.patch.object(platform, "run_stoppable", return_value=("too_much", b'{"status": "ok", "pages": [[1, "ZQ a"]]}', None)):
            self.assertEqual(self.read(pdf(["ZQ a"])).reason, "crash")

    def test_the_child_gets_a_minimal_environment(self):
        env = pdf_reader._env()
        self.assertEqual(env["PATH"], "/usr/bin:/bin")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(set(env), {"PATH", "LANG", "LC_ALL", "PYTHONDONTWRITEBYTECODE"})

    def test_long_page_text_is_cut(self):
        with mock.patch.object(pdf_reader, "MAX_PAGE_CHARS", 10):
            got = self.read(pdf(["ZQ " + "y" * 100]))
        self.assertEqual(got.pages, ((1, "ZQ yyyyyyy"),))


    def test_sixty_full_pages_are_read_not_a_crash(self):
        # 60 pages of about 50,000 characters is 3 MB of output: over the old 2 MB cap (which made it "crash"), so the leading pages must come back.
        got = self.read(pdf(["ZQ %d " % i + "x" * (pdf_reader.MAX_PAGE_CHARS - 10) for i in range(60)]))
        self.assertEqual(got.status, "ok")
        self.assertTrue(10 < len(got.pages) <= 60)
        self.assertEqual([n for n, _t in got.pages], list(range(1, len(got.pages) + 1)))

    def test_over_the_output_budget_keeps_the_leading_pages_not_a_crash(self):
        with mock.patch.object(pdf_reader, "OUT_BUDGET", 5000):
            got = self.read(pdf(["ZQ %d " % i + "x" * 900 for i in range(20)]))
        self.assertEqual(got.status, "ok")
        self.assertTrue(0 < len(got.pages) < 20)
        self.assertEqual([n for n, _t in got.pages], list(range(1, len(got.pages) + 1)))

    def test_a_cut_at_the_output_budget_is_counted_as_left_out(self):
        # pdf-2: the cut was silent; the reader now says pages were left out, and ask counts them so the existing "too long" note shows.
        with mock.patch.object(pdf_reader, "OUT_BUDGET", 5000):
            got = self.read(pdf(["ZQ %d " % i + "x" * 900 for i in range(20)]))
        self.assertEqual(got.left_out, 20 - len(got.pages))
        self.assertGreater(got.left_out, 0)

    def test_a_pdf_read_in_full_leaves_nothing_out(self):
        self.assertEqual(self.read(pdf(["ZQ one", "ZQ two"])).left_out, 0)

    def test_a_first_page_bigger_than_the_budget_is_still_read(self):
        # The guard keeps at least one page: a lone page over the budget is returned, not dropped to an empty or failed result.
        with mock.patch.object(pdf_reader, "OUT_BUDGET", 100):
            got = self.read(pdf(["ZQ one " + "x" * 400, "ZQ two " + "x" * 400]))
        self.assertEqual((got.status, got.reason), ("ok", ""))
        self.assertEqual([n for n, _t in got.pages], [1])

    def test_the_child_sets_memory_and_cpu_limits(self):
        import importlib.util
        import resource
        spec = importlib.util.spec_from_file_location("pdf_child_under_test", pdf_reader.CHILD)
        child = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(child)
        with mock.patch.object(resource, "setrlimit") as setr:
            child._limits()
        got = {c.args[0]: c.args[1] for c in setr.call_args_list}
        self.assertEqual(got[resource.RLIMIT_AS], (1024 ** 3, 1024 ** 3))
        self.assertLessEqual(got[resource.RLIMIT_CPU][0], pdf_reader.SECONDS + 5)


class SeparateProcess(Fake):
    def test_the_reader_is_another_process_started_without_the_servers_environment(self):
        seen = {}
        real = platform.run_stoppable

        def spy(args, data, env, limit, max_out, **kw):
            seen.update(args=list(args), env=dict(env), limit=limit, max_out=max_out)
            return real(args, data, env, limit, max_out, **kw)
        with mock.patch.dict(os.environ, {"ZQ_SECRET_ENV": "x"}), mock.patch.object(platform, "run_stoppable", side_effect=spy):
            got = self.read(pdf(["ZQ a"]))
        self.assertEqual(got.status, "ok")
        self.assertEqual(seen["args"][:3], [sys.executable, "-I", "-S"])
        self.assertTrue(seen["args"][3].endswith("pdf_reader_child.py"))
        self.assertNotIn("ZQ_SECRET_ENV", seen["env"])
        self.assertLessEqual(seen["limit"], 30)
        self.assertNotIn("pypdf", sys.modules, "the server's own process never imports the library")

    def test_the_child_runs_under_its_own_pid_and_group(self):
        code = "import os,sys;sys.stdout.write(str(os.getpid())+' '+str(os.getpgrp()))"
        status, out, _c = platform.run_stoppable([sys.executable, "-I", "-S", "-c", code], b"", pdf_reader._env(), 10, 100)
        pid, group = (int(x) for x in out.split())
        self.assertNotEqual(pid, os.getpid())
        self.assertNotEqual(group, os.getpgrp())

    def test_no_process_is_left_after_a_timeout(self):
        before = subprocess.run(["pgrep", "-f", "pdf_reader_child.py"], capture_output=True).stdout
        with mock.patch.object(pdf_reader, "SECONDS", 1.0):
            self.read(pdf(["HANG"]))
        after = subprocess.run(["pgrep", "-f", "pdf_reader_child.py"], capture_output=True).stdout
        self.assertEqual(before, after)


class InAsk(Fake):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        p.start()
        self.addCleanup(p.stop)
        v = mock.patch.object(pdf_reader, "VENDOR", self.vendor)
        v.start()
        self.addCleanup(v.stop)
        self.data = self.d / "data"
        self.box = self.d / "saved"
        self.data.mkdir()
        self.box.mkdir()

    def put(self, name, raw):
        (self.box / name).write_bytes(raw)

    def run_it(self):
        return ask_passages.folder_data([str(self.box)], self.data, "plan")

    def test_passages_carry_the_page_and_the_name_in_the_folder(self):
        self.put("Plan.pdf", pdf(["ZQ budget is agreed", "ZQ deadline is May", "ZQ risks"]))
        got = self.run_it()
        self.assertEqual((got.pdf, got.pdf_reasons, got.safety), (0, (), 0))
        labels = {p.label: p.text for p in got.passages}
        self.assertEqual(labels, {"saved/Plan.pdf, page 1": "ZQ budget is agreed", "saved/Plan.pdf, page 2": "ZQ deadline is May",
                                  "saved/Plan.pdf, page 3": "ZQ risks"})
        self.assertEqual({(p.file, p.page) for p in got.passages}, {("saved/Plan.pdf", 1), ("saved/Plan.pdf", 2), ("saved/Plan.pdf", 3)})   # #943: the open-at-page fields

    # mutation hunt (item 1182): part labels, the part cap, the char and byte budgets and the size cap's source were never pinned
    def test_a_long_page_is_cut_into_parts_that_keep_the_page_number(self):
        self.put("Plan.pdf", pdf(["ZQ " + "a" * 57, "ZQ short"]))
        with mock.patch.object(ask_passages.ask_data, "PASSAGE_SIZE", 20):
            got = self.run_it()
        labels = [p.label for p in got.passages]
        self.assertEqual(labels, ["saved/Plan.pdf, page 1", "saved/Plan.pdf, page 1, part 2", "saved/Plan.pdf, page 1, part 3", "saved/Plan.pdf, page 2"])
        self.assertEqual([p.page for p in got.passages], [1, 1, 1, 2])
        self.assertEqual("".join(p.text for p in got.passages[:3]), "ZQ " + "a" * 57)

    def test_one_pdf_gives_at_most_the_part_cap_of_passages(self):
        self.put("Plan.pdf", pdf(["ZQ " + "a" * 197]))
        with mock.patch.object(ask_passages.ask_data, "PASSAGE_SIZE", 20), mock.patch.object(ask_passages, "MAX_PDF_PARTS", 4):
            got = self.run_it()
        self.assertEqual([p.label for p in got.passages][-1], "saved/Plan.pdf, page 1, part 4")
        self.assertEqual(len(got.passages), 4)

    def test_parts_cut_by_the_part_cap_are_counted_as_left_out(self):
        self.put("Plan.pdf", pdf(["ZQ " + "a" * 197]))
        with mock.patch.object(ask_passages.ask_data, "PASSAGE_SIZE", 20), mock.patch.object(ask_passages, "MAX_PDF_PARTS", 4):
            got = self.run_it()
        self.assertGreater(got.left_out, 0)

    def test_pages_cut_by_the_reader_budget_are_counted_as_left_out_in_ask(self):
        self.put("Plan.pdf", pdf(["ZQ %d " % i + "x" * 900 for i in range(20)]))
        with mock.patch.object(pdf_reader, "OUT_BUDGET", 5000):
            got = self.run_it()
        self.assertGreater(got.left_out, 0)

    def test_the_part_cap_leaves_room_for_every_page_of_the_longest_pdf(self):
        self.assertGreaterEqual(ask_passages.MAX_PDF_PARTS, pdf_reader.MAX_PAGES)

    def test_the_text_of_a_pdf_counts_against_the_character_budget(self):
        self.put("a.pdf", pdf(["ZQ " + "a" * 30]))
        self.put("b.pdf", pdf(["ZQ second file"]))
        with mock.patch.object(ask_passages, "MAX_CHARS", 10):
            got = self.run_it()
        self.assertEqual(sorted({p.file for p in got.passages}), ["saved/a.pdf"])
        self.assertEqual(got.other, 1, "the second file is left out, counted")

    def test_the_bytes_of_a_pdf_count_against_the_byte_budget(self):
        self.put("a.pdf", pdf(["ZQ first file"]))
        self.put("b.pdf", pdf(["ZQ second file"]))
        with mock.patch.object(ask_passages, "MAX_BYTES_READ", 10):
            got = self.run_it()
        self.assertEqual(sorted({p.file for p in got.passages}), ["saved/a.pdf"])
        self.assertEqual(got.other, 1)

    def test_the_folder_reader_reads_a_file_up_to_the_readers_own_limit(self):
        self.assertEqual(ask_passages.MAX_PDF_BYTES, pdf_reader.MAX_BYTES)

    def test_each_failure_is_counted_with_its_code_and_gives_no_passage(self):
        self.put("good.pdf", pdf(["ZQ fine"]))
        self.put("scan.pdf", pdf(["", ""]))
        self.put("locked.pdf", pdf(["ZQ x"], encrypted=True))
        self.put("broken.pdf", b"%PDF-1.4 ZQ-BROKEN")
        got = self.run_it()
        self.assertEqual([p.label for p in got.passages], ["saved/good.pdf, page 1"])
        self.assertEqual(got.pdf, 3)
        self.assertEqual(dict(got.pdf_reasons), {"saved/scan.pdf": "scanned", "saved/locked.pdf": "encrypted", "saved/broken.pdf": "corrupt"})
        self.assertNotIn("ZQ-BROKEN", "\n".join(p.text for p in got.passages))

    def test_a_file_over_the_size_cap_is_not_read(self):
        self.put("big.pdf", pdf(["ZQ " + "z" * 500]))
        with mock.patch.object(ask_passages, "MAX_PDF_BYTES", 100):
            got = self.run_it()
        self.assertEqual((got.pdf, got.pdf_reasons, got.passages), (1, (("saved/big.pdf", "too_big"),), ()))

    def test_a_slow_pdf_does_not_stop_the_other_files(self):
        self.put("slow.pdf", pdf(["HANG"]))
        (self.box / "note.txt").write_text("ZQ-TEXT still read", encoding="utf-8")
        with mock.patch.object(pdf_reader, "SECONDS", 1.0):
            got = self.run_it()
        self.assertEqual(got.pdf_reasons, (("saved/slow.pdf", "timeout"),))
        self.assertIn("ZQ-TEXT", "\n".join(p.text for p in got.passages))

    def test_a_pdf_that_looks_like_a_key_is_left_out_for_safety(self):
        self.put("keys.pdf", pdf(["-----BEGIN " + "PRIVATE KEY----- MIIEvQIBADANBgkqhkiG9w0BAQEFAASC"]))
        got = self.run_it()
        self.assertEqual((got.passages, got.safety), ((), 1))


class Words(unittest.TestCase):
    """Row 891: the approved sentences (#1052), for every reason code, in the count form, the per-file form and the source label."""
    def test_each_reason_has_its_sentence_in_both_forms(self):
        want = {"scanned": "it holds pictures of pages and no text", "encrypted": "it is protected with a password", "too_big": "it is too big",
                "too_many_pages": "it has too many pages"}
        for code in pdf_reader.REASONS:
            why = want.get(code, "it could not be read safely")
            self.assertEqual(pdf_reader.count_note(1, code), f"1 PDF was not read: {why}.", code)
            self.assertEqual(pdf_reader.count_note(3, code), f"3 PDF were not read: {why}.", code)
            self.assertEqual(pdf_reader.file_note("Plan.pdf", code), f"Plan.pdf was not read: {why}.", code)
        self.assertEqual(pdf_reader.SOURCE_PAGE.format(name="Plan.pdf", page=2), "Plan.pdf, page 2")

    def test_the_notes_under_an_answer_say_the_reason_for_each_kind(self):
        from clark import ask_passages, ask_service
        found = ask_passages.FolderData(pdf=4, pdf_reasons=(("a.pdf", "scanned"), ("b.pdf", "encrypted"), ("c.pdf", "scanned"), ("d.pdf", "crash")))
        notes = [n for n in ask_service.folder_notes(found) if "PDF" in n]
        self.assertEqual(notes, ["2 PDF were not read: it holds pictures of pages and no text.", "1 PDF was not read: it is protected with a password.",
                                 "1 PDF was not read: it could not be read safely."])
        self.assertFalse(any("not supported" in n for n in ask_service.folder_notes(found)))


@unittest.skipUnless((pdf_reader.VENDOR / "pypdf").is_dir(), "the vendored pypdf is not in this checkout")
class RealLibrary(unittest.TestCase):
    def test_a_real_text_pdf_is_read_with_its_page(self):
        # A well-formed file (objects, a cross-reference table and a startxref line with true byte offsets): the vendored library
        # refuses a file with no startxref, so the earlier hand-written fixture without a table was not a readable PDF at all.
        body = b"BT /F1 12 Tf 20 100 Td (Hello from a tiny PDF) Tj ET"
        objects = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
                   b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
                   b"<</Length %d>>\nstream\n" % len(body) + body + b"\nendstream",
                   b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
        raw, offsets = b"%PDF-1.4\n", []
        for number, obj in enumerate(objects, 1):
            offsets.append(len(raw))
            raw += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
        table = len(raw)
        raw += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % o for o in offsets)
        raw += b"trailer\n<</Root 1 0 R/Size 6>>\nstartxref\n%d\n%%%%EOF\n" % table
        got = pdf_reader.read(raw)
        self.assertEqual(got.status, "ok")
        self.assertEqual(got.pages[0][0], 1)
        self.assertIn("Hello from a tiny PDF", got.pages[0][1])

    def test_garbage_is_not_read(self):
        self.assertEqual(pdf_reader.read(os.urandom(500)).status, "not_read")


if __name__ == "__main__":
    unittest.main()
