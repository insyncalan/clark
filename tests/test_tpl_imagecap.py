"""#96 Image with caption (store type 'imagecap'): its checker, what it publishes (nothing until it has a picture), its picture
through R1's route (one step, one Undo; the words keep it), the file and the served View, and the page. The picture rules and the
route itself are tested in test_tpl_textimage.py.

Run: python3 dev/run_tests.py test_tpl_imagecap
Needs Chrome (the #33 harness) for the page tests. Fictional data only.
"""
import json
import unittest

from _pictures import EXIF, GOOD, GOOD_JPEG, PictureSteps, check, published
from _pictures_cases import PicturePage
from _pictures_page import BarePage
from clark import changes, store as store_module
from clark.section_kinds import imagecap, textimage
from test_changes import Api
from test_server import chrome  # noqa: F401  (a browser file: its page tests drive Chrome through _pictures_cases)

KIND = "imagecap"


class Checker(unittest.TestCase):
    def test_its_fields_and_nothing_else(self):
        self.assertEqual(check(KIND, {"v": 1, "caption": " Fictional plan ", "alt": "A plan", "pictures": {"image": GOOD}}),
                         {"v": 1, "caption": "Fictional plan", "alt": "A plan", "pictures": {"image": GOOD}})
        for bad, words in (({"v": 1, "words": ["x"]}, textimage.UNKNOWN_FIELD), ({"v": 1, "caption": "x" * 301}, textimage.LONG_LINE),
                           ({"v": 1, "pictures": {"image": EXIF}}, textimage.CAMERA_DETAILS),
                           ({"v": 1, "pictures": {"2": GOOD}}, textimage.BAD_SLOT)):
            with self.assertRaises(store_module.Invalid) as e:
                check(KIND, bad)
            self.assertEqual(str(e.exception), words)
        self.assertTrue(imagecap.READY)
        self.assertEqual(imagecap.PICTURE_MAX, textimage.PICTURE_MAX)

    def test_published_waits_for_a_picture(self):
        self.assertIsNone(published(KIND, {"v": 1, "caption": "Fictional", "alt": "Fictional"}))
        self.assertEqual(published(KIND, {"v": 1, "caption": "Fictional plan", "pictures": {"image": GOOD}}),
                         {"content": {"image": GOOD, "caption": "Fictional plan", "alt": ""}})


class Route(PictureSteps, Api):
    def test_one_step_one_undo_and_the_words_keep_the_picture(self):
        ref = self.made(KIND)
        status, got = self.put(ref, "image", GOOD)
        self.assertEqual(status, 200, got)
        self.assertEqual(self.words(ref, {"v": 1, "caption": "Fictional plan"})[0], 200)
        self.assertEqual(self.body(ref), {"v": 1, "caption": "Fictional plan", "pictures": {"image": GOOD}})
        second = self.put(ref, "image", GOOD_JPEG)[1]
        self.undone(second["apply_id"])
        self.assertEqual(self.body(ref)["pictures"], {"image": GOOD})
        self.assertEqual(self.put(ref, "other", GOOD)[1]["message"], textimage.BAD_SLOT)

    def test_in_the_file_only_with_a_picture_and_never_when_hidden(self):
        shown = self.made(KIND, "Fictional plan")
        self.put(shown, "image", GOOD)
        self.words(shown, {"v": 1, "caption": "Fictional caption", "alt": "Fictional plan"})
        bare = self.made(KIND, "Fictional bare")
        self.words(bare, {"v": 1, "caption": "Fictional lonely caption"})
        hidden = self.made(KIND, "Fictional hidden")
        self.put(hidden, "image", GOOD_JPEG)
        self.ok(changes.UPDATE, id=hidden, changes={"hidden": 1})
        sections, text = self.file()
        self.assertEqual(sections[shown]["content"], {"image": GOOD, "caption": "Fictional caption", "alt": "Fictional plan"})
        self.assertNotIn(bare, sections)
        self.assertNotIn(hidden, sections)
        self.assertNotIn("Fictional lonely caption", text)
        self.assertNotIn(GOOD_JPEG.split(",")[1], text)


class Parity(BarePage):
    def test_the_page_shows_what_publish_publishes(self):
        self.assertTrue(self.val("P.ready.imagecap"))
        self.parity(KIND, [{"v": 1}, {"v": 1, "caption": "Fictional"}, {"v": 1, "pictures": {"image": GOOD}},
                           {"v": 1, "caption": "Fictional", "alt": "A", "pictures": {"image": GOOD_JPEG}}])


class InThePage(PicturePage):
    KIND = KIND

    def test_view_and_edit(self):
        full = self.add({"v": 1, "caption": "Fictional caption", "alt": "Fictional plan", "pictures": {"image": GOOD}})
        ref = self.add(title="Fictional new")
        with self.chrome() as cdp:
            p = self.visit(cdp)
            sel = f"[data-id={json.dumps(full)}]"
            p.until(f"!!document.querySelector('{sel} .tpl-cap img')", "View draws the picture")
            self.assertEqual(p.js(f"document.querySelector('{sel} figcaption').textContent"), "Fictional caption")
            self.assertEqual(p.js(f"document.querySelector('{sel} img').alt"), "Fictional plan")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}]')"), "no picture: not in View")
            self.at_widths(cdp, p, sel, "img")
            p.edit()
            new = f"[data-id={json.dumps(ref)}]"
            p.until(f"!!document.querySelector('{new} .tpl-cap-edit')", "the Edit part")
            start = self.applies()
            self.drop_file(p, f"{new} input[type=file]")
            p.saved()
            self.assertEqual(self.applies(), start + 1)
            self.assertEqual(self.width_of(self.body(ref)["pictures"]["image"]), 1600)
            p.clear_toast()
            p.js(f"document.querySelector('{new} input[id$=-caption]').focus()")
            p.type("Fictional new caption")
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            self.assertEqual(self.body(ref)["caption"], "Fictional new caption")
            self.assertIn("pictures", self.body(ref))
            p.clear_toast()
            p.js(f"document.querySelector('{new} [data-act=out]').click()")
            p.saved()
            self.assertEqual(p.toast(), "Picture taken out.")
            self.assertEqual(self.body(ref), {"v": 1, "caption": "Fictional new caption"})
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"!!document.querySelector('{new} .tpl-pic-slot.has-pic')", "Undo put the picture back")


if __name__ == "__main__":
    unittest.main()
