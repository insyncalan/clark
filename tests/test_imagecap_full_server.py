"""Row 1223, server side of 'Full width image' (store type 'imagecap', body version 2): the checks, the framed copy clark makes from the original and
the framing numbers, the sizes (3,000 px wide at most, never enlarged), camera details, and what is published (the framed copy only).
The old Image with caption body (version 1) must open and publish unchanged: Version1 below.

Run: python3 dev/run_tests.py test_imagecap_full_server
Fictional data only. No browser.
"""
import base64
import struct
import unittest
import zlib

from _pictures import EXIF, GOOD_JPEG, GOOD_WEBP, data, jpeg, png
from clark.section_kinds import imagecap as fi
from clark.section_kinds.base import Bad
from clark.section_kinds.textimage import BAD_SLOT, CAMERA_DETAILS, NOT_A_PICTURE

RED, BLUE, GREEN = (255, 0, 0), (0, 0, 255), (0, 255, 0)


def make_png(w, h, colour_at, ctype=2, extra=None):
    """A real PNG of w x h; colour_at(x, y) -> (r, g, b)."""
    def chunk(name, body):
        return struct.pack(">I", len(body)) + name + body + struct.pack(">I", zlib.crc32(name + body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"".join(bytes(colour_at(x, y)) for x in range(w)) for y in range(h))
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    if extra:
        out += chunk(*extra)
    return data(out + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def decode(text):
    """Independent reader of what clark writes (PNG, filter 0 only): (w, h, rows of (r, g, b) tuples)."""
    raw = base64.b64decode(text.split(",", 1)[1])
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    i, idat, ihdr = 8, b"", None
    while i < len(raw):
        n = int.from_bytes(raw[i:i + 4], "big")
        name, body = raw[i + 4:i + 8], raw[i + 8:i + 8 + n]
        if name == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif name == b"IDAT":
            idat += body
        i += 12 + n
    w, h, _depth, ctype = ihdr[:4]
    ch = 3 if ctype == 2 else 4
    flat = zlib.decompress(idat)
    rows = []
    for y in range(h):
        row = flat[y * (w * ch + 1):(y + 1) * (w * ch + 1)]
        assert row[0] == 0
        rows.append([tuple(row[1 + x * ch:4 + x * ch]) for x in range(w)])
    return w, h, rows


def sized_jpeg(w, h=10):
    """A JPEG's header as the checks read it, with a frame header (SOF0) that names its size."""
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, h, w, 3) + b"\x00" * 9
    return data(b"\xff\xd8\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + sof
                + b"\xff\xda" + b"\x00" * 8 + b"\xff\xd9", "jpeg")


def halves(w, h):
    return make_png(w, h, lambda x, y: RED if x < w // 2 else BLUE)


def made(original, **frame_numbers):
    """The body a section holds after the original is added (the route's step), then checked as the store checks it."""
    body = fi.with_picture({"v": 2, **frame_numbers}, "original", original)
    return fi.check(body, None)


def framed(body):
    return decode(body["pictures"]["image"])


class FramedPixels(unittest.TestCase):
    def test_only_the_cropped_part_is_in_the_published_image(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000])
        got = fi.published(body, None)["content"]["image"]
        w, h, rows = decode(got)
        self.assertEqual((w, h), (20, 10))
        self.assertEqual({px for row in rows for px in row}, {BLUE})          # no red anywhere: the cropped part is gone
        self.assertNotIn(BLUE, {px for row in decode(body["pictures"]["original"])[2] for px in row[:20]})

    def test_the_published_file_never_carries_the_original(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000])
        out = fi.published(body, None)
        self.assertNotIn(body["pictures"]["original"], repr(out))
        self.assertEqual(set(out["content"]), {"image", "caption", "alt", "full"})

    def test_a_shape_cuts_around_the_focus(self):
        left = framed(made(halves(40, 20), shape="banner", fx=0, fy=500))
        right = framed(made(halves(40, 20), shape="banner", fx=1000, fy=500))
        self.assertEqual(left[:2], (40, 13))                                   # 3:1 of 40 wide
        self.assertEqual({px for row in left[2] for px in row[:15]}, {RED})
        self.assertEqual({px for row in right[2] for px in row[-15:]}, {BLUE})

    def test_a_shape_on_a_wide_image_cuts_the_width(self):
        w, h, rows = framed(made(halves(60, 10), shape="16:9", fx=1000))
        self.assertEqual((w, h), (17, 10))
        self.assertEqual({px for row in rows for px in row}, {BLUE})

    def test_a_free_shape_takes_its_ratio(self):
        w, h, _ = framed(made(halves(40, 40), shape="free", ratio=2000))
        self.assertEqual((w, h), (40, 20))

    def test_the_whole_image_by_default_and_grey_and_palette_pngs_read(self):
        w, h, rows = framed(made(halves(10, 4)))
        self.assertEqual((w, h, rows[0][0], rows[0][9]), (10, 4, RED, BLUE))

    def test_a_crop_and_a_shape_together(self):
        w, h, rows = framed(made(halves(100, 20), crop=[500, 0, 1000, 1000], shape="free", ratio=1000, fx=1000))
        self.assertEqual((w, h), (20, 20))
        self.assertEqual({px for row in rows for px in row}, {BLUE})


