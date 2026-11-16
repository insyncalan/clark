"""Row 1233, server side of the Image gallery (store type 'gallery', body version 2): the data shape, the checks, the framed copy clark
makes for each image from its original and the framing (the Image template's code), the sizes (1,600 px wide at most, never enlarged), the
order, removal, and what is published (the framed copies only). A body saved by 1.0.7 (version 1) must open and publish unchanged.

Run: python3 dev/run_tests.py test_gallery_v2_server
Fictional data only. No browser.
"""
import json
import random
import unittest

from _pictures import GOOD, GOOD_JPEG, EXIF, data, jpeg
from test_imagecap_full_server import BLUE, RED, decode, halves, make_png, sized_jpeg
from clark import changes, section_bodies, store as store_module
from clark.section_kinds import gallery, imagecap
from clark.section_kinds.base import Bad
from clark.section_kinds.textimage import BAD_SLOT, BIG_PICTURE, CAMERA_DETAILS, NOT_A_PICTURE, NOT_CONTENT, OLD_VERSION, UNKNOWN_FIELD


IMAGE_SLOT = "That image's place isn't in this section. Reload the page and try again."      # BAD_SLOT, said of images


def add(body, slot, image):
    """The body after the image is put in `slot` (the route's step), checked as the store checks it."""
    return gallery.check(gallery.with_picture(body, slot, image), None)


def six(shape=None):
    body = {"v": 2, **({"shape": shape} if shape else {})}
    for n in range(1, 7):
        body = add(body, str(n), halves(8 + n, 6))
    return body


