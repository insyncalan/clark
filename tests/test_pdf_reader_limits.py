"""Hardening of src/clark/pdf_reader.py and pdf_reader_child.py: the numeric limits, the child's resource limits, and the error paths.

Run: python3 dev/run_tests.py test_pdf_reader_limits
Stand-in `pypdf` only; no real PDF library is needed."""
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import pdf_reader, pdf_reader_child as child, platform
from test_ask_pdf_passages import FAKE_PYPDF, pdf


class Limits(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / "pypdf").mkdir()
        (self.d / "pypdf" / "__init__.py").write_text(FAKE_PYPDF, encoding="utf-8")

    def read(self, raw):
        return pdf_reader.read(raw, vendor=self.d)

    def spy(self, raw):
        seen = {}
        real = platform.run_stoppable

        def run(args, data, env, limit, max_out, **kw):
            seen.update(args=list(args), limit=limit, max_out=max_out, kw=kw, data=data)
            return real(args, data, env, limit, max_out, **kw)
        with mock.patch.object(platform, "run_stoppable", side_effect=run):
            got = self.read(raw)
        return got, seen

    def test_the_constants_are_the_documented_limits(self):
        self.assertEqual((pdf_reader.SECONDS, pdf_reader.MAX_BYTES, pdf_reader.MAX_PAGES, pdf_reader.MAX_PAGE_CHARS, pdf_reader.MAX_OUT),
                         (20.0, 20 * 1024 * 1024, 200, 50_000, 2 * 1024 * 1024))

    def test_the_parent_hands_its_limits_and_the_bytes_to_the_runner(self):
        got, seen = self.spy(pdf(["ZQ a"]))
        self.assertEqual(got.status, "ok")
        self.assertEqual((seen["limit"], seen["max_out"]), (pdf_reader.SECONDS, pdf_reader.MAX_OUT))
        self.assertEqual(seen["args"][5:], [str(pdf_reader.MAX_PAGES), str(pdf_reader.MAX_PAGE_CHARS)])
        self.assertEqual(seen["kw"].get("prefix"), "clark-pdf-")
        self.assertEqual(seen["data"], pdf(["ZQ a"]))

    def test_a_bytearray_is_read(self):
        self.assertEqual(self.read(bytearray(pdf(["ZQ a"]))).status, "ok")

    def test_too_much_output_is_a_crash_not_a_partial_read(self):
        with mock.patch.object(pdf_reader, "MAX_OUT", 20):
            got = self.read(pdf(["ZQ " + "w" * 100]))
        self.assertEqual((got.status, got.reason, got.pages), ("not_read", "crash", ()))

    def test_every_code_the_child_may_say_is_passed_on(self):
        for code, status in (("too_many_pages", "not_read"), ("corrupt", "not_read"), ("unavailable", "not_read"),
                             ("scanned", "scanned"), ("encrypted", "encrypted"), ("too_big", "not_read"), ("timeout", "not_read")):
            said = json.dumps({"status": code, "pages": []}).encode()
            with mock.patch.object(platform, "run_stoppable", return_value=("ok", said, 0)):
                got = self.read(pdf(["ZQ a"]))
            self.assertEqual((got.status, got.reason, got.pages), (status, code, ()), code)

    def test_a_slow_run_is_a_timeout_and_any_other_failure_a_crash(self):
        with mock.patch.object(platform, "run_stoppable", return_value=("slow", b"", None)):
            self.assertEqual(self.read(pdf(["ZQ a"])).reason, "timeout")
        for status in ("failed", "stopped", "too_much", "weird"):
            with mock.patch.object(platform, "run_stoppable", return_value=(status, b"", None)):
                self.assertEqual(self.read(pdf(["ZQ a"])).reason, "crash", status)

    def test_a_bad_utf8_or_missing_key_is_a_crash(self):
        for out in (b"\xff\xfe", b"{}", b'{"status": "ok"}', b'{"status": "ok", "pages": [[1]]}'):
            with mock.patch.object(platform, "run_stoppable", return_value=("ok", out, 0)):
                self.assertEqual(self.read(pdf(["ZQ a"])).reason, "crash", out)

    def test_page_numbers_and_text_come_back_as_int_and_str(self):
        said = json.dumps({"status": "ok", "pages": [["2", "ZQ b"], [3, 7]]}).encode()
        with mock.patch.object(platform, "run_stoppable", return_value=("ok", said, 0)):
            self.assertEqual(self.read(pdf(["ZQ a"])).pages, ((2, "ZQ b"), (3, "7")))

    def test_the_size_check_comes_before_anything_starts_even_for_a_truncated_good_file(self):
        with mock.patch.object(platform, "run_stoppable") as run:
            self.assertEqual(pdf_reader.read(b"x" * (pdf_reader.MAX_BYTES + 1), vendor=self.d).reason, "too_big")
        run.assert_not_called()


