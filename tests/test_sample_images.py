"""Row 1251: the sample picture is drawn by clark, the same every time, a clean PNG within the image limits, and accepted by the
Image with caption and Full width image checks. Run: python3 dev/run_tests.py test_sample_images (no browser). Fictional data only.
"""
import struct
import unittest
import zlib

from _pictures import data
from clark import sample_images
from clark.section_kinds import imagecap, textimage


class Sample(unittest.TestCase):
    def test_a_clean_png_of_the_stated_size(self):
        raw = sample_images.sample_png()
        self.assertEqual(imagecap.png_size(raw), (sample_images.SAMPLE_WIDTH, sample_images.SAMPLE_HEIGHT))
        self.assertEqual({k for k, _ in imagecap._chunks(raw)}, {b"IHDR", b"IDAT", b"IEND"})

    def test_the_same_bytes_every_time(self):
        self.assertEqual(sample_images.sample_png(), sample_images.sample_png())

    def test_small_enough_to_ship(self):
        self.assertLess(len(sample_images.sample_png()), 200 * 1024)
        self.assertLess(len(sample_images.sample_png()), textimage.PICTURE_MAX)

    def test_the_image_template_accepts_it(self):
        got = imagecap.check({"v": 2, "pictures": {"original": data(sample_images.sample_png())}}, {})
        self.assertIn("original", got["pictures"])

    def test_exact_size_and_header(self):
        raw = sample_images.sample_png()
        self.assertEqual((sample_images.SAMPLE_WIDTH, sample_images.SAMPLE_HEIGHT), (1200, 675))
        self.assertEqual(raw[16:29], struct.pack(">IIBBBBB", 1200, 675, 8, 2, 0, 0, 0))

    def test_every_chunk_crc_and_rows_are_unfiltered_rgb(self):
        raw, pos, idat = sample_images.sample_png(), 8, b""
        while pos < len(raw):
            n, kind = struct.unpack(">I4s", raw[pos:pos + 8])
            body = raw[pos + 8:pos + 8 + n]
            self.assertEqual(struct.unpack(">I", raw[pos + 8 + n:pos + 12 + n])[0], zlib.crc32(kind + body) & 0xFFFFFFFF)
            idat += body if kind == b"IDAT" else b""
            pos += 12 + n
        rows = zlib.decompress(idat)
        stride = 1 + 3 * 1200
        self.assertEqual(len(rows), stride * 675)
        self.assertEqual({rows[i * stride] for i in range(675)}, {0})

    def test_the_picture_has_its_sun_and_sky(self):
        rows = zlib.decompress(b"".join(
            raw for raw in [self._idat(sample_images.sample_png())]))
        def px(x, y):
            o = y * (1 + 3 * 1200) + 1 + 3 * x
            return tuple(rows[o:o + 3])
        self.assertEqual(px(936, 175), (246, 226, 168))
        self.assertEqual(px(10, 0), (176, 205, 232))

    @staticmethod
    def _idat(raw):
        pos, out = 8, b""
        while pos < len(raw):
            n, kind = struct.unpack(">I4s", raw[pos:pos + 8])
            out += raw[pos + 8:pos + 8 + n] if kind == b"IDAT" else b""
            pos += 12 + n
        return out


if __name__ == "__main__":
    unittest.main()
