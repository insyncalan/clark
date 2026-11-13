"""#1355: tests/_backdrop_pics.decode reads every PNG row filter back correctly (None, Sub, Up, Average, Paeth), for RGB and RGBA.

Run: python3 dev/run_tests.py test_backdrop_pics   (quick tier, no browser)

The backdrop tests read Chrome screenshots with decode(), and a filter it gets wrong shifts a pixel and so a contrast figure; the
faster decode of #1355 has its own code for each filter. Here each row is filtered by an independent, plain encoder and read back.
"""
import random
import struct
import unittest
import zlib

import _backdrop_pics as pics


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _filtered(row, prev, f, bpp):
    out = bytearray()
    for i, x in enumerate(row):
        a = row[i - bpp] if i >= bpp else 0
        b = prev[i]
        c = prev[i - bpp] if i >= bpp else 0
        pred = (0, a, b, (a + b) >> 1, _paeth(a, b, c))[f]
        out.append((x - pred) & 255)
    return bytes([f]) + bytes(out)


def _png(rows, bpp, filters):
    w, h = len(rows[0]) // bpp, len(rows)
    raw, prev = b"", bytes(len(rows[0]))
    for row, f in zip(rows, filters):
        raw += _filtered(row, prev, f, bpp)
        prev = row
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2 if bpp == 3 else 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + pics._chunk(b"IHDR", ihdr) + pics._chunk(b"IDAT", zlib.compress(raw)) + pics._chunk(b"IEND", b"")


class DecodeFilters(unittest.TestCase):
    def test_each_row_filter_reads_back_the_pixels_it_was_made_from(self):
        rng = random.Random(1355)
        for bpp in (3, 4):
            for f in range(5):
                with self.subTest(bpp=bpp, filter=f):
                    rows = [bytes(rng.randrange(256) for _ in range(7 * bpp)) for _ in range(5)]
                    w, h, px = pics.decode(_png(rows, bpp, [f] * 5))
                    self.assertEqual((w, h), (7, 5))
                    want = [[tuple(r[x * bpp:x * bpp + 3]) for x in range(7)] for r in rows]
                    self.assertEqual(px, want)

    def test_a_mix_of_filters_down_the_picture(self):
        rng = random.Random(7)
        rows = [bytes(rng.randrange(256) for _ in range(9 * 3)) for _ in range(10)]
        w, h, px = pics.decode(_png(rows, 3, [0, 1, 2, 3, 4, 4, 3, 2, 1, 0]))
        self.assertEqual(px, [[tuple(r[x * 3:x * 3 + 3]) for x in range(9)] for r in rows])


if __name__ == "__main__":
    unittest.main()
