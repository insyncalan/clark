"""Row 1232: the Word export of Text and Image Side by Side (a textimage section, an older Text and image section reads the same). The section
heading, the words, the framed image with its caption (small ones at their own size) and the section is left out when it has neither words nor
image. Fictional data only. Run: python3 dev/run_tests.py test_docx_textimage_1232"""
import base64
import io
import re
import struct
import unittest
import zipfile
import zlib

from clark import docx_build


def png(w, h):
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
    row = b"\x00" + bytes((200, 30, 30)) * w
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(row * h)) + chunk(b"IEND", b"")


def uri(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def word(content, title="Site visit"):
    pub = {"as_at": "2026-11-15", "data": {"project": {"code": "FIC", "name": "Fictional project"}, "actions": [], "raid": [], "decisions": [],
                                           "milestones": [], "use_cases": [], "documents": []},
           "sections": [{"id": "FIC-S-001", "type": "textimage", "title": title, "beside": 0, "content": content}], "tabs": ["dashboard"]}
    z = zipfile.ZipFile(io.BytesIO(docx_build.build(pub)))
    return z.read("word/document.xml").decode(), z.namelist()


class Word(unittest.TestCase):
    def test_a_version_2_section_carries_its_words_the_framed_image_and_the_caption(self):
        doc, names = word({"v": 2, "html": "<p>Fictional words about the visit.</p>", "image": uri(png(1200, 600)), "caption": "Fictional caption", "alt": "Fictional alt"})
        self.assertIn("Fictional words about the visit.", doc)
        self.assertIn("Fictional caption", doc)
        self.assertIn("Site visit", doc)
        self.assertEqual(len([n for n in names if n.startswith("word/media/")]), 1)

    def test_an_old_text_and_image_section_opens_the_same_words_image_caption_and_description(self):
        doc, names = word({"words": ["Fictional old words"], "side": "left", "image": uri(png(300, 200)), "caption": "Fictional old caption", "alt": "Fictional old alt"})
        self.assertIn("Fictional old words", doc)
        self.assertIn("Fictional old caption", doc)
        self.assertIn("Fictional old alt", doc)
        self.assertEqual(len([n for n in names if n.startswith("word/media/")]), 1)
        self.assertLess(doc.index("<w:drawing"), doc.index("Fictional old words"), "on the left: the image first")

    def test_on_the_right_the_image_comes_after_the_words(self):
        doc, _ = word({"v": 2, "html": "<p>Fictional right words</p>", "image": uri(png(300, 200))})
        self.assertLess(doc.index("Fictional right words"), doc.index("<w:drawing"))

    def test_a_small_image_is_not_enlarged(self):
        doc, _ = word({"v": 2, "html": "<p>x</p>", "image": uri(png(150, 100))})
        self.assertEqual(int(re.search(r'<wp:extent cx="(\d+)"', doc).group(1)), 150 * 15 * 635)

    def test_words_alone_show_and_neither_leaves_the_section_out(self):
        doc, names = word({"v": 2, "html": "<p>Fictional words only</p>"})
        self.assertIn("Fictional words only", doc)
        self.assertFalse([n for n in names if n.startswith("word/media/")])
        doc, _ = word({"v": 2, "heading": "Only a heading"})
        self.assertNotIn("Site visit", doc)

    def test_the_own_heading_line_is_written_under_the_section_heading_before_the_words(self):
        doc, _ = word({"v": 2, "heading": "Fictional own heading", "html": "<p>Fictional body words</p>"})
        self.assertIn("Fictional own heading", doc)
        self.assertLess(doc.index("Site visit"), doc.index("Fictional own heading"))
        self.assertLess(doc.index("Fictional own heading"), doc.index("Fictional body words"))
        self.assertIn('w:val="Heading2"', doc)
        doc, _ = word({"v": 2, "html": "<p>Fictional body words</p>"})
        self.assertNotIn('w:val="Heading2"', doc)

    def _picture_paragraph(self, doc):
        return next(p for p in re.findall(r"<w:p>.*?</w:p>|<w:p [^>]*>.*?</w:p>", doc, re.S) if "<w:drawing" in p)

    def test_the_picture_keeps_with_its_caption_and_stands_alone_without_one(self):
        doc, _ = word({"v": 2, "html": "<p>x</p>", "image": uri(png(300, 200)), "caption": "Fictional caption"})
        self.assertIn("<w:keepNext/>", self._picture_paragraph(doc), "the image stays on the page with its caption")
        doc, _ = word({"v": 2, "html": "<p>x</p>", "image": uri(png(300, 200))})
        self.assertNotIn("<w:keepNext/>", self._picture_paragraph(doc))

    def test_a_small_image_is_centred_and_a_large_one_is_not(self):
        doc, _ = word({"v": 2, "html": "<p>x</p>", "image": uri(png(150, 100))})
        self.assertIn('<w:jc w:val="center"/>', self._picture_paragraph(doc))
        doc, _ = word({"v": 2, "html": "<p>x</p>", "image": uri(png(1200, 600))})
        self.assertNotIn("<w:jc ", self._picture_paragraph(doc))


if __name__ == "__main__":
    unittest.main()
