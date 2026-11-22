"""Row 1232, server side of 'Text and Image Side by Side' (store type 'textimage', body version 2): the fields and their limits, the
framed copy (made by the Full width image's own code), the position kept for each width, and what is published (the framed copy
only, never the original). The old Text and image body (version 1) must open, save and publish unchanged.

Run: python3 dev/run_tests.py test_textimage_side_server
Fictional data only. No browser.
"""
import json
import unittest

from _pictures import GOOD, GOOD_JPEG, PictureSteps, check, data, png, published
from test_changes import Api
from test_imagecap_full_server import BLUE, GREEN, RED, decode, halves, make_png, sized_jpeg
from clark import changes, section_bodies, server as sv
from clark.section_kinds import base, imagecap, textimage as ti

WORDS = "<p>Fictional words about the site.</p>"


def made(original, **fields):
    """The body a section holds after the original is added (the route's step), checked as the store checks it."""
    body = ti.with_picture({"v": 2, **fields}, "original", original)
    return ti.check(body, None)


def framed(body):
    return decode(body["pictures"]["image"])


class Fields(unittest.TestCase):
    def test_a_new_body_is_just_its_version(self):
        self.assertEqual(ti.START, '{"v":2}')
        self.assertEqual(ti.check({"v": 2}, None), {"v": 2})
        self.assertIsNone(ti.published({"v": 2}, None))

    def test_the_defaults_are_not_stored(self):
        body = {"v": 2, "html": WORDS, "side": "right", "half": "top", "share": "half", "shape": "fill", "fx": 500, "fy": 500}
        self.assertEqual(ti.check(body, None), {"v": 2, "html": WORDS})

    def test_each_width_keeps_its_own_position(self):
        """Full left, then half bottom, then back to full: still left (the two choices are two fields)."""
        body = ti.check({"v": 2, "html": WORDS, "side": "left"}, None)
        body = ti.check({**body, "half": "bottom"}, None)
        self.assertEqual((body["side"], body["half"]), ("left", "bottom"))
        again = ti.check(json.loads(json.dumps(body)), None)
        self.assertEqual(again, body)
        self.assertEqual(ti.published(body, None)["content"]["side"], "left")
        self.assertEqual(ti.published(body, None)["content"]["half"], "bottom")

    def test_only_the_choices_of_each_field_are_taken(self):
        for key, bad in (("side", "top"), ("side", "bottom"), ("half", "left"), ("half", "right"), ("share", "quarter"),
                         ("shape", "banner"), ("shape", "free"), ("shape", "16:9"), ("side", None), ("share", 3)):
            with self.subTest(key=key, bad=bad):
                with self.assertRaises(base.Bad) as e:
                    ti.check({"v": 2, key: bad}, None)
                self.assertEqual(str(e.exception), imagecap.BAD_FRAME)

    def test_the_three_widths_and_the_shapes_are_all_taken(self):
        for share in ti.SHARES:
            for shape in ti.SHAPES_V2:
                body = ti.check({"v": 2, "share": share, "shape": shape}, None)
                self.assertEqual(body.get("share", "half"), share)
                self.assertEqual(body.get("shape", "fill"), shape)

    def test_a_field_this_section_does_not_keep_is_refused(self):
        for key in ("ratio", "side_width", "pictures2", "full", "style"):
            with self.assertRaises(base.Bad) as e:
                ti.check({"v": 2, key: 1}, None)
            self.assertEqual(str(e.exception), ti.UNKNOWN_FIELD)

    def test_a_newer_version_is_refused_and_the_framing_is_validated(self):
        with self.assertRaises(base.Bad) as e:
            ti.check({"v": 3}, None)
        self.assertEqual(str(e.exception), ti.OLD_VERSION)
        for bad in ({"fx": 1001}, {"fx": "5"}, {"crop": [0, 0, 5, 5]}, {"crop": [0, 0, 1000]}, {"fit": "zoom"}, {"fill": "red"}, {"from_w": 0}):
            with self.subTest(bad=bad):
                with self.assertRaises(base.Bad) as e:
                    ti.check({"v": 2, **bad}, None)
                self.assertEqual(str(e.exception), imagecap.BAD_FRAME)

    def test_the_heading_the_caption_and_the_description_are_one_line_of_text(self):
        body = ti.check({"v": 2, "heading": "  Fictional heading ", "caption": " c ", "alt": " d "}, None)
        self.assertEqual((body["heading"], body["caption"], body["alt"]), ("Fictional heading", "c", "d"))
        for key in ("heading", "caption", "alt"):
            with self.assertRaises(base.Bad) as e:
                ti.check({"v": 2, key: "x" * 301}, None)
            self.assertEqual(str(e.exception), ti.LONG_LINE)
            with self.assertRaises(base.Bad) as e:
                ti.check({"v": 2, key: ["x"]}, None)
            self.assertEqual(str(e.exception), ti.NOT_A_LINE)

    def test_the_words_have_their_limits_and_html_wins_over_the_old_lines(self):
        self.assertEqual(ti.check({"v": 2, "html": WORDS, "words": ["old"]}, None), {"v": 2, "html": WORDS})
        self.assertEqual(ti.check({"v": 2, "words": [" one ", "", "two"]}, None), {"v": 2, "words": ["one", "two"]})
        with self.assertRaises(base.Bad) as e:
            ti.check({"v": 2, "html": "x" * (ti.HTML_MAX + 1)}, None)
        self.assertEqual(str(e.exception), ti.LONG_HTML)
        with self.assertRaises(base.Bad) as e:
            ti.check({"v": 2, "words": ["p"] * 21}, None)
        self.assertEqual(str(e.exception), ti.TOO_MANY_WORDS)

    def test_the_stored_limit_holds_both_images_and_the_words(self):
        self.assertGreaterEqual(ti.LIMIT, imagecap.LIMIT + 2 * ti.HTML_MAX)
        self.assertEqual(section_bodies.LIMITS["textimage"], ti.LIMIT)
        self.assertEqual(ti.SEND_MAX, imagecap.PICTURE_MAX)
        self.assertEqual(ti.PICTURE_MAX, imagecap.V1_PICTURE_MAX)           # a version 1 picture keeps its 1 MiB

    def test_the_store_checks_a_version_2_body_like_the_module(self):
        self.assertEqual(check("textimage", {"v": 2, "html": WORDS, "side": "left"}), {"v": 2, "html": WORDS, "side": "left"})


