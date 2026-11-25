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
from clark import changes, section_bodies, server, store as store_module
from clark.section_kinds import gallery, imagecap
from clark.section_kinds.base import Bad
from clark.section_kinds.textimage import BAD_SIDE, BAD_SLOT, BIG_PICTURE, CAMERA_DETAILS, NOT_A_PICTURE, NOT_CONTENT, OLD_VERSION, UNKNOWN_FIELD


IMAGE_SLOT = "That image's place isn't in this section. Reload the page and try again."      # BAD_SLOT, said of images


WHOLE = {"v": 2, "shape": "whole"}      # the shape that leaves every image as it is (never the default)


def add(body, slot, image):
    """The body after the image is put in `slot` (the route's step), checked as the store checks it."""
    return gallery.check(gallery.with_picture(body, slot, image), None)


def six(shape="whole"):
    body = {"v": 2, "shape": shape}
    for n in range(1, 7):
        body = add(body, str(n), halves(8 + n, 6))
    return body


class Shape(unittest.TestCase):
    def test_the_sizes_are_the_ones_the_report_states(self):
        self.assertEqual((gallery.WIDTH_MAX, gallery.FRAMED_MAX, gallery.ORIGINAL_MAX), (1600, 512 * 1024, 1024 * 1024))
        self.assertEqual(gallery.PICTURE_MAX, 10 * 1024 * 1024, "a person may add a picture up to 10 MB")
        self.assertEqual(imagecap.PICTURE_MAX, 8 * 1024 * 1024, "the Image template keeps its 8 MiB")
        self.assertEqual(server.IMAGE_FILE_MB * 1024 * 1024, gallery.PICTURE_MAX)
        self.assertGreater(server.ROUTE_BODY_LIMITS["/api/section-image"], gallery.PICTURE_MAX * 4 // 3 + server.REQUEST_ENVELOPE, "the route takes a 10 MiB picture in base64")
        self.assertGreater(gallery.LIMIT, gallery.V1_LIMIT, "a stored 1.0.7 gallery is never refused for size")
        self.assertLess(6 * (gallery.FRAMED_MAX + 2) // 3 * 4, 5 * 1024 * 1024, "six framed copies fit a published report")
        self.assertEqual(gallery.LIMIT, section_bodies.LIMITS["gallery"])
        self.assertEqual(gallery.START, '{"v":2}')

    def test_a_version_2_body_keeps_its_fields_and_leaves_out_the_defaults(self):
        body = gallery.check({"v": 2, "columns": 3, "shape": "4:3", "items": {"1": {"caption": " Fictional ", "alt": "A hall", "fx": 500}}}, None)
        self.assertEqual(body, {"v": 2, "items": {"1": {"caption": "Fictional", "alt": "A hall"}}})
        body = gallery.check({"v": 2, "columns": 2, "shape": "square", "items": {"2": {"fx": 100, "fy": 900, "crop": [0, 0, 500, 500]}}}, None)
        self.assertEqual(body, {"v": 2, "columns": 2, "shape": "square", "items": {"2": {"fx": 100, "fy": 900, "crop": [0, 0, 500, 500]}}})
        self.assertEqual(gallery.check({"v": 2}, None), {"v": 2})
        self.assertEqual(gallery.check({"v": 2, "shape": "whole"}, None), {"v": 2, "shape": "whole"}, "whole is never the default, so it is kept")

    def test_what_is_refused(self):
        for bad, words in (({"v": 2, "columns": 4}, gallery.BAD_LAYOUT), ({"v": 2, "columns": "3"}, gallery.BAD_LAYOUT), ({"v": 2, "columns": True}, gallery.BAD_LAYOUT),
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
        text = store_module.check_section_body("gallery", json.dumps({"v": 2, "columns": 2, "items": {"1": {"caption": "Fictional"}}}))
        self.assertEqual(json.loads(text), {"v": 2, "columns": 2, "items": {"1": {"caption": "Fictional"}}})
        with self.assertRaises(store_module.Invalid):
            store_module.check_section_body("gallery", json.dumps({"v": 2, "columns": 5}))


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
                gallery.with_picture(WHOLE, "1", bad)
            self.assertIn("image", str(e.exception))
            self.assertNotIn("picture", str(e.exception).replace("Pictures", "").replace("Add a picture", ""))
        self.assertEqual(gallery._say_image(CAMERA_DETAILS), CAMERA_DETAILS)       # the button keeps its words


class Sizes(unittest.TestCase):
    def test_a_very_large_image_becomes_1600_wide_and_a_small_one_is_not_enlarged(self):
        body = add(WHOLE, "1", make_png(2400, 8, lambda x, y: RED if x < 1200 else BLUE))
        w, h, rows = decode(body["pictures"]["1"])
        self.assertEqual((w, h), (1600, 5))
        self.assertEqual(body["items"]["1"]["from_w"], 2400)
        self.assertEqual((rows[0][0], rows[0][-1]), (RED, BLUE))
        self.assertNotIn("o1", body["pictures"], "the shrunk image is its own original")
        small = add(WHOLE, "2", halves(30, 20))
        self.assertEqual(decode(small["pictures"]["2"])[:2], (30, 20))
        self.assertNotIn("items", small)

    def test_the_original_is_the_shrunk_image_so_a_crop_decodes_to_the_framed_part_only(self):
        body = add(WHOLE, "1", make_png(2400, 8, lambda x, y: RED if x < 1200 else BLUE))
        body["items"]["1"]["crop"] = [500, 0, 1000, 1000]
        out = gallery.check(body, None)
        w, h, rows = decode(out["pictures"]["1"])
        self.assertEqual(w, 800)
        self.assertEqual({px for row in rows for px in row}, {BLUE})
        self.assertEqual(decode(out["pictures"]["o1"])[0], 1600, "the original is kept so Reset works")

    def test_a_jpeg_wider_than_1600_is_refused_in_words_and_a_png_cut_is_asked_for(self):
        with self.assertRaises(Bad) as e:
            gallery.with_picture(WHOLE, "1", sized_jpeg(2000))
        self.assertEqual(str(e.exception), gallery.TOO_WIDE)
        body = add(WHOLE, "1", sized_jpeg(800))
        self.assertEqual(body["pictures"], {"1": sized_jpeg(800)})
        with self.assertRaises(Bad) as e:
            gallery.with_picture({"v": 2, "shape": "square"}, "1", sized_jpeg(800))
        self.assertEqual(str(e.exception), imagecap.CANT_FRAME.replace("picture", "image"))

    def test_a_jpeg_exactly_1600_wide_is_kept_and_one_pixel_wider_is_refused(self):
        body = add(WHOLE, "1", sized_jpeg(gallery.WIDTH_MAX))
        self.assertEqual(body["pictures"], {"1": sized_jpeg(gallery.WIDTH_MAX)})
        with self.assertRaises(Bad) as e:
            gallery.with_picture(WHOLE, "1", sized_jpeg(gallery.WIDTH_MAX + 1))
        self.assertEqual(str(e.exception), gallery.TOO_WIDE)

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
        back = gallery.check(body, None)
        self.assertEqual(back["pictures"]["1"], halves(40, 10))
        self.assertNotIn("o1", back["pictures"], "one copy of the same image is kept")

    def test_the_published_file_carries_each_image_as_framed(self):
        body = add(WHOLE, "1", halves(40, 10))
        body["items"] = {"1": {"crop": [500, 0, 1000, 1000], "caption": "Fictional"}}
        body = gallery.check(body, None)
        out = gallery.published(body, None)
        self.assertEqual(out, {"content": {"pictures": [{"image": body["pictures"]["1"], "caption": "Fictional", "alt": ""}], "columns": 3, "shape": "whole"}})
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
        body = add(WHOLE, "1", halves(40, 10))
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
        body = add(WHOLE, "1", halves(8, 6))
        out = gallery.check(gallery.with_picture(body, "1", None), None)
        self.assertEqual(out, {"v": 2, "shape": "whole"})
        self.assertIsNone(gallery.published(out, None))
        self.assertIsNone(gallery.published({"v": 2}, None))

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
        body = add(add(WHOLE, "2", halves(8, 6)), "5", halves(9, 6))
        body["order"] = ["5"]
        body = gallery.check(body, None)
        self.assertEqual(body["order"], ["5", "1", "2", "3", "4", "6"])
        self.assertEqual([decode(p["image"])[0] for p in gallery.published(body, None)["content"]["pictures"]], [9, 8])


class Columns(unittest.TestCase):
    def test_columns_and_shape_are_published_for_the_page_to_draw(self):
        body = gallery.check({**six("square"), "columns": 2}, None)
        content = gallery.published(body, None)["content"]
        self.assertEqual((content["columns"], content["shape"], len(content["pictures"])), (2, "square", 6))
        self.assertEqual(gallery.published(six(), None)["content"]["columns"], 3)


class SayImage(unittest.TestCase):
    def test_say_image_leaves_the_side_sentence_alone(self):
        side = "A picture sits on the left or the right. Choose one and try again."
        self.assertEqual(BAD_SIDE, side)
        self.assertEqual(gallery._say_image(side), side)
        self.assertEqual(gallery._say_image("Oops. " + side), "Oops. " + side)
        self.assertEqual(gallery._say_image("That picture is big. " + side + " Use a picture."), "That image is big. " + side + " Use an image.")
        self.assertEqual(gallery._say_image("That picture can't be used."), "That image can't be used.")
        self.assertEqual(gallery._say_image("Use a picture."), "Use an image.")


class Version1Stays(unittest.TestCase):
    OLD = {"v": 1, "items": {"1": {"caption": "Fictional one", "alt": "A room"}, "2": {"caption": "Two"}}, "pictures": {"1": GOOD, "2": GOOD_JPEG}}

    def test_a_picture_of_10_mib_is_read_and_one_byte_more_is_refused_at_once(self):
        from clark.section_kinds.textimage import picture
        mib = 1024 * 1024
        exact = data(jpeg(pad=10 * mib - 101), "jpeg")
        self.assertEqual(picture(exact, gallery.PICTURE_MAX), exact, "10 MiB decoded is read")
        over = data(jpeg(pad=10 * mib - 101 + 4), "jpeg")
        with self.assertRaises(Bad) as e:
            gallery.with_picture({"v": 2}, "1", over)
        self.assertEqual(str(e.exception), imagecap._say_image(BIG_PICTURE), "over 10 MiB is refused before it is decoded")
        with self.assertRaises(Bad) as e:
            imagecap.with_picture({"v": 2}, "original", data(jpeg(pad=9 * mib), "jpeg"))
        self.assertEqual(str(e.exception), imagecap._say_image(BIG_PICTURE), "the Image template still refuses over 8 MiB")

    def test_a_1_0_7_gallery_checks_and_publishes_as_before(self):
        self.assertEqual(gallery.check(self.OLD, None), self.OLD)
        self.assertEqual(gallery.published(self.OLD, None), {"content": {"pictures": [
            {"image": GOOD, "caption": "Fictional one", "alt": "A room"}, {"image": GOOD_JPEG, "caption": "Two", "alt": ""}]}})
        self.assertIsNone(gallery.published({"v": 1, "items": {"1": {"caption": "x"}}}, None))
        for bad in ({"v": 1, "columns": 2}, {"v": 1, "order": ["1"]}, {"v": 1, "items": {"1": {"fx": 5}}}, {"v": 1, "pictures": {"o1": GOOD}}):
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
        self.assertEqual(got["items"], self.OLD["items"], "every caption and description is kept")
        self.assertEqual(got["pictures"]["2"], GOOD_JPEG, "a JPEG is not cut by the default shape: it is kept as stored")
        self.assertEqual(got["pictures"]["o1"], GOOD, "the old PNG is kept whole as the original, so the upgrade loses nothing")
        shown = gallery.published(got, None)["content"]
        self.assertEqual([(p["caption"], p["alt"]) for p in shown["pictures"]], [("Fictional one", "A room"), ("Two", "")])
        self.assertEqual(shown["pictures"][1]["image"], GOOD_JPEG)
        self.assertEqual((shown["columns"], shown["shape"]), (3, "4:3"))
        self.assertNotIn(GOOD, [p["image"] for p in shown["pictures"][1:]])
        back = gallery.check({"v": 2, "shape": "whole", "items": got["items"], "pictures": got["pictures"]}, None)
        self.assertEqual(back["pictures"]["1"], GOOD, "the original comes back whole")
        self.assertNotIn("o1", back["pictures"])

    def test_a_shape_said_on_a_jpeg_is_still_refused_in_words(self):
        with self.assertRaises(Bad):
            gallery.check({"v": 2, "shape": "square", "pictures": {"1": GOOD_JPEG}}, None)


class RuledRules(unittest.TestCase):
    """Row 1233 ruling: the new gallery starts 4:3, 3 across (the page draws 2 across at half width and at 900 px); old galleries stay;
    whole is never the default. Real checks and the real store; the page side is in test_tpl_gallery_view."""

    def test_a_new_gallery_is_4_3_three_across_and_a_png_is_cut_to_4_3(self):
        self.assertEqual(gallery.START, '{"v":2}')
        self.assertEqual((gallery.DEFAULT_SHAPE, gallery.DEFAULT_COLUMNS), ("4:3", 3))
        self.assertEqual((gallery.COLUMNS, gallery.SHAPES), ((2, 3), ("4:3", "square", "16:9", "whole")))
        body = add({"v": 2}, "1", halves(40, 10))
        self.assertNotIn("shape", body)
        self.assertNotIn("columns", body)
        w, h, _ = decode(body["pictures"]["1"])
        self.assertEqual((w, h), (13, 10), "cut to 4:3 around the focus")
        self.assertIn("o1", body["pictures"], "the whole image is kept as the original")
        content = gallery.published(body, None)["content"]
        self.assertEqual((content["columns"], content["shape"]), (3, "4:3"))
        self.assertEqual(decode(content["pictures"][0]["image"])[:2], (13, 10))

    def test_whole_is_never_the_default_not_in_check_not_in_published_not_for_a_new_image(self):
        self.assertNotIn("shape", gallery.check({"v": 2}, None))
        self.assertEqual(gallery.published(add({"v": 2}, "1", halves(40, 10)), None)["content"]["shape"], "4:3")
        self.assertNotEqual(gallery.published(add({"v": 2}, "1", halves(40, 10)), None)["content"]["shape"], "whole")
        self.assertEqual(gallery.published(add({"v": 2, "shape": "whole"}, "1", halves(40, 10)), None)["content"]["shape"], "whole")
        self.assertNotIn("o1", add({"v": 2, "shape": "whole"}, "1", halves(40, 10))["pictures"])

    def test_columns_default_3_and_2_is_kept_and_published_under_main_names(self):
        body = add({"v": 2}, "1", halves(40, 10))
        self.assertEqual(gallery.published(body, None)["content"]["columns"], 3)
        two = gallery.check({**body, "columns": 2}, None)
        self.assertEqual(two["columns"], 2)
        self.assertEqual(gallery.published(two, None)["content"]["columns"], 2)
        with self.assertRaises(Bad):
            gallery.check({"v": 2, "cols": 2}, None)
        for bad in (2.0, 3.0, True, "2", None, [2]):
            with self.assertRaises(Bad, msg=repr(bad)):
                gallery.check({"v": 2, "columns": bad}, None)
        for bad in (["4:3"], {"a": 1}, 43, None, True):
            with self.assertRaises(Bad, msg=repr(bad)):
                gallery.check({"v": 2, "shape": bad}, None)
        self.assertIsNone(gallery.published({**body, "columns": 4}, None), "a stored number that is not 2 or 3 is never published")
        for odd in ("tall", ["4:3"], 43, None):
            self.assertIsNone(gallery.published({**body, "shape": odd}, None), repr(odd))

    def test_a_new_image_is_cut_to_4_3_by_with_picture_itself_before_any_check(self):
        raw = gallery.with_picture({"v": 2}, "1", halves(40, 10))
        self.assertEqual(decode(raw["pictures"]["1"])[:2], (13, 10))
        self.assertEqual(raw["pictures"]["o1"], halves(40, 10))
        sq = gallery.with_picture({"v": 2, "shape": "square"}, "1", halves(40, 10))
        self.assertEqual(decode(sq["pictures"]["1"])[:2], (10, 10))
        whole = gallery.with_picture({"v": 2, "shape": "whole"}, "1", halves(40, 10))
        self.assertEqual(whole["pictures"], {"1": halves(40, 10)})

    def test_a_sent_framed_copy_is_never_trusted_whatever_its_type(self):
        got = gallery.check({"v": 2, "pictures": {"1": GOOD_JPEG, "o1": halves(40, 10)}}, None)
        self.assertEqual(decode(got["pictures"]["1"])[:2], (13, 10), "made again from the PNG original, cut to 4:3 (the copy sent was a JPEG)")
        self.assertEqual(got["pictures"]["o1"], halves(40, 10))
        with self.assertRaises(Bad):
            gallery.check({"v": 2, "pictures": {"1": halves(40, 10), "o1": GOOD_JPEG}}, None)

    def test_a_version_1_body_publishes_a_columns_and_shape_it_holds_only_when_valid(self):
        old = {"v": 1, "pictures": {"1": GOOD}}
        got = gallery.published({**old, "columns": 2, "shape": "square"}, None)["content"]
        self.assertEqual((got["columns"], got["shape"]), (2, "square"))
        got = gallery.published({**old, "columns": 4, "shape": "tall"}, None)["content"]
        self.assertEqual(set(got), {"pictures"})

    def test_a_png_default_and_the_published_never_carries_the_original(self):
        body = add({"v": 2}, "1", halves(40, 10))
        self.assertNotIn(body["pictures"]["o1"], repr(gallery.published(body, None)))

    def test_old_v1_file_is_unchanged_in_check_published_and_the_real_store(self):
        old = {"v": 1, "items": {"1": {"caption": "Fictional one"}}, "pictures": {"1": GOOD, "2": GOOD_JPEG}}
        text = json.dumps(old)
        self.assertEqual(json.loads(store_module.check_section_body("gallery", text)), old, "opens and saves as it was")
        self.assertEqual(gallery.published(old, None), {"content": {"pictures": [
            {"image": GOOD, "caption": "Fictional one", "alt": ""}, {"image": GOOD_JPEG, "caption": "", "alt": ""}]}},
            "no columns and no shape are published: the page draws it 4:3 as before")
        self.assertEqual(gallery.with_picture(old, "3", GOOD)["pictures"]["3"], GOOD)
        self.assertEqual(gallery.with_picture(old, "3", GOOD)["v"], 1, "a picture added to an old gallery does not upgrade it")

    def test_v2_round_trip_through_the_real_store(self):
        body = add({"v": 2, "shape": "16:9", "columns": 2}, "1", halves(40, 10))
        body["items"] = {"1": {"caption": "Fictional", "alt": "A hall", "fx": 100, "fy": 300, "crop": [0, 0, 1000, 800]}}
        body = gallery.check(body, None)
        text = store_module.check_section_body("gallery", json.dumps(body))
        self.assertEqual(json.loads(text), body, "what is saved is what comes back")
        again = json.loads(store_module.check_section_body("gallery", text))
        self.assertEqual(again, body)
        self.assertEqual(body["items"]["1"], {"caption": "Fictional", "alt": "A hall", "fx": 100, "fy": 300, "crop": [0, 0, 1000, 800]})
        self.assertEqual(body["pictures"]["o1"], halves(40, 10), "the original is the full image")
        got = gallery.published(body, None)["content"]
        self.assertEqual((got["columns"], got["shape"], got["pictures"][0]["caption"], got["pictures"][0]["alt"]), (2, "16:9", "Fictional", "A hall"))
        self.assertEqual(got["pictures"][0]["image"], body["pictures"]["1"], "the framed copy, never the original")


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

    def test_a_v1_gallery_gets_a_words_only_v2_update_without_a_keyerror_1567(self):
        old = Version1Stays.OLD
        section = {"type": "gallery", "body": json.dumps(old, separators=(",", ":"))}
        out = json.loads(changes._keep_pictures(section, json.dumps({"v": 2, "items": {"1": {"caption": "Fictional new"}}})))
        self.assertEqual(out["pictures"], old["pictures"], "the stored pictures are kept as they were")
        self.assertEqual(out["items"], {"1": {"caption": "Fictional new"}}, "the words are taken")
        one = {"type": "textimage", "body": json.dumps({"v": 1, "pictures": {"image": GOOD}}, separators=(",", ":"))}
        got = json.loads(changes._keep_pictures(one, json.dumps({"v": 2})))
        self.assertEqual(got["pictures"]["original"], GOOD, "a v1 Image or Text and Image body: the image becomes the original, as in row 1232")


if __name__ == "__main__":
    unittest.main()
