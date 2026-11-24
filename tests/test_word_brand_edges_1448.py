"""Row 1448: a DOCTYPE or entity spelled in UTF-16 or split by NUL bytes is refused in every template part, not only word/document.xml and .rels.

Run: python3 dev/run_tests.py test_word_brand_edges_1448      No browser; the templates are made in the test from made-up text.
"""
import random
import re
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

from clark import word_brand
from clark.docx_read import WordRefused
from test_word_brand import BUILT, HEAD, template

EVIL = '<!DOCTYPE r [<!ENTITY e "boom">]><x/>'
ENTITY = "<!ENTITY e 'x'>"
SAME = "could not be read safely, so it was not opened"


def utf16(text):
    return text.encode("utf-16")


def utf16_be(text):
    return text.encode("utf-16-be")


def nul_split(text):
    return b"".join(bytes([c]) + b"\x00" for c in text.encode("ascii"))


def refused(extra):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "brand" / "word" / "template.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(template(extra=extra))
        with unittest.TestCase().assertRaises(WordRefused) as e:
            word_brand.on_template(BUILT, Path(d) / "brand")
    return str(e.exception)


class Hidden(unittest.TestCase):
    def check(self, make, names=("word/other.dat", "customXml/item1")):
        for name in names:
            for bad in (EVIL, ENTITY, "<!doctype r>"):
                with self.subTest(name=name, bad=bad), self.assertRaises(WordRefused) as e:
                    word_brand.wrap(template(extra=[(name, make(HEAD + bad))]), BUILT)
                self.assertIn(SAME, str(e.exception))
                self.assertTrue(str(e.exception).startswith(word_brand.NAME), str(e.exception))

    def test_a_utf16_doctype_in_any_part_is_refused(self):
        self.check(utf16)
        self.check(utf16_be, ("word/other.dat",))
        self.check(utf16, ("zzz.dat", "!first.dat", "word/styles2.XML.bak"))

    def test_a_nul_split_doctype_in_any_part_is_refused(self):
        self.check(nul_split)

    def test_a_doctype_at_the_first_and_last_byte_of_a_hidden_part_is_refused(self):
        for make in (utf16, nul_split):
            with self.subTest(make=make.__name__):
                for body in (EVIL, "<!DOCTYPE"):
                    with self.assertRaises(WordRefused):
                        word_brand.wrap(template(extra=[("word/first.dat", make(body))]), BUILT)

    def test_a_hidden_doctype_after_three_mib_of_prolog_is_refused(self):
        fill = "<!-- " + random.Random(7).randbytes(3 * 1024 * 1024 // 2).hex() + " -->"
        for make in (utf16, nul_split):
            with self.subTest(make=make.__name__), self.assertRaises(WordRefused):
                word_brand.wrap(template(extra=[("word/more.dat", make(HEAD + fill + EVIL))]), BUILT)

    def test_a_clean_utf16_part_still_wraps_and_the_route_refuses_in_plain_words(self):
        clean = HEAD + "<x>a DOCTYPE-free note, <!-- not a declaration --></x>"
        for make in (utf16, nul_split):
            out = word_brand.wrap(template(extra=[("word/other.dat", make(clean))]), BUILT)
            self.assertTrue(out.startswith(b"PK"))
        self.assertIn(SAME, refused([("word/other.dat", utf16(HEAD + EVIL))]))
        self.assertIn(SAME, refused([("word/other.dat", nul_split(HEAD + EVIL))]))

    def test_the_not_covered_note_is_gone(self):
        for rel in ("src/clark/word_brand.py", "tests/test_word_brand_edges.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"not covered|are only caught in word/document", text, re.I), rel)


if __name__ == "__main__":
    unittest.main()
