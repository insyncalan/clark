"""#891: ask clark reads PDFs (src/clark/pdf_reader.py, pdf_reader_child.py, wired in ask_passages.py).

Run: python3 dev/run_tests.py test_ask_pdf_passages
The PDFs are made in the test. The reader is checked twice: against a small stand-in `pypdf` written into a temporary vendor
folder (so the process, limits and outcomes are tested on every machine, even before the real library is vendored), and, when the
real vendored pypdf is present in vendor/, against it. What is asserted: a text PDF gives passages that keep their page number;
encrypted, scanned, corrupt, oversize, over-the-page-cap and slow PDFs are each reported (own code), never raise, and never give
a passage; the reading is done by another process (not the test's own) that is gone afterwards; the words about PDFs (notes, Help) say they are read."""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask_passages, ask_service, pdf_reader, platform, reach

FAKE_PYPDF = r'''
import os, re, sys, time
class PdfReader:
    def __init__(self, stream, strict=True):
        data = stream.read()
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data:
            raise ValueError("not a pdf")
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

    def test_long_page_text_is_cut(self):
        with mock.patch.object(pdf_reader, "MAX_PAGE_CHARS", 10):
            got = self.read(pdf(["ZQ " + "y" * 100]))
        self.assertEqual(got.pages, ((1, "ZQ yyyyyyy"),))



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
        self.assertEqual(labels, {"saved/Plan.pdf (page 1)": "ZQ budget is agreed", "saved/Plan.pdf (page 2)": "ZQ deadline is May",
                                  "saved/Plan.pdf (page 3)": "ZQ risks"})
        self.assertEqual({(p.file, p.page) for p in got.passages}, {("saved/Plan.pdf", 1), ("saved/Plan.pdf", 2), ("saved/Plan.pdf", 3)})   # #943: the open-at-page fields

    def test_each_failure_is_counted_with_its_code_and_gives_no_passage(self):
        self.put("good.pdf", pdf(["ZQ fine"]))
        self.put("scan.pdf", pdf(["", ""]))
        self.put("locked.pdf", pdf(["ZQ x"], encrypted=True))
        self.put("broken.pdf", b"%PDF-1.4 ZQ-BROKEN")
        got = self.run_it()
        self.assertEqual([p.label for p in got.passages], ["saved/good.pdf (page 1)"])
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


class WordsAboutPdfs(unittest.TestCase):
    """#891: the sentences that say what happened to a PDF (ask_service.folder_notes) and the Help line about PDFs."""
    NOTE = ("{n} PDF {was} not read: ", )

    def notes(self, *reasons):
        found = ask_passages.FolderData(pdf=len(reasons), pdf_reasons=tuple((f"saved/{i}.pdf", r) for i, r in enumerate(reasons)))
        return [n for n in ask_service.folder_notes(found)]

    def test_a_scanned_pdf_is_said_to_have_no_text_to_read(self):
        self.assertEqual(self.notes("scanned"), ["1 PDF file was not read: it has no text to read."])

    def test_an_encrypted_pdf_is_said_to_be_protected(self):
        self.assertEqual(self.notes("encrypted"), ["1 PDF file was not read: it is protected with a password."])

    def test_any_other_pdf_is_said_to_be_unreadable_safely(self):
        for reason in ("too_big", "too_many_pages", "timeout", "crash", "corrupt", "unavailable"):
            self.assertEqual(self.notes(reason), ["1 PDF file was not read: it could not be read safely."], reason)

    def test_counts_are_given_per_reason_and_in_the_plural(self):
        self.assertEqual(self.notes("scanned", "scanned", "encrypted", "corrupt"),
                         ["2 PDF files were not read: they have no text to read.",
                          "1 PDF file was not read: it is protected with a password.",
                          "1 PDF file was not read: it could not be read safely."])

    def test_nothing_is_said_when_every_pdf_was_read(self):
        self.assertEqual(self.notes(), [])

    def test_no_sentence_says_pdf_is_not_supported(self):
        text = (Path(ask_service.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("not supported yet", text)

    def test_the_draft_word_table_is_gone(self):
        self.assertFalse(hasattr(pdf_reader, "NEW_WORDS"))

    def test_help_says_pdfs_are_read_on_this_computer(self):
        import json
        raw = json.loads((Path(ask_service.__file__).parent / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
        flat = json.dumps(raw, ensure_ascii=False)
        self.assertNotIn("PDF files are not read yet", flat)
        self.assertIn("It reads Word, PDF, text, Markdown and CSV files. A PDF is read on this computer and nothing leaves it.", flat)
        self.assertIn("A PDF that is only pictures of pages has no text to read, because clark does not read pictures of text, and a PDF protected with a password is not read.", flat)


def real_pdf(pages):
    """A well-formed PDF (with its cross-reference table, which the real library needs) with one line of text on each page."""
    objs = [b"<</Type/Catalog/Pages 2 0 R>>",
            b"<</Type/Pages/Kids[%s]/Count %d>>" % (b" ".join(b"%d 0 R" % (5 + 2 * i) for i in range(len(pages))), len(pages)),
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    for i, text in enumerate(pages):
        body = b"BT /F1 12 Tf 20 100 Td (%s) Tj ET" % text.encode()
        objs.append(b"<</Length %d>>stream\n%s\nendstream" % (len(body), body))
        objs.append(b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents %d 0 R/Resources<</Font<</F1 3 0 R>>>>>>" % (4 + 2 * i))
    out, offsets = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer<</Root 1 0 R/Size %d>>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


@unittest.skipUnless((pdf_reader.VENDOR / "pypdf").is_dir(), "the vendored pypdf is not in this checkout")
class RealLibrary(unittest.TestCase):
    def test_a_real_text_pdf_is_read_with_its_page(self):
        raw = real_pdf(["Hello from a tiny PDF"])
        got = pdf_reader.read(raw)
        self.assertEqual(got.status, "ok")
        self.assertEqual(got.pages[0][0], 1)
        self.assertIn("Hello from a tiny PDF", got.pages[0][1])

    def test_each_page_keeps_its_number(self):
        got = pdf_reader.read(real_pdf(["First page text", "Second page text"]))
        self.assertEqual([(n, t) for n, t in got.pages], [(1, "First page text"), (2, "Second page text")])

    def test_garbage_is_not_read(self):
        self.assertEqual(pdf_reader.read(os.urandom(500)).status, "not_read")


if __name__ == "__main__":
    unittest.main()
