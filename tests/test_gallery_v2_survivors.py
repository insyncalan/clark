"""Row 1233, the gallery's server join: tests that pin the edges a mutation sweep found open: the version check, a stored framed copy over its
size, the 1,600 px edge, a JPEG or WebP whose size can't be read, the size of a sent original, the order kept while words remain, what a
version 2 body publishes of an image's fit and fill, a published body that can't be read, and that the Edit page asks for no more than a
version 1 body takes.

Run: python3 dev/run_tests.py test_gallery_v2_survivors
Fictional data only. No browser.
"""
import random
import re
import struct
import unittest
from pathlib import Path

from _pictures import data
from test_imagecap_full_server import RED, BLUE, halves, make_png
from clark import server
from clark.section_kinds import gallery, imagecap
from clark.section_kinds.base import Bad
from clark.section_kinds.textimage import BIG_PICTURE, NOT_A_PICTURE, NOT_CONTENT, OLD_VERSION

WHOLE = {"v": 2, "shape": "whole"}
ROOT = Path(__file__).resolve().parent.parent


def noise(w, h, seed):
    r = random.Random(seed)
    return make_png(w, h, lambda x, y: (r.randrange(256), r.randrange(256), r.randrange(256)))


class Version(unittest.TestCase):
    def test_only_1_and_2_are_versions(self):
        for v in (0, 3, 4, 99, -1):
            with self.subTest(v=v):
                for body in ({"v": v}, {"v": v, "items": {"1": {"caption": "x"}}}):
                    with self.assertRaises(Bad) as e:
                        gallery.check(body, None)
                    self.assertEqual(str(e.exception), OLD_VERSION)
        self.assertEqual(gallery.check({}, None), {"v": 1})
        self.assertEqual(gallery.check({"v": 1}, None), {"v": 1})

    def test_a_version_that_is_not_a_whole_number_is_not_content(self):
        for v in ("2", "1", 2.0, 1.0, True, False, None, [2]):
            with self.subTest(v=v):
                with self.assertRaises(Bad) as e:
                    gallery.check({"v": v}, None)
                self.assertEqual(str(e.exception), NOT_CONTENT)


class StoredCopy(unittest.TestCase):
    def test_a_stored_framed_copy_that_is_ours_but_over_its_limit_is_refused(self):
        source = noise(500, 500, 3)
        numbers = gallery._numbers({}, "square", source)
        big = imagecap._make_framed(source, numbers, gallery.WIDTH_MAX, 4 * 1024 * 1024)      # made with a larger limit: it belongs, and is too large
        self.assertGreater(len(imagecap._decode_data(big)[1]), gallery.FRAMED_MAX)
        self.assertTrue(imagecap._framed_belongs(source, big, numbers))
        with self.assertRaises(Bad) as e:
            gallery.check({"v": 2, "shape": "square", "pictures": {"1": big, "o1": source}}, None)
        self.assertEqual(str(e.exception), imagecap.STILL_BIG)


class Edges(unittest.TestCase):
    def test_a_png_1600_wide_is_kept_and_1601_is_made_smaller(self):
        exact = make_png(1600, 1, lambda x, y: RED)
        body = gallery.with_picture(WHOLE, "1", exact)
        self.assertEqual(body["pictures"], {"1": exact})
        self.assertNotIn("items", body, "nothing was made smaller")
        wide = make_png(1601, 1, lambda x, y: RED)
        body = gallery.with_picture(WHOLE, "1", wide)
        self.assertEqual(body["items"], {"1": {"from_w": 1601}})
        self.assertEqual(imagecap.png_size(imagecap._decode_data(body["pictures"]["1"])[1]), (1600, 1))

    def test_a_jpeg_or_webp_whose_size_can_not_be_read_is_refused_in_words(self):
        jpeg = data(b"\xff\xd8\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\xff\xd9", "jpeg")
        webp = data(b"RIFF" + struct.pack("<I", 40) + b"WEBPVP8Z" + b"\x00" * 30, "webp")
        for bad in (jpeg, webp):
            with self.subTest(kind=bad[:20]):
                with self.assertRaises(Bad) as e:
                    gallery.with_picture(WHOLE, "1", bad)
                self.assertEqual(str(e.exception), NOT_A_PICTURE.replace("picture", "image"))

    def test_an_original_over_1_mib_is_refused_as_too_large_before_it_is_framed(self):
        big = noise(600, 600, 4)
        self.assertGreater(len(imagecap._decode_data(big)[1]), gallery.ORIGINAL_MAX)
        self.assertLess(len(imagecap._decode_data(big)[1]), gallery.PICTURE_MAX)
        with self.assertRaises(Bad) as e:
            gallery.with_picture(WHOLE, "1", big)
        self.assertEqual(str(e.exception), imagecap._say_image(BIG_PICTURE))