class Child(unittest.TestCase):
    def run_child(self, data, argv=("v", "5", "10"), pypdf=None):
        mods = {"pypdf": pypdf} if pypdf is not None else {}
        out = io.StringIO()
        stdin = types.SimpleNamespace(buffer=io.BytesIO(data))
        with mock.patch.dict(sys.modules, mods), mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "stdout", out), \
                mock.patch.object(sys, "path", list(sys.path)), mock.patch.object(child, "_limits"):
            child.main(["child", *argv])
            path = list(sys.path)
        return json.loads(out.getvalue()), path

    def stub(self, pages, encrypted=False, strict_seen=None):
        class Page:
            def __init__(self, t): self.t = t
            def extract_text(self): return self.t

        class Reader:
            def __init__(self, stream, strict=True):
                if strict_seen is not None:
                    strict_seen.append(strict)
                self.is_encrypted = encrypted
                self.pages = [Page(t) for t in pages]
        return types.SimpleNamespace(PdfReader=Reader)

    def test_a_page_whose_text_is_none_counts_as_no_text(self):
        said, _ = self.run_child(b"x", pypdf=self.stub([None, "  ", "ZQ t"]))
        self.assertEqual(said, {"status": "ok", "pages": [[3, "ZQ t"]]})
        said, _ = self.run_child(b"x", pypdf=self.stub([None]))
        self.assertEqual(said, {"status": "scanned", "pages": []})

    def test_the_page_cap_and_the_char_cap_come_from_the_arguments(self):
        said, _ = self.run_child(b"x", argv=("v", "2", "3"), pypdf=self.stub(["abcdef", "gh"]))
        self.assertEqual(said["pages"], [[1, "abc"], [2, "gh"]])
        said, _ = self.run_child(b"x", argv=("v", "2", "3"), pypdf=self.stub(["a", "b", "c"]))
        self.assertEqual(said, {"status": "too_many_pages", "pages": []})

    def test_an_encrypted_file_is_refused_before_its_pages_are_touched(self):
        said, _ = self.run_child(b"x", pypdf=self.stub(["ZQ t"], encrypted=True))
        self.assertEqual(said, {"status": "encrypted", "pages": []})

    def test_the_vendor_folder_is_put_first_on_the_path_and_the_forgiving_read_is_asked_for(self):
        seen = []
        said, path = self.run_child(b"x", argv=("/the/vendor", "5", "10"), pypdf=self.stub(["ZQ t"], strict_seen=seen))
        self.assertEqual(path[0], "/the/vendor")
        self.assertEqual(seen, [False])

    def test_a_reader_that_raises_is_corrupt_and_nothing_else_leaks(self):
        class Boom:
            def PdfReader(self, *a, **k): raise ValueError("secret detail")
        said, _ = self.run_child(b"x", pypdf=types.SimpleNamespace(PdfReader=Boom().PdfReader))
        self.assertEqual(said, {"status": "corrupt", "pages": []})

    def test_a_page_that_raises_while_reading_is_corrupt(self):
        stub = self.stub(["a"])
        stub.PdfReader.__init__ = lambda self, s, strict=True: (setattr(self, "is_encrypted", False), setattr(self, "pages", [types.SimpleNamespace(extract_text=lambda: 1 / 0)]))[0]
        said, _ = self.run_child(b"x", pypdf=stub)
        self.assertEqual(said, {"status": "corrupt", "pages": []})

    def test_the_resource_limits_are_set_to_the_stated_values(self):
        import resource
        calls = {}
        with mock.patch.object(resource, "setrlimit", side_effect=lambda r, v: calls.__setitem__(r, v)):
            child._limits()
        self.assertEqual(calls, {resource.RLIMIT_CPU: (15, 15), resource.RLIMIT_AS: (1 << 30, 1 << 30), resource.RLIMIT_CORE: (0, 0)})

    def test_a_refused_limit_does_not_stop_the_others_or_the_read(self):
        import resource
        calls = []

        def refuse_first(r, v):
            calls.append(r)
            if len(calls) == 1:
                raise ValueError("no")
        with mock.patch.object(resource, "setrlimit", side_effect=refuse_first):
            child._limits()
        self.assertEqual(len(calls), 3)
        with mock.patch.object(resource, "setrlimit", side_effect=OSError("no")):
            child._limits()


if __name__ == "__main__":
    unittest.main()