class FramedPixels(unittest.TestCase):
    def test_a_crop_leaves_only_the_cropped_part_in_the_framed_copy(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000])
        w, h, rows = framed(body)
        self.assertEqual((w, h), (20, 10))
        self.assertEqual({px for row in rows for px in row}, {BLUE})

    def test_the_published_file_has_the_framed_copy_and_never_the_original(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000], html=WORDS)
        content = ti.published(body, None)["content"]
        w, h, rows = decode(content["image"])                            # decoded from the published content, not looked at
        self.assertEqual({px for row in rows for px in row}, {BLUE})
        self.assertNotIn(body["pictures"]["original"], repr(content))
        self.assertNotIn("pictures", content)
        self.assertEqual(decode(body["pictures"]["original"])[:2], (40, 10), "the editor keeps the original, whole")

    def test_4_3_and_square_are_cut_around_the_focus(self):
        for shape, width in (("4:3", 39), ("square", 30)):                 # 30 tall: 4:3 is 1.333 wide (39 whole pixels)
            left = framed(made(halves(60, 30), shape=shape, fx=0))
            right = framed(made(halves(60, 30), shape=shape, fx=1000))
            self.assertEqual((left[0], left[1]), (width, 30))
            self.assertEqual(left[0], right[0])
            self.assertEqual({px for row in left[2] for px in row[:5]}, {RED})
            self.assertEqual({px for row in right[2] for px in row[-5:]}, {BLUE})

    def test_whole_and_fill_cut_no_shape_but_a_crop_applies_to_both(self):
        for shape in ("whole", "fill"):
            w, h, rows = framed(made(halves(40, 10), shape=shape, fx=0, fy=0))
            self.assertEqual((w, h, rows[0][0], rows[0][-1]), (40, 10, RED, BLUE))
            w, h, rows = framed(made(halves(40, 10), shape=shape, crop=[0, 0, 500, 1000]))
            self.assertEqual((w, h), (20, 10))

    def test_5200_wide_becomes_3000_wide_and_the_note_says_so(self):
        body = made(make_png(5200, 6, lambda x, y: GREEN))
        self.assertEqual(framed(body)[:2], (3000, 3))
        self.assertEqual(decode(body["pictures"]["original"])[:2], (3000, 3))
        self.assertEqual(body["from_w"], 5200)

    def test_1800_wide_is_left_alone(self):
        body = made(make_png(1800, 2, lambda x, y: GREEN))
        self.assertEqual(framed(body)[:2], (1800, 2))
        self.assertNotIn("from_w", body)
        self.assertEqual(body["pictures"]["image"], body["pictures"]["original"], "nothing changed: the original is the framed copy")

    def test_600_wide_is_not_enlarged(self):
        self.assertEqual(framed(made(make_png(600, 100, lambda x, y: GREEN)))[:2], (600, 100))
        self.assertEqual(framed(made(make_png(600, 600, lambda x, y: GREEN), shape="4:3"))[:2], (600, 450))
        self.assertEqual(framed(made(make_png(600, 600, lambda x, y: GREEN), shape="square"))[:2], (600, 600))

    def test_a_small_image_carries_how_the_page_draws_it(self):
        body = made(make_png(600, 100, lambda x, y: GREEN), html=WORDS, fit="stretch", fill="brand")
        content = ti.published(body, None)["content"]
        self.assertEqual((content["fit"], content["fill"]), ("stretch", "brand"))

    def test_a_jpeg_is_used_as_it_is_when_nothing_is_cut_and_cannot_be_shaped(self):
        body = ti.with_picture({"v": 2}, "original", sized_jpeg(1800))
        self.assertEqual(ti.check(body, None)["pictures"]["image"], sized_jpeg(1800))
        with self.assertRaises(base.Bad) as e:
            made(sized_jpeg(1800), shape="square")
        self.assertEqual(str(e.exception), imagecap.CANT_FRAME)

    def test_a_changed_framing_makes_the_copy_again_here(self):
        body = made(halves(40, 10))
        sent = {**body, "crop": [500, 0, 1000, 1000]}
        self.assertEqual(framed(ti.check(sent, None))[:2], (20, 10))

    def test_a_framed_copy_that_is_not_ours_is_made_again_never_kept(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000])
        forged = {**body, "pictures": {"original": body["pictures"]["original"], "image": made(make_png(40, 10, lambda x, y: GREEN))["pictures"]["image"]}}
        again = ti.check(forged, None)
        self.assertEqual(again["pictures"]["image"], body["pictures"]["image"])

    def test_a_framed_copy_alone_is_refused(self):
        with self.assertRaises(base.Bad) as e:
            ti.check({"v": 2, "pictures": {"image": GOOD}}, None)
        self.assertEqual(str(e.exception), imagecap.NOT_ALONE)

    def test_only_the_original_is_taken_and_a_new_one_starts_from_no_framing(self):
        with self.assertRaises(base.Bad) as e:
            ti.with_picture({"v": 2}, "image", GOOD)
        self.assertEqual(str(e.exception), imagecap.MADE_HERE)
        body = made(halves(40, 10), shape="square", crop=[0, 0, 500, 1000], fx=100, html=WORDS, side="left", half="bottom", share="two", heading="H")
        again = ti.with_picture(body, "original", halves(40, 10))
        for key in ("shape", "crop", "fx", "fy", "fit", "fill", "from_w"):
            self.assertNotIn(key, again)
        for key in ("side", "half", "share", "heading", "html"):
            self.assertEqual(again[key], body[key], "the words and the position stay")
        gone = ti.with_picture(body, "original", None)
        self.assertNotIn("pictures", gone)
        self.assertEqual(gone["html"], WORDS)

    def test_refusals_say_image_never_picture(self):
        for original in ("data:image/gif;base64,AAAA", "nonsense", 7):
            with self.assertRaises(base.Bad) as e:
                ti.with_picture({"v": 2}, "original", original)
            self.assertNotIn("icture", str(e.exception))

    def test_camera_details_and_a_wide_jpeg_are_refused(self):
        from _pictures import EXIF
        with self.assertRaises(base.Bad) as e:
            ti.with_picture({"v": 2}, "original", EXIF)
        self.assertEqual(str(e.exception), ti.CAMERA_DETAILS.replace("picture", "image").replace("Add a image", "Add an image"))
        with self.assertRaises(base.Bad) as e:
            ti.with_picture({"v": 2}, "original", sized_jpeg(3500))
        self.assertEqual(str(e.exception), imagecap.TOO_WIDE)