class Words(unittest.TestCase):
    def test_taking_an_image_out_keeps_the_order_while_other_words_stay(self):
        body = gallery.with_picture(WHOLE, "1", halves(8, 6))
        body["items"] = {"3": {"caption": "Three"}}
        body["order"] = ["3", "1", "2", "4", "5", "6"]
        out = gallery.with_picture(body, "1", None)
        self.assertNotIn("pictures", out)
        self.assertEqual(out["order"], body["order"])
        self.assertEqual(gallery.check(out, None)["order"], body["order"])

    def test_the_last_image_and_words_gone_leaves_no_order(self):
        body = gallery.with_picture(WHOLE, "1", halves(8, 6))
        body["order"] = ["2", "1", "3", "4", "5", "6"]
        self.assertNotIn("order", gallery.with_picture(body, "1", None))

    def test_fit_and_fill_are_published_with_the_image(self):
        body = gallery.with_picture(WHOLE, "1", halves(8, 6))
        body["items"] = {"1": {"fit": "stretch", "fill": "brand", "caption": "Fictional"}}
        body = gallery.check(body, None)
        shown = gallery.published(body, None)["content"]["pictures"][0]
        self.assertEqual((shown["fit"], shown["fill"]), ("stretch", "brand"))
        body["items"] = {"1": {"fill": "plain"}}
        shown = gallery.published(gallery.check(body, None), None)["content"]["pictures"][0]
        self.assertEqual((shown.get("fit"), shown["fill"]), (None, "plain"))
        body["items"] = {"1": {"fit": "centre"}}
        shown = gallery.published(gallery.check(body, None), None)["content"]["pictures"][0]
        self.assertEqual((shown.get("fit"), shown.get("fill")), (None, None), "the default fit is not stored")

    def test_a_stored_image_that_can_not_be_read_is_not_published_and_does_not_fail(self):
        for text in ("data:image/png;base64,AAAAA", "data:image/png;base64,A"):
            with self.subTest(text=text):
                self.assertIsNone(gallery.published({"v": 2, "pictures": {"1": text}}, None))
                self.assertIsNone(gallery.published({"v": 2, "shape": "square", "pictures": {"1": text, "o1": text}}, None))


class EditPage(unittest.TestCase):
    def test_the_edit_page_asks_for_no_more_than_a_version_1_body_takes(self):
        text = (ROOT / "src/clark/page/src/edit/templates/Gallery.jsx").read_text(encoding="utf-8")
        most = re.search(r"export const MOST = (\d+) \* 1024;", text)
        self.assertTrue(most, "MOST is one number of KiB")
        self.assertEqual(int(most.group(1)) * 1024, gallery.V1_PICTURE_MAX, "Edit still sends version 1 bodies, so a picture over this is refused by the server")
        with self.assertRaises(Bad):
            gallery.with_picture({"v": 1}, "1", data(b"\xff\xd8\xff\xe0" + b"\x00" * (gallery.V1_PICTURE_MAX + 1), "jpeg"))


if __name__ == "__main__":
    unittest.main()