class Sizes(unittest.TestCase):
    def test_5200_wide_is_made_3000_wide(self):
        body = made(make_png(5200, 6, lambda x, y: GREEN))
        self.assertEqual(framed(body)[:2], (3000, 3))
        self.assertEqual(decode(body["pictures"]["original"])[:2], (3000, 3))
        self.assertEqual(body["from_w"], 5200)

    def test_a_wide_crop_of_a_big_image_is_made_3000_wide_from_the_cropped_part(self):
        w, h, rows = framed(made(halves(5200, 4), crop=[500, 0, 1000, 1000], from_w=5200))
        self.assertEqual(w, 1500)
        self.assertEqual({px for row in rows for px in row}, {BLUE})

    def test_1800_is_left_alone(self):
        body = made(make_png(1800, 2, lambda x, y: GREEN))
        self.assertEqual(framed(body)[:2], (1800, 2))
        self.assertNotIn("from_w", body)

    def test_600_is_not_enlarged_even_when_shaped(self):
        self.assertEqual(framed(made(make_png(600, 100, lambda x, y: GREEN)))[:2], (600, 100))
        self.assertEqual(framed(made(make_png(600, 100, lambda x, y: GREEN), shape="16:9"))[:2], (177, 100))
        self.assertEqual(framed(made(make_png(600, 600, lambda x, y: GREEN), shape="banner"))[:2], (600, 200))

    def test_3000_exactly_is_left_alone(self):
        self.assertEqual(framed(made(make_png(3000, 1, lambda x, y: GREEN)))[:2], (3000, 1))

    def test_the_average_of_the_pixels_is_kept_when_made_smaller(self):
        body = made(make_png(6000, 2, lambda x, y: RED if x % 2 else BLUE))
        px = framed(body)[2][0][5]
        self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(px, (127, 0, 127))), px)

    def test_a_jpeg_or_webp_is_used_as_it_is_when_nothing_is_cut(self):
        j = sized_jpeg(1800)
        self.assertEqual(made(j)["pictures"], {"original": j, "image": j})
        self.assertEqual(made(GOOD_WEBP)["pictures"]["image"], GOOD_WEBP)

    def test_a_jpeg_cannot_be_cut_and_a_wide_one_is_refused(self):
        with self.assertRaises(Bad) as e:
            made(sized_jpeg(1800), crop=[0, 0, 500, 1000])
        self.assertEqual(str(e.exception), fi.CANT_FRAME)
        wide = sized_jpeg(4000)
        with self.assertRaises(Bad) as e:
            fi.with_picture({"v": 2}, "original", wide)
        self.assertEqual(str(e.exception), fi.TOO_WIDE)