class Published(unittest.TestCase):
    def test_nothing_with_no_words_and_no_image_even_with_a_heading_and_a_caption(self):
        self.assertIsNone(ti.published({"v": 2, "heading": "H", "caption": "c", "alt": "d"}, None))
        self.assertIsNone(ti.published({"v": 2, "html": ""}, None))
        self.assertIsNone(ti.published("x", None))

    def test_words_only_has_no_image_fields_and_no_empty_caption(self):
        got = ti.published({"v": 2, "html": WORDS, "caption": "never shown", "alt": "never shown"}, None)["content"]
        self.assertEqual(got, {"words": [], "v": 2, "html": WORDS})

    def test_an_image_only_is_published_with_its_caption_and_description(self):
        body = made(halves(40, 10), caption="Fictional caption", alt="Two halves")
        got = ti.published(body, None)["content"]
        self.assertEqual((got["caption"], got["alt"]), ("Fictional caption", "Two halves"))
        self.assertEqual(got["v"], 2)
        self.assertEqual((got["fx"], got["fy"]), (500, 500), "fill the height: the page fits the image to the words around this point")

    def test_the_position_and_the_look_are_carried_only_when_chosen(self):
        body = made(halves(40, 10), html=WORDS, side="left", half="bottom", share="two", shape="4:3", heading="Fictional heading")
        got = ti.published(body, None)["content"]
        for key, want in (("side", "left"), ("half", "bottom"), ("share", "two"), ("shape", "4:3"), ("heading", "Fictional heading")):
            self.assertEqual(got[key], want)
        self.assertNotIn("fx", got, "a shape cut here needs no focus on the page")
        plain = ti.published(made(halves(40, 10), html=WORDS), None)["content"]
        for key in ("side", "half", "share", "shape", "heading"):
            self.assertNotIn(key, plain)

    def test_an_image_whose_copy_is_not_ours_is_left_out_and_the_words_stay(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000], html=WORDS)
        body["pictures"]["image"] = made(make_png(40, 10, lambda x, y: GREEN))["pictures"]["image"]
        got = ti.published(body, None)["content"]
        self.assertNotIn("image", got)
        self.assertEqual(got["html"], WORDS)
        self.assertIsNone(ti.published({**body, "html": ""}, None))
        self.assertIsNone(ti.published({"v": 2, "pictures": {"image": GOOD}}, None))

    def test_a_stored_body_that_no_longer_checks_still_publishes_what_is_safe(self):
        self.assertIsNone(ti.published({"v": 2, "fx": 5000, "pictures": {"original": GOOD, "image": GOOD}}, None))
        self.assertEqual(ti.published({"v": 2, "fx": 5000, "html": WORDS}, None)["content"]["html"], WORDS)

    def test_the_words_are_cleaned_again_at_publish(self):
        out = section_bodies.published("textimage", {"v": 2, "html": '<p>ok</p><script>alert(1)</script><p onclick="x">two</p>'})
        self.assertNotIn("script", out["content"]["html"])
        self.assertNotIn("onclick", out["content"]["html"])

    def test_the_published_file_through_the_store_helper(self):
        got = published("textimage", made(halves(40, 10), html=WORDS))
        self.assertEqual(got["content"]["html"], WORDS)


