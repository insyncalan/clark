"""Row 1251: the sample picture is drawn by clark, the same every time, a clean PNG within the image limits, and accepted by the
Image with caption and Full width image checks. Run: python3 dev/run_tests.py test_sample_images (no browser). Fictional data only.
"""
import unittest

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


if __name__ == "__main__":
    unittest.main()