class Refusals(unittest.TestCase):
    def test_camera_details_and_wrong_types_are_refused(self):
        for bad, words in ((EXIF, fi._say_image(CAMERA_DETAILS)), ("data:image/gif;base64,R0lGODlhAQABAAAAACw=", fi._say_image(NOT_A_PICTURE)),
                           (make_png(4, 4, lambda x, y: RED, extra=(b"eXIf", b"MM\x00*x")), fi._say_image(CAMERA_DETAILS))):
            with self.assertRaises(Bad) as e:
                fi.check({"v": 2, "pictures": {"original": bad}}, None)
            self.assertEqual(str(e.exception), words)

    def test_a_version_2_refusal_says_image_and_version_1_keeps_its_words(self):
        said = []
        for bad in (EXIF, "data:image/gif;base64,R0lGODlhAQABAAAAACw="):
            with self.assertRaises(Bad) as e:
                fi.check({"v": 2, "pictures": {"original": bad}}, None)
            said.append(str(e.exception))
        self.assertEqual(said[1], "That image can't be used. Add a PNG, JPEG or WebP image.")
        with self.assertRaises(Bad) as e:
            fi.check({"v": 2, "pictures": {"2": GOOD_JPEG}}, None)
        said.append(str(e.exception))
        for words in said:
            self.assertNotIn("picture", words.lower())
            self.assertIn("image", words)
        with self.assertRaises(Bad) as e:
            fi.check({"v": 1, "pictures": {"image": "data:image/gif;base64,R0lGODlhAQABAAAAACw="}}, None)
        self.assertEqual(str(e.exception), NOT_A_PICTURE)           # version 1: the old string, unchanged
        self.assertEqual(NOT_A_PICTURE, "That picture can't be used. Add a PNG, JPEG or WebP picture.")

    def test_a_version_1_body_between_its_limit_and_the_new_limit_is_refused_by_the_old_limit(self):
        from clark.section_kinds.textimage import BIG_PICTURE
        self.assertEqual(fi.V1_LIMIT, 1600 * 1024)
        self.assertEqual(fi.LIMIT, 8454144)
        for size in (fi.V1_LIMIT + 1, 4 * 1024 * 1024, fi.LIMIT - 1024):
            body = {"v": 1, "pictures": {"image": "data:image/png;base64," + "A" * (size - 100)}}
            with self.assertRaises(Bad) as e:
                fi.check(body, None)
            self.assertEqual(str(e.exception), BIG_PICTURE, size)
        from _pictures import check
        from clark import store as store_module
        with self.assertRaises(store_module.Invalid):
            check("imagecap", {"v": 1, "pictures": {"image": "data:image/png;base64," + "A" * (3 * 1024 * 1024)}})
        self.assertEqual(fi.check({"v": 1, "pictures": {"image": GOOD_JPEG}}, None)["pictures"]["image"], GOOD_JPEG)

    def test_the_route_checks_a_big_send_by_this_types_limit(self):
        from clark.section_kinds.textimage import picture
        self.assertEqual(picture(GOOD_JPEG, fi.PICTURE_MAX), GOOD_JPEG)
        self.assertGreater(fi.PICTURE_MAX, 1024 * 1024)

    def test_the_framed_copy_is_never_taken_from_a_request(self):
        with self.assertRaises(Bad) as e:
            fi.with_picture({"v": 2}, "image", GOOD_JPEG)
        self.assertEqual(str(e.exception), fi.MADE_HERE)
        with self.assertRaises(Bad) as e:
            fi.with_picture({"v": 2}, "other", GOOD_JPEG)
        self.assertEqual(str(e.exception), fi.MADE_HERE)
        with self.assertRaises(Bad) as e:
            fi.check({"v": 2, "pictures": {"image": GOOD_JPEG}}, None)
        self.assertEqual(str(e.exception), fi.NOT_ALONE)
        with self.assertRaises(Bad) as e:
            fi.check({"v": 2, "pictures": {"2": GOOD_JPEG}}, None)
        self.assertEqual(str(e.exception), fi._say_image(BAD_SLOT))

    def test_the_framing_is_numbers_only(self):
        for bad in ({"shape": "round"}, {"fx": -1}, {"fx": True}, {"fy": 1001}, {"crop": [0, 0, 5, 1000]}, {"crop": [0, 0, 1000]},
                    {"crop": "a.png"}, {"ratio": 2000}, {"shape": "free", "ratio": 5000}, {"shape": "free", "ratio": 249},
                    {"fit": "zoom"}, {"fill": "red"}, {"from_w": 0}, {"file": "a.png"}):
            with self.subTest(bad=bad), self.assertRaises(Bad):
                fi.check({"v": 2, **bad}, None)

    def test_the_most_a_framed_copy_may_take(self):
        noise = make_png(2000, 1000, lambda x, y: ((x * 7 + y * 13) % 256, (x * 31) % 256, (y * 17 + x) % 256))
        with self.assertRaises(Bad):
            with_limits = fi.FRAMED_MAX
            fi.FRAMED_MAX = 1000
            try:
                made(noise, shape="16:9")
            finally:
                fi.FRAMED_MAX = with_limits

    def test_an_interlaced_or_16_bit_png_cannot_be_cut(self):
        raw = bytearray(base64.b64decode(halves(4, 4).split(",")[1]))
        raw[24] = 16
        raw[29:33] = struct.pack(">I", zlib.crc32(bytes(raw[12:29])) & 0xFFFFFFFF)
        with self.assertRaises(Bad):
            made(data(bytes(raw)), shape="banner")

    def test_a_png_with_too_many_pixels_is_refused_before_it_is_read(self):
        raw = bytearray(base64.b64decode(halves(4, 4).split(",")[1]))
        raw[16:24] = struct.pack(">II", 20000, 20000)
        with self.assertRaises(Bad):
            fi._read_png(bytes(raw))