class Version1(unittest.TestCase):
    """The old Text and image body opens, saves and publishes exactly as it did before row 1232."""
    OLD = {"v": 1, "html": WORDS, "caption": "c", "alt": "a", "side": "left", "pictures": {"image": GOOD_JPEG}}

    def test_an_old_body_is_checked_to_itself(self):
        self.assertEqual(ti.check(dict(self.OLD), None), self.OLD)
        self.assertEqual(ti.check({"html": WORDS}, None), {"v": 1, "html": WORDS})
        with self.assertRaises(base.Bad) as e:
            ti.check({"v": 1, "half": "top"}, None)
        self.assertEqual(str(e.exception), ti.UNKNOWN_FIELD)

    def test_an_old_body_publishes_as_before(self):
        self.assertEqual(ti.published(dict(self.OLD), None),
                         {"content": {"words": [], "side": "left", "html": WORDS, "image": GOOD_JPEG, "caption": "c", "alt": "a"}})
        self.assertEqual(ti.published({"v": 1, "html": WORDS}, None), {"content": {"words": [], "side": "right", "html": WORDS}})
        self.assertIsNone(ti.published({"v": 1, "caption": "only"}, None))

    def test_an_old_body_keeps_its_one_slot_and_its_one_mebibyte(self):
        self.assertEqual(ti.with_picture(None, "image", GOOD_JPEG), {"v": 1, "pictures": {"image": GOOD_JPEG}})
        self.assertEqual(ti.with_picture({"v": 1, "html": WORDS}, "image", None), {"v": 1, "html": WORDS})
        with self.assertRaises(base.Bad) as e:
            ti.with_picture(None, "original", GOOD_JPEG)
        self.assertEqual(str(e.exception), ti.BAD_SLOT)
        big = data(png((b"tEXt", b"x" * (ti.PICTURE_MAX + 10))))
        with self.assertRaises(base.Bad) as e:
            ti.with_picture(None, "image", big)
        self.assertEqual(str(e.exception), ti.BIG_PICTURE)




