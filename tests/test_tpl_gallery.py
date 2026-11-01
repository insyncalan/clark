"""#96 Image gallery (store type 'gallery'): six slots, each picture with its caption and description; its checker, what it
publishes (the pictures in slot order; nothing until there is one), its pictures through R1's route (one step, one Undo; taking a
picture out takes its caption too; the words keep every picture), the file and the served View, and the page. The picture rules
and the route itself are tested in test_tpl_textimage.py.

Run: python3 dev/run_tests.py test_tpl_gallery
Needs Chrome (the #33 harness) for the page tests. Fictional data only.
"""
import json
import unittest

from _pictures import GOOD, GOOD_JPEG, GOOD_WEBP, PictureSteps, check, data, jpeg, published
from _pictures_cases import PicturePage
from _pictures_page import BarePage
from clark import changes, store as store_module
from clark.section_kinds import gallery, textimage
from test_changes import Api
from test_server import chrome  # noqa: F401  (a browser file: its page tests drive Chrome through _pictures_cases)

KIND = "gallery"


class Checker(unittest.TestCase):
    def test_its_fields_and_nothing_else(self):
        got = check(KIND, {"v": 1, "items": {"2": {"caption": " Fictional hall ", "alt": ""}, "3": {}}, "pictures": {"2": GOOD}})
        self.assertEqual(got, {"v": 1, "items": {"2": {"caption": "Fictional hall"}}, "pictures": {"2": GOOD}})
        for bad, words in (({"v": 1, "items": {"7": {"caption": "x"}}}, textimage.BAD_SLOT),
                           ({"v": 1, "pictures": {"0": GOOD}}, textimage.BAD_SLOT),
                           ({"v": 1, "items": {"1": {"caption": "x", "href": "https://example.org"}}}, textimage.UNKNOWN_FIELD),
                           ({"v": 1, "items": {"1": "x"}}, textimage.NOT_CONTENT),
                           ({"v": 1, "items": ["x"]}, textimage.NOT_CONTENT),
                           ({"v": 1, "pictures": {"1": data(jpeg(pad=gallery.PICTURE_MAX), "jpeg")}}, textimage.BIG_PICTURE)):
            with self.assertRaises(store_module.Invalid) as e:
                check(KIND, bad)
            self.assertEqual(str(e.exception), words)
        self.assertTrue(gallery.READY)
        self.assertGreaterEqual(gallery.LIMIT, 6 * ((gallery.PICTURE_MAX + 2) // 3 * 4) + textimage.TEXT_LIMIT // 2, "six pictures fit")

    def test_published_lists_the_pictures_in_slot_order(self):
        self.assertIsNone(published(KIND, {"v": 1, "items": {"1": {"caption": "Fictional"}}}))
        got = published(KIND, {"v": 1, "items": {"1": {"caption": "One"}, "5": {"caption": "Five", "alt": "A five"}},
                               "pictures": {"5": GOOD_JPEG, "2": GOOD}})
        self.assertEqual(got, {"content": {"pictures": [{"image": GOOD, "caption": "", "alt": ""},
                                                        {"image": GOOD_JPEG, "caption": "Five", "alt": "A five"}]}})


class Route(PictureSteps, Api):
    def test_each_picture_is_one_step_and_taking_one_out_takes_its_caption(self):
        ref = self.made(KIND)
        for slot, pic in (("1", GOOD), ("2", GOOD_JPEG), ("3", GOOD_WEBP)):
            self.assertEqual(self.put(ref, slot, pic)[0], 200)
        self.assertEqual(self.words(ref, {"v": 1, "items": {"1": {"caption": "Fictional one"}, "2": {"caption": "Fictional two"}}})[0], 200)
        self.assertEqual(sorted(self.body(ref)["pictures"]), ["1", "2", "3"], "the words kept every picture")
        before = self.body(ref)
        status, got = self.put(ref, "2", None)
        self.assertEqual(status, 200, got)
        self.assertEqual(self.body(ref), {"v": 1, "items": {"1": {"caption": "Fictional one"}}, "pictures": {"1": GOOD, "3": GOOD_WEBP}})
        self.undone(got["apply_id"])
        self.assertEqual(self.body(ref), before, "one Undo puts the picture and its caption back")
        self.assertEqual(self.put(ref, "7", GOOD)[1]["message"], textimage.BAD_SLOT)
        self.assertEqual(self.put(ref, "image", GOOD)[1]["message"], textimage.BAD_SLOT)

    def test_in_the_file_only_with_a_picture_and_never_when_hidden(self):
        shown = self.made(KIND, "Fictional gallery")
        self.put(shown, "4", GOOD)
        self.words(shown, {"v": 1, "items": {"4": {"caption": "Fictional caption"}, "1": {"caption": "Fictional no picture"}}})
        bare = self.made(KIND, "Fictional bare")
        self.words(bare, {"v": 1, "items": {"1": {"caption": "Fictional lonely caption"}}})
        hidden = self.made(KIND, "Fictional hidden")
        self.put(hidden, "1", GOOD_JPEG)
        self.ok(changes.UPDATE, id=hidden, changes={"hidden": 1})
        sections, text = self.file()
        self.assertEqual(sections[shown]["content"], {"pictures": [{"image": GOOD, "caption": "Fictional caption", "alt": ""}]})
        self.assertNotIn(bare, sections)
        self.assertNotIn(hidden, sections)
        for marker in ("Fictional lonely caption", "Fictional no picture", GOOD_JPEG.split(",")[1]):
            self.assertNotIn(marker, text)


class Parity(BarePage):
    def test_the_page_shows_what_publish_publishes(self):
        self.assertTrue(self.val("P.ready.gallery"))
        self.parity(KIND, [{"v": 1}, {"v": 1, "items": {"1": {"caption": "Fictional"}}}, {"v": 1, "pictures": {"3": GOOD}},
                           {"v": 1, "items": {"6": {"caption": "Six", "alt": "A"}}, "pictures": {"6": GOOD_JPEG, "1": GOOD}}])


class InThePage(PicturePage):
    KIND = KIND

    def test_view_and_edit(self):
        full = self.add({"v": 1, "items": {"1": {"caption": "Fictional one"}, "2": {"caption": "Fictional two", "alt": "Two"}},
                         "pictures": {"1": GOOD, "2": GOOD_JPEG, "3": GOOD_WEBP}})
        ref = self.add(title="Fictional new")
        with self.chrome() as cdp:
            p = self.visit(cdp)
            sel = f"[data-id={json.dumps(full)}]"
            p.until(f"document.querySelectorAll('{sel} .tpl-gal img').length === 3", "View draws three pictures")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} figcaption')].map(e => e.textContent)"), ["Fictional one", "Fictional two"])
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}]')"), "no picture: not in View")
            self.at_widths(cdp, p, sel, "img")
            p.edit()
            new = f"[data-id={json.dumps(ref)}]"
            p.until(f"document.querySelectorAll('{new} .tpl-slot').length === 1", "one free slot")
            self.drop_file(p, f"{new} .tpl-slot[data-slot=\"1\"] input[type=file]", 2000, 1500)
            p.saved()
            pic = self.body(ref)["pictures"]["1"]
            self.assertLessEqual(max(self.width_of(pic) or 0, 0), 1200, "a gallery picture is at most 1200 px")
            p.until(f"document.querySelectorAll('{new} .tpl-slot').length === 2", "the next slot is offered")
            p.clear_toast()
            p.js(f"document.querySelector('{new} input[id$=-caption-1]').focus()")
            p.type("Fictional caption")
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            self.assertEqual(self.body(ref)["items"], {"1": {"caption": "Fictional caption"}})
            self.assertEqual(self.body(ref)["pictures"], {"1": pic})


if __name__ == "__main__":
    unittest.main()