class Stored(unittest.TestCase):
    def test_the_words_are_kept_and_nothing_is_made_again_when_only_they_change(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000])
        again = fi.check({**body, "caption": "  Fictional view "}, None)
        self.assertEqual(again["caption"], "Fictional view")
        self.assertEqual(again["pictures"], body["pictures"])

    def test_a_new_framing_makes_the_copy_again(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000])
        body["crop"] = [0, 0, 500, 1000]
        again = fi.check(body, None)
        self.assertEqual({px for row in framed(again)[2] for px in row}, {RED})

    def test_reset_to_the_whole_image(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000])
        del body["crop"]
        self.assertEqual(framed(fi.check(body, None))[:2], (40, 10))

    def test_taking_the_image_out_takes_both_slots_out(self):
        body = made(make_png(5200, 2, lambda x, y: RED))
        self.assertEqual(body["from_w"], 5200)
        out = fi.with_picture(body, "original", None)
        self.assertNotIn("pictures", out)
        self.assertNotIn("from_w", out)

    def test_a_new_image_replacing_one_starts_from_no_framing_and_the_words_stay(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000], shape="banner", fit="stretch", fill="brand")
        body.update(caption="Fictional view", alt="Two blocks")
        again = fi.with_picture(body, "original", halves(20, 10))
        self.assertEqual({k: v for k, v in again.items() if k != "pictures"}, {"v": 2, "caption": "Fictional view", "alt": "Two blocks"})
        self.assertEqual(framed(again)[:2], (20, 10))
        out = fi.with_picture(body, "original", None)
        self.assertEqual(out, {"v": 2, "caption": "Fictional view", "alt": "Two blocks"})

    def test_the_words_alone_are_kept_when_the_image_goes(self):
        out = fi.with_picture({**made(halves(4, 4)), "caption": "Fictional"}, "original", None)
        self.assertEqual(out["caption"], "Fictional")