class Shape(unittest.TestCase):
    def test_the_sizes_are_the_ones_the_report_states(self):
        self.assertEqual((gallery.WIDTH_MAX, gallery.FRAMED_MAX, gallery.ORIGINAL_MAX), (1600, 512 * 1024, 1024 * 1024))
        self.assertEqual(gallery.PICTURE_MAX, imagecap.PICTURE_MAX, "the route's one send limit is the Image template's")
        self.assertGreater(gallery.LIMIT, gallery.V1_LIMIT, "a stored 1.0.7 gallery is never refused for size")
        self.assertLess(6 * (gallery.FRAMED_MAX + 2) // 3 * 4, 5 * 1024 * 1024, "six framed copies fit a published report")
        self.assertEqual(gallery.LIMIT, section_bodies.LIMITS["gallery"])
        self.assertEqual(gallery.START, '{"v":2}')

    def test_a_version_2_body_keeps_its_fields_and_leaves_out_the_defaults(self):
        body = gallery.check({"v": 2, "cols": 3, "shape": "whole", "items": {"1": {"caption": " Fictional ", "alt": "A hall", "fx": 500}}}, None)
        self.assertEqual(body, {"v": 2, "items": {"1": {"caption": "Fictional", "alt": "A hall"}}})
        body = gallery.check({"v": 2, "cols": 2, "shape": "square", "items": {"2": {"fx": 100, "fy": 900, "crop": [0, 0, 500, 500]}}}, None)
        self.assertEqual(body, {"v": 2, "cols": 2, "shape": "square", "items": {"2": {"fx": 100, "fy": 900, "crop": [0, 0, 500, 500]}}})
        self.assertEqual(gallery.check({"v": 2}, None), {"v": 2})

    def test_what_is_refused(self):
        for bad, words in (({"v": 2, "cols": 4}, gallery.BAD_LAYOUT), ({"v": 2, "cols": "3"}, gallery.BAD_LAYOUT), ({"v": 2, "cols": True}, gallery.BAD_LAYOUT),
                           ({"v": 2, "shape": "banner"}, gallery.BAD_LAYOUT), ({"v": 2, "order": ["1", "1"]}, gallery.BAD_LAYOUT),
                           ({"v": 2, "order": ["7"]}, gallery.BAD_LAYOUT), ({"v": 2, "order": "12"}, gallery.BAD_LAYOUT),
                           ({"v": 2, "items": {"7": {"caption": "x"}}}, IMAGE_SLOT), ({"v": 2, "items": {"1": "x"}}, NOT_CONTENT),
                           ({"v": 2, "items": {"1": {"href": "https://example.org"}}}, UNKNOWN_FIELD), ({"v": 2, "extra": 1}, UNKNOWN_FIELD),
                           ({"v": 2, "items": {"1": {"fx": 1001}}}, imagecap.BAD_FRAME), ({"v": 2, "items": {"1": {"crop": [0, 0, 5, 500]}}}, imagecap.BAD_FRAME),
                           ({"v": 2, "items": {"1": {"fx": True}}}, imagecap.BAD_FRAME), ({"v": 2, "items": {"1": {"fill": "red"}}}, imagecap.BAD_FRAME),
                           ({"v": 3}, OLD_VERSION), ({"v": 2, "pictures": {"7": GOOD}}, IMAGE_SLOT), ({"v": 2, "pictures": {"1": GOOD_JPEG, "oo1": GOOD}}, IMAGE_SLOT),
                           ({"v": 2, "pictures": {"o1": GOOD}}, imagecap.NOT_ALONE)):
            with self.subTest(bad=bad):
                with self.assertRaises(Bad) as e:
                    gallery.check(bad, None)
                self.assertEqual(str(e.exception), words)

    def test_the_words_are_plain_text_of_a_limited_length(self):
        for bad in ({"v": 2, "items": {"1": {"caption": "x" * 301}}}, {"v": 2, "items": {"1": {"caption": 5}}}):
            with self.assertRaises(Bad):
                gallery.check(bad, None)

    def test_the_store_takes_the_same_body_and_refuses_what_check_refuses(self):
        text = store_module.check_section_body("gallery", json.dumps({"v": 2, "cols": 2, "items": {"1": {"caption": "Fictional"}}}))
        self.assertEqual(json.loads(text), {"v": 2, "cols": 2, "items": {"1": {"caption": "Fictional"}}})
        with self.assertRaises(store_module.Invalid):
            store_module.check_section_body("gallery", json.dumps({"v": 2, "cols": 5}))


class SixImages(unittest.TestCase):
    def test_six_in_six_out_in_order_and_the_seventh_is_refused(self):
        body = six()
        self.assertEqual(sorted(body["pictures"]), ["1", "2", "3", "4", "5", "6"], "no original is kept for a whole image")
        shown = gallery.published(body, None)["content"]["pictures"]
        self.assertEqual([decode(p["image"])[0] for p in shown], [9, 10, 11, 12, 13, 14])
        with self.assertRaises(Bad) as e:
            gallery.with_picture(body, "7", halves(8, 6))
        self.assertEqual(str(e.exception), IMAGE_SLOT, "image, never picture")
        self.assertEqual(BAD_SLOT.replace("picture", "image"), IMAGE_SLOT)
        for slot in ("0", "o1", "", 1, None):
            with self.assertRaises(Bad):
                gallery.with_picture(body, slot, halves(8, 6))

    def test_an_image_is_framed_by_clark_and_never_taken_from_a_request(self):
        got = gallery.check({"v": 2, "shape": "square", "pictures": {"1": halves(40, 10)}}, None)      # a "framed copy" sent in is not trusted
        self.assertEqual(decode(got["pictures"]["1"])[:2], (10, 10))
        self.assertEqual(got["pictures"]["o1"], halves(40, 10), "the sent image is kept as the original")

    def test_a_jpeg_and_a_png_with_camera_details_are_refused_as_for_every_picture(self):
        for bad, words in ((EXIF, CAMERA_DETAILS), (data(b"nope", "png"), NOT_A_PICTURE)):
            with self.assertRaises(Bad) as e:
                gallery.with_picture({"v": 2}, "1", bad)
            self.assertIn("image", str(e.exception))
            self.assertNotIn("picture", str(e.exception).replace("Pictures", ""))
        self.assertIn("image", str(CAMERA_DETAILS.replace("picture", "image")))


class Sizes(unittest.TestCase):
    def test_a_very_large_image_becomes_1600_wide_and_a_small_one_is_not_enlarged(self):
        body = add({"v": 2}, "1", make_png(2400, 8, lambda x, y: RED if x < 1200 else BLUE))
        w, h, rows = decode(body["pictures"]["1"])
        self.assertEqual((w, h), (1600, 5))
        self.assertEqual(body["items"]["1"]["from_w"], 2400)
        self.assertEqual((rows[0][0], rows[0][-1]), (RED, BLUE))
        self.assertNotIn("o1", body["pictures"], "the shrunk image is its own original")
        small = add({"v": 2}, "2", halves(30, 20))
        self.assertEqual(decode(small["pictures"]["2"])[:2], (30, 20))
        self.assertNotIn("items", small)

    def test_the_original_is_the_shrunk_image_so_a_crop_decodes_to_the_framed_part_only(self):
        body = add({"v": 2}, "1", make_png(2400, 8, lambda x, y: RED if x < 1200 else BLUE))
        body["items"]["1"]["crop"] = [500, 0, 1000, 1000]
        out = gallery.check(body, None)
        w, h, rows = decode(out["pictures"]["1"])
        self.assertEqual(w, 800)
        self.assertEqual({px for row in rows for px in row}, {BLUE})
        self.assertEqual(decode(out["pictures"]["o1"])[0], 1600, "the original is kept so Reset works")

    def test_a_jpeg_wider_than_1600_is_refused_in_words_and_a_png_cut_is_asked_for(self):
        with self.assertRaises(Bad) as e:
            gallery.with_picture({"v": 2}, "1", sized_jpeg(2000))
        self.assertEqual(str(e.exception), gallery.TOO_WIDE)
        body = add({"v": 2}, "1", sized_jpeg(800))
        self.assertEqual(body["pictures"], {"1": sized_jpeg(800)})
        with self.assertRaises(Bad) as e:
            gallery.with_picture({"v": 2, "shape": "square"}, "1", sized_jpeg(800))
        self.assertEqual(str(e.exception), imagecap.CANT_FRAME.replace("picture", "image"))

    def test_a_framed_copy_over_its_limit_is_refused(self):
        noise = random.Random(1)
        noise = make_png(500, 500, lambda x, y: (noise.randrange(256), noise.randrange(256), noise.randrange(256)))
        with self.assertRaises(Bad) as e:
            gallery.with_picture({"v": 2, "shape": "square"}, "1", noise)
        self.assertEqual(str(e.exception), imagecap.STILL_BIG)


class Framing(unittest.TestCase):
    def test_each_image_has_its_own_focus_and_changing_the_shape_keeps_it(self):
        body = add({"v": 2, "shape": "16:9"}, "1", halves(100, 20))
        body = add(body, "2", halves(100, 20))
        body["items"] = {"1": {"fx": 0}, "2": {"fx": 1000}}
        body = gallery.check(body, None)
        one, two = decode(body["pictures"]["1"]), decode(body["pictures"]["2"])
        self.assertEqual({px for row in one[2] for px in row}, {RED})
        self.assertEqual({px for row in two[2] for px in row}, {BLUE})
        body["shape"] = "square"
        body = gallery.check(body, None)
        self.assertEqual(body["items"], {"1": {"fx": 0}, "2": {"fx": 1000}}, "the focus is kept")
        one, two = decode(body["pictures"]["1"]), decode(body["pictures"]["2"])
        self.assertEqual(one[:2], (20, 20))
        self.assertEqual({px for row in one[2] for px in row}, {RED})
        self.assertEqual({px for row in two[2] for px in row}, {BLUE})

    def test_reset_restores_the_whole_image_from_the_kept_original(self):
        body = add({"v": 2, "shape": "square"}, "1", halves(40, 10))
        self.assertEqual(decode(body["pictures"]["1"])[:2], (10, 10))
        body["shape"] = "whole"
        body.pop("shape")
        back = gallery.check(body, None)
        self.assertEqual(back["pictures"]["1"], halves(40, 10))
        self.assertNotIn("o1", back["pictures"], "one copy of the same image is kept")

    def test_the_published_file_carries_each_image_as_framed(self):
        body = add({"v": 2}, "1", halves(40, 10))
        body["items"] = {"1": {"crop": [500, 0, 1000, 1000], "caption": "Fictional"}}
        body = gallery.check(body, None)
        out = gallery.published(body, None)
        self.assertEqual(out, {"content": {"pictures": [{"image": body["pictures"]["1"], "caption": "Fictional", "alt": ""}], "cols": 3, "shape": "whole"}})
        w, h, rows = decode(out["content"]["pictures"][0]["image"])
        self.assertEqual((w, {px for row in rows for px in row}), (20, {BLUE}))
        self.assertNotIn(body["pictures"]["o1"], repr(out))

    def test_a_framed_copy_that_does_not_belong_is_never_published(self):
        body = add({"v": 2, "shape": "square"}, "1", halves(40, 10))
        body["pictures"]["1"] = add({"v": 2, "shape": "square"}, "1", halves(40, 12))["pictures"]["1"]      # some other framed image
        self.assertIsNone(gallery.published(body, None))
        body["shape"] = "4:3"
        self.assertIsNone(gallery.published(add({"v": 2, "shape": "square"}, "1", halves(40, 10)) | {"shape": "4:3"}, None))

    def test_a_new_image_in_a_used_slot_starts_unframed_and_keeps_the_words(self):
        body = add({"v": 2}, "1", halves(40, 10))
        body["items"] = {"1": {"caption": "Fictional", "alt": "A hall", "fx": 100, "crop": [0, 0, 500, 1000]}}
        body = gallery.check(body, None)
        body = add(body, "1", halves(20, 10))
        self.assertEqual(body["items"], {"1": {"caption": "Fictional", "alt": "A hall"}})
        self.assertEqual(decode(body["pictures"]["1"])[:2], (20, 10))
        self.assertNotIn("o1", body["pictures"])


class Remove(unittest.TestCase):
    def test_removing_takes_the_words_framing_and_original_with_it(self):
        body = add({"v": 2, "shape": "square"}, "2", halves(40, 10))
        body["items"] = {"2": {"caption": "Fictional", "alt": "A hall", "fx": 100}}
        body["order"] = ["2"]
        body = gallery.check(body, None)
        self.assertIn("o2", body["pictures"])
        out = gallery.check(gallery.with_picture(body, "2", None), None)
        self.assertEqual(out, {"v": 2, "shape": "square"}, "nothing of it is left in the stored body")
        self.assertNotIn("Fictional", json.dumps(out))

    def test_the_last_removed_leaves_an_empty_gallery_that_is_not_published(self):
        body = add({"v": 2}, "1", halves(8, 6))
        out = gallery.check(gallery.with_picture(body, "1", None), None)
        self.assertEqual(out, {"v": 2})
        self.assertIsNone(gallery.published(out, None))

    def test_the_others_keep_their_words_and_the_order_without_it(self):
        body = six()
        body["items"] = {"1": {"caption": "One"}, "3": {"caption": "Three"}}
        body["order"] = ["3", "1", "2", "4", "5", "6"]
        body = gallery.check(body, None)
        out = gallery.check(gallery.with_picture(body, "1", None), None)
        self.assertEqual(out["items"], {"3": {"caption": "Three"}})
        self.assertEqual(out["order"], ["3", "1", "2", "4", "5", "6"], "the order is of slots; an empty one is skipped")
        self.assertEqual([p["caption"] for p in gallery.published(out, None)["content"]["pictures"]][:2], ["Three", ""])


class Order(unittest.TestCase):
    def test_the_order_moves_the_image_and_its_words_together_and_the_plain_order_is_not_stored(self):
        body = six()
        body["items"] = {"1": {"caption": "One", "alt": "First", "fx": 10}, "2": {"caption": "Two"}}
        body["order"] = ["2", "1"]
        body = gallery.check(body, None)
        self.assertEqual(body["order"], ["2", "1", "3", "4", "5", "6"])
        shown = gallery.published(body, None)["content"]["pictures"]
        self.assertEqual([(p["caption"], decode(p["image"])[0]) for p in shown][:2], [("Two", 10), ("One", 9)])
        self.assertEqual(shown[1]["alt"], "First")
        body["order"] = ["1", "2", "3", "4", "5", "6"]
        self.assertNotIn("order", gallery.check(body, None))

    def test_an_order_names_all_six_slots_and_an_empty_one_is_skipped_in_view(self):
        body = add(add({"v": 2}, "2", halves(8, 6)), "5", halves(9, 6))
        body["order"] = ["5"]
        body = gallery.check(body, None)
        self.assertEqual(body["order"], ["5", "1", "2", "3", "4", "6"])
        self.assertEqual([decode(p["image"])[0] for p in gallery.published(body, None)["content"]["pictures"]], [9, 8])


class Columns(unittest.TestCase):
    def test_columns_and_shape_are_published_for_the_page_to_draw(self):
        body = gallery.check({**six("square"), "cols": 2}, None)
        content = gallery.published(body, None)["content"]
        self.assertEqual((content["cols"], content["shape"], len(content["pictures"])), (2, "square", 6))
        self.assertEqual(gallery.published(six(), None)["content"]["cols"], 3)


class Version1Stays(unittest.TestCase):
    OLD = {"v": 1, "items": {"1": {"caption": "Fictional one", "alt": "A room"}, "2": {"caption": "Two"}}, "pictures": {"1": GOOD, "2": GOOD_JPEG}}

    def test_a_1_0_7_gallery_checks_and_publishes_as_before(self):
        self.assertEqual(gallery.check(self.OLD, None), self.OLD)
        self.assertEqual(gallery.published(self.OLD, None), {"content": {"pictures": [
            {"image": GOOD, "caption": "Fictional one", "alt": "A room"}, {"image": GOOD_JPEG, "caption": "Two", "alt": ""}]}})
        self.assertIsNone(gallery.published({"v": 1, "items": {"1": {"caption": "x"}}}, None))
        for bad in ({"v": 1, "cols": 2}, {"v": 1, "order": ["1"]}, {"v": 1, "items": {"1": {"fx": 5}}}, {"v": 1, "pictures": {"o1": GOOD}}):
            with self.assertRaises(Bad):
                gallery.check(bad, None)

    def test_version_1_pictures_are_still_held_to_400_kb_and_a_valid_old_one_is_never_refused(self):
        big = data(jpeg(pad=gallery.V1_PICTURE_MAX), "jpeg")
        with self.assertRaises(Bad) as e:
            gallery.check({"v": 1, "pictures": {"1": big}}, None)
        self.assertEqual(str(e.exception), BIG_PICTURE)
        with self.assertRaises(Bad):
            gallery.with_picture({"v": 1}, "1", big)
        ok = data(jpeg(pad=gallery.V1_PICTURE_MAX - 400), "jpeg")
        body = {"v": 1, "pictures": {str(n): ok for n in range(1, 7)}}
        self.assertEqual(gallery.check(body, None), body)
        self.assertLessEqual(len(json.dumps(body)), gallery.V1_LIMIT, "six old pictures fit the old limit")
        json.loads(store_module.check_section_body("gallery", json.dumps(body)))      # the store takes it too

    def test_a_first_picture_still_starts_a_version_1_body_and_removing_one_takes_its_words(self):
        body = gallery.with_picture(None, "1", GOOD)
        self.assertEqual(body, {"v": 1, "pictures": {"1": GOOD}})
        body = gallery.check({"v": 1, "items": {"1": {"caption": "x"}}, "pictures": {"1": GOOD}}, None)
        self.assertEqual(gallery.with_picture(body, "1", None), {"v": 1})

    def test_the_words_alone_upgrade_it_and_keep_every_image_caption_and_description(self):
        upgraded = {"v": 2, "items": self.OLD["items"], "pictures": self.OLD["pictures"]}
        got = gallery.check(upgraded, None)
        self.assertEqual(got, upgraded, "no shape, so each image is as stored and the page draws it 4:3 as 1.0.7 did")
        shown = gallery.published(got, None)["content"]
        self.assertEqual([(p["image"], p["caption"], p["alt"]) for p in shown["pictures"]], [(GOOD, "Fictional one", "A room"), (GOOD_JPEG, "Two", "")])
        cut = gallery.check({"v": 2, "pictures": {"1": GOOD}, "shape": "4:3"}, None)
        self.assertEqual(cut["pictures"]["o1"], GOOD, "a shape chosen later keeps the old image as the original")


class ThroughTheRoute(unittest.TestCase):
    def test_the_words_route_keeps_the_pictures_and_order_moves_with_the_words(self):
        section = {"type": "gallery", "body": json.dumps(six("square"), separators=(",", ":"))}
        words = json.dumps({"v": 2, "shape": "square", "order": ["2", "1"], "items": {"1": {"caption": "One"}}})
        out = json.loads(changes._keep_pictures(section, words))
        self.assertEqual(out["order"], ["2", "1", "3", "4", "5", "6"])
        self.assertEqual(out["items"], {"1": {"caption": "One"}})
        self.assertEqual(out["pictures"], json.loads(section["body"])["pictures"], "every image and original kept as stored")
        with self.assertRaises(changes.Refused):
            changes._keep_pictures(section, json.dumps({"v": 2, "pictures": {"1": GOOD}}))


if __name__ == "__main__":
    unittest.main()
