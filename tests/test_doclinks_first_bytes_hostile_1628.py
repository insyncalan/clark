"""Row 1194 hostile pass (PR 1628): the first-bytes rule, one case per signature and per edge of the text rule."""
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on sys.path)
from clark import section_bodies
from clark.section_kinds import doclinks

OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class FirstBytesEdges(unittest.TestCase):
    def test_every_ending_takes_its_own_signature(self):
        for name, head in (("a.xls", OLE), ("a.ppt", OLE), ("a.jpeg", b"\xff\xd8\xff\xe0"), ("a.docx", b"PK\x05\x06"),
                           ("a.xlsx", b"PK\x05\x06"), ("a.pptx", b"PK\x05\x06"), ("a.txt", b"\xfe\xff\x00a"), ("a.csv", b"\xfe\xff\x00a")):
            with self.subTest(name=name):
                self.assertEqual(doclinks.allowed_content(name, head), name)

    def test_only_the_first_head_bytes_are_read_for_text(self):
        at = doclinks.HEAD_BYTES
        self.assertEqual(at, 512)
        self.assertEqual(doclinks.allowed_content("a.txt", b"x" * at + b"\x00"), "a.txt")       # a zero byte after the head is not read
        with self.assertRaises(section_bodies.Bad):
            doclinks.allowed_content("a.txt", b"x" * (at - 1) + b"\x00")                         # the last byte of the head is read