class Published(unittest.TestCase):
    def test_no_image_is_not_published(self):
        self.assertIsNone(fi.published({"v": 2}, None))
        self.assertIsNone(fi.published({"v": 2, "caption": "Fictional lonely", "alt": "x"}, None))
        self.assertIsNone(fi.published(None, None))
        self.assertIsNone(fi.published({"v": 2, "pictures": {}}, None))
        body = made(halves(40, 10))
        self.assertIsNone(fi.published(dict(body, pictures={"original": body["pictures"]["original"]}), None))   # no framed copy yet

    def test_a_framed_copy_that_is_not_ours_is_not_published(self):
        body = made(halves(40, 10), crop=[500, 0, 1000, 1000])
        stale = dict(body, crop=[0, 0, 500, 1000])                              # framing changed without the copy being made again
        self.assertIsNone(fi.published(stale, None))
        swapped = dict(body, pictures={"original": body["pictures"]["original"], "image": body["pictures"]["original"]})
        self.assertIsNone(fi.published(swapped, None))
        self.assertIsNone(fi.published(dict(body, pictures={"image": body["pictures"]["image"]}), None))
        self.assertIsNone(fi.published(dict(body, crop="a.png"), None))

    def test_the_words_and_the_look_go_with_the_image(self):
        body = made(halves(40, 10), fit="stretch", fill="plain")
        body.update(caption="Fictional view", alt="Two blocks")
        got = fi.published(body, None)["content"]
        self.assertEqual((got["caption"], got["alt"], got["fit"], got["fill"]), ("Fictional view", "Two blocks", "stretch", "plain"))
        self.assertEqual(fi.published(made(halves(40, 10)), None)["content"]["caption"], "")

    def test_the_module_keeps_the_contract(self):
        self.assertTrue(fi.READY)
        self.assertEqual(fi.EMPTY, "")
        self.assertGreater(fi.LIMIT, (fi.ORIGINAL_MAX + fi.FRAMED_MAX) * 4 // 3)


class Version1(unittest.TestCase):
    """The old Image with caption body opens, saves and publishes exactly as it did before row 1223."""
    OLD = {"v": 1, "caption": "Fictional plan", "alt": "A plan", "pictures": {"image": GOOD_JPEG}}

    def test_an_old_body_is_checked_to_itself(self):
        self.assertEqual(fi.check(dict(self.OLD), None), self.OLD)
        self.assertEqual(fi.check({"v": 1}, None), {"v": 1})
        self.assertEqual(fi.check({"caption": " x "}, None), {"v": 1, "caption": "x"})      # a body with no version is version 1

    def test_an_old_body_publishes_byte_for_byte_as_before(self):
        self.assertEqual(fi.published(dict(self.OLD), None), {"content": {"image": GOOD_JPEG, "caption": "Fictional plan", "alt": "A plan"}})
        self.assertEqual(list(fi.published(dict(self.OLD), None)["content"]), ["image", "caption", "alt"])
        self.assertIsNone(fi.published({"v": 1, "caption": "only words"}, None))
        self.assertIsNone(fi.published({"v": 1}, None))

    def test_an_old_body_keeps_its_one_slot_and_its_old_size(self):
        self.assertEqual(fi.with_picture(None, "image", GOOD_JPEG), {"v": 1, "pictures": {"image": GOOD_JPEG}})
        self.assertEqual(fi.with_picture(dict(self.OLD), "image", None), {"v": 1, "caption": "Fictional plan", "alt": "A plan"})
        with self.assertRaises(Bad) as e:
            fi.with_picture(None, "original", GOOD_JPEG)
        self.assertEqual(str(e.exception), BAD_SLOT)
        big = data(b"\xff\xd8\xff\xe0" + b"\x00" * (1024 * 1024 + 10), "jpeg")
        with self.assertRaises(Bad):
            fi.with_picture(None, "image", big)             # over the old 1 MiB: refused, though this type now takes more for the new body
        with self.assertRaises(Bad):
            fi.check({"v": 1, "pictures": {"image": big}}, None)

    def test_an_old_body_takes_no_framing_and_no_other_version(self):
        for bad in ({"shape": "banner"}, {"fx": 1}, {"pictures": {"original": GOOD_JPEG}}):
            with self.assertRaises(Bad):
                fi.check({"v": 1, **bad}, None)
        for v in (0, 3, "2", True):
            with self.assertRaises(Bad):
                fi.check({"v": v}, None)

    def test_the_new_body_starts_empty_and_is_not_published(self):
        self.assertEqual(fi.check({"v": 2}, None), {"v": 2})
        self.assertEqual(fi.START, '{"v":2}')
        self.assertIsNone(fi.published({"v": 2}, None))
        self.assertEqual(fi.published(made(halves(8, 4)), None)["content"]["full"], 1)


class Limits(unittest.TestCase):
    def test_the_limits_row_1223_states(self):
        mib = 1024 * 1024
        self.assertEqual((fi.PICTURE_MAX, fi.ORIGINAL_MAX, fi.FRAMED_MAX, fi.WIDTH_MAX), (8 * mib, 3 * mib, 3 * mib, 3000))
        self.assertEqual(fi.LIMIT, 6 * mib * 4 // 3 + 64 * 1024)
        self.assertLessEqual(fi.FRAMED_MAX * 4 // 3, 4 * mib, "one framed copy in base64 leaves a published page its 5 MiB for the rest")

    def test_the_server_route_takes_what_this_type_may_send(self):
        from clark import server
        self.assertEqual(server.IMAGE_FILE_MB * 1024 * 1024, fi.PICTURE_MAX)
        self.assertGreater(server.ROUTE_BODY_LIMITS["/api/section-image"], fi.PICTURE_MAX * 4 // 3 + server.REQUEST_ENVELOPE)
        self.assertGreater(server.BODY_LIMIT, 0)

    def test_the_stored_body_limit_is_this_types(self):
        from clark import section_bodies
        self.assertEqual(section_bodies.LIMITS["imagecap"], fi.LIMIT)


if __name__ == "__main__":
    unittest.main()
