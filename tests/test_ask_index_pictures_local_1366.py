"""#1366 AP20: a picture is read on this Mac only and never sent to the provider. Made-up pictures and a made-up reader: no real recognition runs.
Run: python3 dev/run_tests.py test_ask_index_pictures_local_1366"""
import ast
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from clark import ask_picture, ask_vision_mac, platform as pl

NETWORK = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "requests", "asyncio", "xmlrpc", "telnetlib"}
RAW = b"\x89PNG-RAWPICTUREBYTES|zqlocalone words"


def _imports(module):
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


class PicturesLocal(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(ask_picture, "_READER", None)        # on a Mac ask_index registers the real reader at import: start with none
        p.start()
        self.addCleanup(p.stop)

    def reader(self, on=pl.MAC, fn=None):
        for p in (mock.patch.object(ask_picture.platform, "system", return_value=on), mock.patch.object(ask_picture, "_READER", fn)):
            p.start()
            self.addCleanup(p.stop)

    def test_pictures_read_locally_never_sent_to_provider(self):
        seen = []

        def reader(raw):
            seen.append(bytes(raw))
            return raw.decode("latin-1").split("|", 1)[-1]

        self.reader(fn=reader)
        pic = self.put("scan.png", RAW, binary=True)
        self.build()
        self.assertEqual(seen, [RAW])                                   # the picture went to the local reader and nowhere else
        got = self.found("zqlocalone")
        self.assertEqual(len(got), 1)
        sent = repr(got).encode("latin-1", "replace")                   # everything a question can hand to the provider
        self.assertIn(b"zqlocalone", sent)
        for leak in (b"RAWPICTUREBYTES", b"PNG-RAW", str(pic).encode()):
            self.assertNotIn(leak, sent)
        dbs = [p for p in Path(self.data).rglob("*") if p.is_file()]
        self.assertTrue(dbs)
        for p in dbs:                                                   # the picture's own bytes are not stored in the index either
            self.assertNotIn(b"RAWPICTUREBYTES", p.read_bytes(), p.name)
        for module in (ask_picture, ask_vision_mac):                    # neither reader module can open a connection
            self.assertEqual(_imports(module) & NETWORK, set(), module.__name__)
        self.assertNotIn("http", ask_vision_mac.SCRIPT.lower())
        self.assertNotIn("NSURLSession", ask_vision_mac.SCRIPT)

    def test_off_a_mac_the_picture_is_not_read_at_all(self):
        seen = []
        self.reader(on="linux", fn=lambda raw: seen.append(raw) or "x")
        self.assertIsNone(ask_picture.reader())                         # no reader is offered off a Mac
        self.put("scan.png", RAW, binary=True)
        self.build()
        self.assertEqual(seen, [])
        self.assertEqual(self.found("zqlocalone"), [])


if __name__ == "__main__":
    unittest.main()
