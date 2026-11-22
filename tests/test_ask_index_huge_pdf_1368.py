"""Row 1368: what a huge PDF shows today, with the REAL vendored pypdf (no stand-in): too many pages, too many bytes, too much text for
the output budget, and memory exhaustion in the child. Pins the behaviour as it is; the memory case is `corrupt` (shown as `type`).
The child sets its own RLIMIT_AS (1 GiB), so run this WITHOUT ulimit -v: bash ~/wo/loadgate.sh -p 70 -- python3 dev/run_tests.py test_ask_index_huge_pdf_1368
Made-up files only; nothing big is written to disk."""
import subprocess
import sys
import zlib
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from clark import pdf_reader, pdf_reader_child

LINE = b"BT /F1 12 Tf 10 100 Td (%s) Tj ET"


def real_pdf(streams, big=0):
    """A valid PDF (real xref) with one page per content stream; `big` > 0 makes one page whose Flate stream inflates to that many bytes of text."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids, bodies = [], []
    for s in streams:
        bodies.append((s, b""))
    if big:
        packer, parts, left = zlib.compressobj(), [], big
        parts.append(packer.compress(b"BT /F1 12 Tf 10 100 Td ("))
        while left > 0:
            step = min(left, 1 << 20)
            parts.append(packer.compress(b"a" * step))
            left -= step
        parts.append(packer.compress(b") Tj ET") + packer.flush())
        bodies.append((b"".join(parts), b" /Filter /FlateDecode"))
    for body, flt in bodies:
        n = len(objs) + 1
        kids.append(b"%d 0 R" % n)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (n + 1))
        objs.append(b"<< /Length %d%s >>\nstream\n" % (len(body), flt) + body + b"\nendstream")
    objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(kids), len(kids))
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    return bytes(out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x))


def pages(words):
    return real_pdf([LINE % w.encode() for w in words])


WRAP = """import sys, resource
sys.path.insert(0, sys.argv[1])
import pdf_reader_child as c
limit = int(sys.argv[2])
c._limits = lambda cpu=15: resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
c.main([sys.argv[0]] + sys.argv[3:])
"""


def child_says(raw, as_limit):
    """The real child, with its RLIMIT_AS replaced by `as_limit` bytes; returns the status it prints."""
    src = str(pdf_reader_child.__file__.rsplit("/", 1)[0])
    done = subprocess.run([sys.executable, "-c", WRAP, src, str(as_limit), str(pdf_reader.VENDOR), "200", "50000"], input=raw, capture_output=True, timeout=120)
    return done.stdout.decode()


class Huge(Base):
    def state(self, name):
        self.build()
        c = ix.status(self.data, "P1", None)
        return {k: c[k] for k in ("indexed", "too_long", "type")}, dict(ix.mod().files_left_out(self.data, "P1", 200)["files"]).get("saved/" + name)

    def test_the_fixture_is_a_real_pdf_the_real_reader_reads(self):
        got = pdf_reader.read(pages(["zqone", "zqtwo"]))
        self.assertEqual((got.status, [t for _n, t in got.pages]), ("ok", ["zqone", "zqtwo"]))

    def test_over_the_page_limit_is_too_long_and_none_of_its_pages_are_indexed(self):
        self.put("long.pdf", pages(["zqa", "zqb", "zqc", "zqd"]), binary=True)
        with mock.patch.object(ix.mod(), "INDEX_PDF_PAGES", 3):
            self.assertEqual(pdf_reader.read(pages(["a", "b", "c", "d"]), max_pages=3).reason, "too_many_pages")
            self.assertEqual(self.state("long.pdf"), ({"indexed": 0, "too_long": 1, "type": 0}, "is a PDF that is too long"))
        self.assertFalse(self.found("zqa"))

    def test_over_the_byte_limit_is_too_long_the_child_is_never_started(self):
        raw = pages(["zqa", "zqb"])
        self.put("fat.pdf", raw, binary=True)
        with mock.patch.object(ix.mod(), "INDEX_PDF_BYTES", len(raw) - 1), mock.patch.object(pdf_reader.platform, "run_stoppable") as run:
            self.assertEqual(self.state("fat.pdf"), ({"indexed": 0, "too_long": 1, "type": 0}, "is a PDF that is too long"))
        run.assert_not_called()
        self.assertEqual(pdf_reader.read(raw, max_bytes=len(raw) - 1).reason, "too_big")

    def test_over_the_output_budget_is_too_long_and_none_of_its_pages_are_indexed(self):
        self.put("wide.pdf", pages(["zq%d " % i + "x" * 1500 for i in range(6)]), binary=True)
        with mock.patch.object(pdf_reader, "OUT_BUDGET", 4000):
            got = pdf_reader.read(pages(["zq%d " % i + "x" * 1500 for i in range(6)]))
            self.assertEqual((got.status, len(got.pages) < 6, got.left_out > 0), ("ok", True, True))
            self.assertEqual(self.state("wide.pdf"), ({"indexed": 0, "too_long": 1, "type": 0}, "is a PDF that is too long"))
        self.assertFalse(self.found("zq0"))

    def test_memory_exhaustion_in_the_child_says_corrupt_not_too_long(self):
        raw = real_pdf([], big=20 * 1024 * 1024)
        self.assertEqual(len(raw) < 100 * 1024, True)
        self.assertIn('"status": "ok"', child_says(raw, 3 * 10 ** 9))                       # the same file reads fine with room
        self.assertEqual(child_says(raw, 200 * 1024 * 1024), '{"status": "corrupt", "pages": []}')   # too little memory: the catch-all says corrupt

    def test_a_flate_bomb_past_pypdfs_own_75mb_cap_is_corrupt_and_listed_as_type(self):
        raw = real_pdf([], big=600 * 1024 * 1024)                 # pypdf refuses a stream past 75 MB itself (a 70 MB one reads, with 3 GiB or 1 GiB): not memory, but the same answer
        got = pdf_reader.read(raw)
        self.assertEqual((got.status, got.reason), ("not_read", "corrupt"))
        self.put("bomb.pdf", raw, binary=True)
        self.assertEqual(self.state("bomb.pdf"), ({"indexed": 0, "too_long": 0, "type": 1}, ix.mod().REASON_TYPE))


if __name__ == "__main__":
    unittest.main()
