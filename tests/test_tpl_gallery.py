"""#96 Image gallery (store type 'gallery'): six slots, each picture with its caption and description; its checker, what it
publishes (the pictures in slot order; nothing until there is one), its pictures through R1's route (one step, one Undo; taking a
picture out takes its caption too; the words keep every picture), the file and the served View, and the page. The picture rules
and the route itself are tested in test_tpl_textimage.py.

Run: python3 dev/run_tests.py test_tpl_gallery
Needs Chrome (the #33 harness) for the page tests. Fictional data only.
"""
import json
import unittest

from _classic_page import classic
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
                           ({"v": 1, "pictures": {"1": data(jpeg(pad=gallery.V1_PICTURE_MAX), "jpeg")}}, textimage.BIG_PICTURE)):
            with self.assertRaises(store_module.Invalid) as e:
                check(KIND, bad)
            self.assertEqual(str(e.exception), words)
        self.assertTrue(gallery.READY)
        self.assertGreaterEqual(gallery.LIMIT, 6 * ((gallery.V1_PICTURE_MAX + 2) // 3 * 4) + textimage.TEXT_LIMIT // 2, "six pictures fit")

    def test_published_lists_the_pictures_in_slot_order(self):
        self.assertIsNone(published(KIND, {"v": 1, "items": {"1": {"caption": "Fictional"}}}))
        got = published(KIND, {"v": 1, "items": {"1": {"caption": "One"}, "5": {"caption": "Five", "alt": "A five"}},
                               "pictures": {"5": GOOD_JPEG, "2": GOOD}})
        self.assertEqual(got, {"content": {"pictures": [{"image": GOOD, "caption": "", "alt": ""},
                                                        {"image": GOOD_JPEG, "caption": "Five", "alt": "A five"}]}})


    def test_the_body_a_new_gallery_starts_with_is_taken_as_it_is(self):
        """Row 1233 (AP19, ticket test 11): the catalogue starts a new gallery as {"v":2}; the model and the store take that empty version 2 body."""
        self.assertEqual(gallery.check({"v": 2}, None), {"v": 2})
        self.assertEqual(json.loads(store_module.check_section_body("gallery", '{"v":2}')), {"v": 2})
        self.assertIsNone(gallery.published({"v": 2}, None), "no picture: nothing in the report")


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
            p.until(f"document.querySelectorAll('{new} .tpl-pic-slot').length === 1", "one free slot")
            self.drop_file(p, f"{new} .tpl-pic-slot[data-slot=\"1\"] input[type=file]", 2000, 1500)
            p.saved()
            pic = self.body(ref)["pictures"]["1"]
            self.assertLessEqual(max(self.width_of(pic) or 0, 0), 1200, "a gallery picture is at most 1200 px")
            p.until(f"document.querySelectorAll('{new} .tpl-pic-slot').length === 2", "the next slot is offered")
            p.clear_toast()
            p.js(f"document.querySelector('{new} [data-rich=caption]').click()")
            p.until(f"!!document.querySelector('{new} .ProseMirror')", "the caption opens on the one editor (item 1005)")
            p.js(f"document.querySelector('{new} .ProseMirror').cxed.editor.commands.insertContent('Fictional caption'); true")
            p.key("Enter", 4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
            p.saved()
            self.assertEqual(self.body(ref)["items"], {"1": {"caption": "<p>Fictional caption</p>"}})
            self.assertEqual(self.body(ref)["pictures"], {"1": pic})

    def test_t11_two_half_width_galleries_pair_side_by_side_at_1400_and_stack_at_900(self):
        """Row 1233 (AP19, ticket test 11, the page half): on the Classic page two half-width galleries share a row at 1400 and stack at 900."""
        a = self.add({"v": 2, "pictures": {"1": GOOD}}, title="Fictional left")
        b = self.add({"v": 2, "pictures": {"1": GOOD}}, title="Fictional right")
        sa, sb = f"[data-id={json.dumps(a)}]", f"[data-id={json.dumps(b)}]"
        classic(self)
        with self.chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sa} .tpl-gal img') && !!document.querySelector('{sb} .tpl-gal img')", "both galleries drawn")
            self.assertTrue(p.js("!!document.getElementById('theme')"), "the Classic page")
            p.js(f"""(() => {{ const x = document.querySelector('{sa}'), y = document.querySelector('{sb}');
              x.className = x.className.replace(/slot-\\w+/, 'slot-left'); y.className = y.className.replace(/slot-\\w+/, 'slot-right'); x.parentNode.insertBefore(x, y); return true; }})()""")
            rect = f"(() => {{ const r = e => document.querySelector(e).getBoundingClientRect(); const x = r('{sa}'), y = r('{sb}'); return {{xl: x.left, xr: x.right, xt: x.top, xb: x.bottom, yl: y.left, yt: y.top, side: document.documentElement.scrollWidth - document.documentElement.clientWidth}}; }})()"
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until(f"window.innerWidth === {width}", "the width is set")
                m = p.js(rect)
                self.assertLessEqual(m["side"], 0, (width, "no sideways scroll"))
                if width == 1400:
                    self.assertAlmostEqual(m["xt"], m["yt"], delta=2, msg="same row")
                    self.assertGreater(m["yl"], m["xr"] - 1, "the second sits right of the first")
                else:
                    self.assertGreaterEqual(m["yt"], m["xb"] - 1, "the second sits below the first")
                    self.assertAlmostEqual(m["xl"], m["yl"], delta=2, msg="stacked: the same left edge")


if __name__ == "__main__":
    unittest.main()
