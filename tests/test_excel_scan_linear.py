"""Row 1029: the streamed early check of an Excel workbook (excel_import._scan_member) reads in time proportional to the size of the
part, and a chunk cut never splits a text node so that its length goes unchecked. The hostile parts are built here; nothing is committed."""
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from clark import excel_import as xi

SST = b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>%s</t></si></sst>'


class ScanLinear(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="clark-scan-")
        self.addCleanup(self.tmp.cleanup)

    def scan(self, data, chunk=None):
        path = Path(self.tmp.name) / "part.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("xl/part.xml", data)
        t0 = time.process_time()
        with zipfile.ZipFile(path) as z:
            if chunk:
                with mock.patch.object(xi, "_SCAN_CHUNK", chunk):
                    out = xi._scan_member(z, "xl/part.xml", "Actions")
            else:
                out = xi._scan_member(z, "xl/part.xml", "Actions")
        return out, time.process_time() - t0

    def test_tags_that_never_close_are_scanned_in_linear_time(self):
        # 30,000 openers with no closing angle bracket: a regex that looks for the bracket from each opener reads the rest of the chunk
        # every time (several seconds at this size); a linear scan takes a few milliseconds.
        for unit in (b"<c ", b"<row ", b"<t ", b"<x:t "):
            with self.subTest(unit=unit):
                _out, seconds = self.scan(unit * 30000)
                self.assertLess(seconds, 1.0)

    def test_a_text_node_is_checked_whole_when_a_chunk_ends_inside_it(self):
        # the text holds '>' characters (legal in XML text), so the chunk cut after one lands inside the node
        text = b"a>" * (xi.MAX_CELL_TEXT // 2 + 10)
        for chunk in (1000, 4096, 10001, 65536):
            with self.subTest(chunk=chunk):
                with self.assertRaises(xi._TextTooLong):
                    self.scan(SST % text, chunk=chunk)
        with self.assertRaises(xi._TextTooLong):
            self.scan(SST % (b"a>" * 40000))           # longer than the default chunk too

    def test_a_text_under_the_limit_split_by_a_chunk_cut_is_let_through(self):
        text = b"a>" * 1000
        for chunk in (7, 100, 1000, 65536):
            with self.subTest(chunk=chunk):
                self.assertEqual(self.scan(SST % text, chunk=chunk)[0], (0, 0))

    def test_a_self_closed_t_does_not_start_a_text_node(self):
        # <t/> has no text: the long run of characters after it belongs to no cell, so it is not measured as one
        data = b"<sst><si><t/>" + b"a" * (xi.MAX_CELL_TEXT + 10) + b"</si></sst>"
        for chunk in (None, 4096):
            with self.subTest(chunk=chunk):
                self.assertEqual(self.scan(data, chunk=chunk)[0], (0, 0))


if __name__ == "__main__":
    unittest.main()