class Route(PictureSteps, Api):
    def new(self):
        return self.ok("new", values={"type": "textimage", "title": "Fictional side by side", "body": ti.START})["ref"]

    def test_a_new_section_may_start_as_version_2_and_only_so(self):
        ref = self.new()
        self.assertEqual(self.body(ref), {"v": 2})
        for body in ('{"v":1}', '{"v":2,"html":"<p>x</p>"}'):
            status, got = self.change(self.req("new", values={"type": "textimage", "title": "x", "body": body}))
            self.assertEqual(status, 400, got)
        self.assertIsNone(self.body(self.made("textimage")), "without the start body a textimage section is empty, as before")

    def test_the_words_and_the_position_save_through_the_change_route_and_keep_the_image(self):
        ref = self.new()
        self.assertEqual(self.put(ref, "original", halves(40, 10))[0], 200)
        sent = {"v": 2, "html": WORDS, "heading": "H", "side": "left", "half": "bottom", "share": "third", "shape": "square", "caption": "c"}
        status, got = self.words(ref, sent)
        self.assertEqual(status, 200, got)
        stored = self.body(ref)
        self.assertEqual((stored["side"], stored["half"], stored["share"], stored["shape"]), ("left", "bottom", "third", "square"))
        self.assertEqual(framed(stored)[:2], (10, 10), "the framing changed with the words: the copy is made again here")
        self.assertEqual(decode(stored["pictures"]["original"])[:2], (40, 10))
        self.undone(got["apply_id"])
        self.assertEqual(framed(self.body(ref))[:2], (40, 10), "one step, one Undo: the whole image is back")

    def test_a_crop_a_reset_and_a_focus_move_are_each_one_step_and_one_undo_brings_the_previous_body_back(self):
        ref = self.new()
        self.assertEqual(self.put(ref, "original", halves(40, 10))[0], 200)
        steps = (("crop", {"crop": [500, 0, 1000, 1000]}), ("focus", {"fx": 100, "fy": 700}), ("shape", {"shape": "square", "crop": [0, 0, 500, 1000]}))
        for name, framing in steps:
            before = self.body(ref)
            status, got = self.words(ref, {k: v for k, v in {**before, **framing}.items() if k != "pictures"})
            self.assertEqual(status, 200, (name, got))
            self.assertNotEqual(self.body(ref), before, name)
            self.undone(got["apply_id"])
            self.assertEqual(self.body(ref), before, f"{name}: one Undo restores the previous body, image and framing")
        framed_now = {k: v for k, v in {**self.body(ref), "crop": [500, 0, 1000, 1000], "fx": 100}.items() if k != "pictures"}
        self.assertEqual(self.words(ref, framed_now)[0], 200)
        before = self.body(ref)
        status, got = self.words(ref, {"v": 2})                          # Reset framing: the whole framing sent without its keys
        self.assertEqual(status, 200, got)
        self.assertFalse({"shape", "crop", "fx", "fy"} & set(self.body(ref)), self.body(ref))
        self.undone(got["apply_id"])
        self.assertEqual(self.body(ref), before, "reset: one Undo brings the framing back")

    def test_a_request_cannot_carry_an_image_with_the_words(self):
        ref = self.new()
        status, got = self.words(ref, {"v": 2, "pictures": {"original": GOOD}})
        self.assertEqual((status, got["message"]), (400, ti.PICTURES_OWN_WAY))
        self.assertEqual(self.body(ref), {"v": 2})

    def test_the_image_route_takes_the_large_send_for_version_2_and_one_mebibyte_for_version_1(self):
        ref = self.new()
        self.assertEqual(self.put(ref, "original", halves(40, 10))[0], 200)
        self.assertEqual(framed(self.body(ref))[:2], (40, 10))
        old = self.made("textimage")
        self.assertEqual(self.put(old, "image", GOOD)[0], 200)
        self.assertEqual(self.body(old)["pictures"]["image"], GOOD)
        status, got = self.put(old, "original", GOOD)
        self.assertEqual((status, got["message"]), (400, ti.BAD_SLOT))
        big = data(png((b"tEXt", b"x" * (ti.PICTURE_MAX + 10))))               # a real PNG over 1 MiB: fine for a version 2 original, too large for a version 1 picture
        status, got = self.put(old, "image", big)
        self.assertEqual((status, got["message"]), (400, ti.BIG_PICTURE))

    def test_an_old_section_becomes_version_2_with_its_image_as_the_original(self):
        old = self.made("textimage")
        self.put(old, "image", GOOD)
        self.assertEqual(self.words(old, {"v": 1, "html": WORDS, "side": "left"})[0], 200)
        status, got = self.words(old, {"v": 2, "html": WORDS, "side": "left", "heading": "H"})
        self.assertEqual(status, 200, got)
        stored = self.body(old)
        self.assertEqual(stored["v"], 2)
        self.assertEqual(stored["pictures"], {"original": GOOD, "image": GOOD})
        self.assertEqual((stored["html"], stored["side"]), (WORDS, "left"))

    def test_a_version_2_original_over_one_mebibyte_is_taken_by_the_image_route(self):
        ref = self.new()
        big = data(png((b"tEXt", b"x" * (ti.PICTURE_MAX + 10))))               # a real PNG over 1 MiB: only the large send of version 2 lets it in
        status, got = self.put(ref, "original", big)
        self.assertEqual(status, 200, got)
        self.assertTrue(self.body(ref)["pictures"]["original"])

    def test_the_published_file_has_the_framed_copy_only(self):
        ref = self.new()
        self.put(ref, "original", halves(40, 10))
        self.assertEqual(self.words(ref, {"v": 2, "html": WORDS, "crop": [500, 0, 1000, 1000]})[0], 200)
        sections, text = self.file()
        content = sections[ref].get("content", sections[ref])
        self.assertEqual({px for row in decode(content["image"])[2] for px in row}, {BLUE})
        stored = self.body(ref)["pictures"]
        self.assertIn(stored["image"].split(",", 1)[1], text, "the framed copy is in the file")
        self.assertNotIn(stored["original"].split(",", 1)[1], text, "the original is not")


if __name__ == "__main__":
    unittest.main()
