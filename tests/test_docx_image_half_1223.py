"""Row 1223 (test 13 and 10): the Image section (an imagecap section of version 2) in the Word report, whether it is half or full width on the page.

Run: python3 dev/run_tests.py test_docx_image_half_1223
Word has one column: a half width Image (beside the next section) is drawn as wide as the text, exactly like a full width one; a small
image still sits centred at its own size; the file carries the framed copy, and a section with no image is not in the report. Made-up data only."""
import base64
import copy
import io
import re
import struct
import unittest
import zipfile
import zlib

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

import _publish_fixture as fx
from clark import docx_build, publish

EMU_TWIP = 635          # one twentieth of a point is 635 EMU


def png(w, h):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + b"\x28\xa0\x3c" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def uri(w, h):
    return "data:image/png;base64," + base64.b64encode(png(w, h)).decode()


def report(beside, w, h, **more):
    p = publish.select(fx.inputs())
    content = {"image": uri(w, h), "caption": "", "alt": "A made-up plan", "full": 1, **more}
    p["sections"].append({"id": "s-img", "type": "imagecap", "title": "Image", "beside": beside, "content": content})
    return docx_build.build(p)


def drawn(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    doc = z.read("word/document.xml").decode("utf-8")
    sizes = [(int(a), int(b)) for a, b in re.findall(r'<wp:extent cx="(\d+)" cy="(\d+)"', doc)]
    media = [n for n in z.namelist() if n.startswith("word/media/")]
    return sizes, media, doc, z


def mine(data):
    """The drawings the Image adds: the report's own drawings are taken away."""
    base = list(drawn(docx_build.build(publish.select(fx.inputs())))[0])
    out = list(drawn(data)[0])
    for s in base:
        out.remove(s)
    return out


class Half(unittest.TestCase):
    def test_a_half_width_image_is_as_wide_as_the_text_like_a_full_one(self):
        full = mine(report(0, 3000, 1000))
        half = mine(report(1, 3000, 1000))
        self.assertEqual(half, full, "Word has one column: beside or not, the same drawing")
        self.assertEqual(len(full), 1)
        self.assertEqual(full[0][0], docx_build.TEXT_W * EMU_TWIP)

    def test_a_small_half_width_image_sits_at_its_own_size_and_a_stretched_one_fills(self):
        small = mine(report(1, 600, 300))
        self.assertEqual(small[0][0], 600 * 15 * EMU_TWIP)
        stretched = mine(report(1, 600, 300, fit="stretch"))
        self.assertEqual(stretched[0][0], docx_build.TEXT_W * EMU_TWIP)

    def test_the_file_carries_the_framed_image_whole_and_a_caption_when_there_is_one(self):
        sizes, media, doc, z = drawn(report(1, 1200, 400, caption="Fictional caption"))
        mine = [n for n in media if z.read(n)[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", z.read(n)[16:24]) == (1200, 400)]
        self.assertEqual(len(mine), 1, "the framed copy, at its own pixel size, once")
        self.assertIn("Fictional caption", doc)
        self.assertNotIn("Fictional caption", drawn(report(1, 1200, 400))[2])

    def test_no_image_leaves_the_section_out_beside_or_not(self):
        for beside in (0, 1):
            p = publish.select(fx.inputs())
            p["sections"].append({"id": "s-img", "type": "imagecap", "title": "Image", "beside": beside, "content": {"image": "", "full": 1}})
            self.assertEqual(mine(docx_build.build(p)), [])


if __name__ == "__main__":
    unittest.main()
