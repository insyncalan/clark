"""Row 1233 slice 3 (AP8, AP15, AP16, AP18 page half): taking an image out of the Image gallery's Edit page (Classic), at 1400 and 900 px, in the
same real-browser harness as test_tpl_gallery_edit.py (bare page, stand-in routes, tests/fixtures/gallery_edit_demo.jsx). What clark's server
does with a removal is test_gallery_v2_server.py.

Run: python3 dev/run_tests.py test_tpl_gallery_edit_remove
Needs Chrome (the #33 harness): fails, never skips, without it. Fictional data only.
"""
import base64
import json
import time
import unittest

from clark.section_kinds import gallery
from test_tpl_gallery_edit import ADD, FULL, PIC, Page, many

WORDS_ITEMS = {"1": {"caption": "Fictional one", "alt": "A room"}, "2": {"caption": "Fictional two", "alt": "A hall"}, "3": {"caption": "Fictional three", "alt": "A yard"}}
BIN = ".tpl-gal-tile[data-slot='{}'] .tpl-gal-del"


def png_width(data_url):
    return int.from_bytes(base64.b64decode(data_url.split(",", 1)[1])[16:20], "big")


class Remove(Page):        # AP8: the bin on the image
    def test_bin_is_26_square_radius_7_6px_in_white_on_dark_and_red_on_hover(self):
        for page in (1400, 900):
            with self.subTest(page):
                self.mount(many(3), page)
                self.assertEqual(self.style(BIN.format(2), "width", "height", "borderTopLeftRadius", "top", "right", "position", "color", "backgroundColor"),
                                 ["26px", "26px", "7px", "6px", "6px", "absolute", "rgb(255, 255, 255)", "rgba(6, 47, 58, 0.78)"])
                self.assertEqual(self.val(f"(function(){{ const s = document.querySelector({json.dumps(BIN.format(2) + ' svg')}); const r = s.getBoundingClientRect(); return [r.width, r.height, getComputedStyle(s).strokeWidth]; }})()"), [15, 15, "1.8px"])
                self.assertEqual(self.val(f"document.querySelector({json.dumps(BIN.format(2))}).getAttribute('aria-label')"), "Remove image 2")
                self.assertEqual(self.val(f"document.querySelector({json.dumps(BIN.format(2))}).title"), "Remove this image")
                tile = self.val("(function(){const r = document.querySelector(\".tpl-gal-tile[data-slot='2']\").getBoundingClientRect(); return [r.top, r.right];})()")
                bin_ = self.val(f"(function(){{const r = document.querySelector({json.dumps(BIN.format(2))}).getBoundingClientRect(); return [r.top, r.right];}})()")
                self.assertEqual([round(bin_[0] - tile[0]), round(tile[1] - bin_[1])], [8, 8], "6px inside the 2px border")
                self.assertEqual(self.style(BIN.format(1), "opacity"), ["1"], "the selected image shows it")
                self.assertEqual(self.style(BIN.format(2), "opacity"), ["0"], "an unselected one shows it on hover only")
                x, y = self.val(f"(function(){{const r = document.querySelector(\".tpl-gal-tile[data-slot='2']\").getBoundingClientRect(); return [r.left + r.width / 2, r.top + 20];}})()")
                self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, self.sid)
                self.until(f"getComputedStyle(document.querySelector({json.dumps(BIN.format(2))})).opacity === '1'", "hover shows the bin")
                bx, by = self.val(f"(function(){{const r = document.querySelector({json.dumps(BIN.format(2))}).getBoundingClientRect(); return [r.left + 13, r.top + 13];}})()")
                self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": bx, "y": by}, self.sid)
                self.until(f"getComputedStyle(document.querySelector({json.dumps(BIN.format(2))})).backgroundColor === 'rgb(179, 57, 47)'", "hover on the bin is the Classic red token")
                self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 2, "y": 2}, self.sid)

    def test_remove_takes_the_caption_and_description_with_it_and_undo_brings_everything_back(self):
        for page in (1400, 900):
            with self.subTest(page):
                start = {"v": 2, "items": WORDS_ITEMS, "pictures": {"1": PIC, "2": PIC, "3": PIC}}
                self.mount(json.dumps(start), page)
                self.val(f"document.querySelector({json.dumps(BIN.format(2))}).click()")
                self.until("document.querySelectorAll('.tpl-gal-tile').length === 2", "taken out")
                got = self.body()
                self.assertEqual(sorted(got["pictures"]), ["1", "3"])
                self.assertEqual(got["items"], {"1": WORDS_ITEMS["1"], "3": WORDS_ITEMS["3"]}, "its caption and description went with it")
                self.assertEqual([c["slot"] for c in self.calls() if c["path"] == "/api/section-image"], ["2"], "one step")
                self.until("(F.toast() || {}).text === 'Image removed.'", "said")
                self.val("F.undo(F.toast().undo)", True)
                self.until("document.querySelectorAll('.tpl-gal-tile').length === 3", "back")
                self.assertEqual(self.body(), start, "the image, caption and description are back exactly")

    def test_a_version_1_body_stays_version_1_and_valid_after_a_removal(self):
        v1 = {"v": 1, "items": {"1": {"caption": "Fictional", "alt": "A room"}, "2": {"caption": "Second", "alt": "B"}}, "pictures": {"1": PIC, "2": PIC}}
        self.mount(json.dumps(v1))
        self.val(f"document.querySelector({json.dumps(BIN.format(1))}).click()")
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 1", "taken out")
        got = self.body()
        self.assertEqual(got["v"], 1, "a removal needs no version 2 field")
        self.assertEqual(got["items"], {"2": v1["items"]["2"]})
        self.assertEqual(gallery.check(got, None)["v"], 1, "still a valid version 1 body")

    def test_the_bin_leaves_focus_on_the_next_image_the_one_before_the_add_tile_or_the_empty_area(self):
        self.mount(many(3))
        self.val(f"document.querySelector({json.dumps(BIN.format(2))}).click()")
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 2", "gone")
        self.until("document.activeElement && document.activeElement.dataset.slot === '3'", "focus on the next image")
        self.val(f"document.querySelector({json.dumps(BIN.format(3))}).click()")
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 1", "gone")
        self.until("document.activeElement && document.activeElement.dataset.slot === '1'", "the last one: focus on the one before")
        self.assertEqual(self.text(".tpl-gal-fields label"), "Selected image 1: describe it for people who cannot see it")
        self.val(f"document.querySelector({json.dumps(BIN.format(1))}).click()")
        self.until("document.querySelector('.tpl-gal-empty')", "the empty area is back (the section stays)")
        self.until("document.activeElement && document.activeElement.classList.contains('tpl-gal-empty')", "focus on the empty area")

    def test_the_bin_takes_a_key_press_and_does_not_select_instead(self):
        self.mount(many(3))
        self.val("document.querySelector(\".tpl-gal-tile[data-slot='1']\").click()")
        self.assertFalse(self.val(f"(function(){{ const e = new KeyboardEvent('keydown', {{key: 'Enter', bubbles: true, cancelable: true}}); document.querySelector({json.dumps(BIN.format(3))}).dispatchEvent(e); return e.defaultPrevented; }})()"),
                         "the tile's own key handler leaves a key on the bin alone")
        self.assertEqual(self.count(".tpl-gal-tile.sel[data-slot='1']"), 1)


class Toast(Page):         # AP15
    def test_the_removal_message_has_undo_and_goes_after_5_seconds(self):
        for page in (1400, 900):
            with self.subTest(page):
                self.mount(many(3), page)
                self.val(f"document.querySelector({json.dumps(BIN.format(3))}).click()")
                self.until("F.toast()", "said")
                t0 = time.monotonic()
                self.assertEqual(self.toast_text(), "Image removed.")
                self.assertTrue(self.val("!!F.toast().undo"), "with Undo")
                self.until("!F.toast()", "goes", 9)
                self.assertTrue(4.5 <= time.monotonic() - t0 <= 6.5, time.monotonic() - t0)


class Six(Page):           # AP16 (the refusal itself is test_tpl_gallery_edit.py; here at 900 and after a removal)
    def test_the_seventh_is_refused_at_both_widths_and_a_removal_makes_room(self):
        for page in (1400, 900):
            with self.subTest(page):
                self.mount(many(6), page)
                self.assertEqual(self.count(".tpl-gal-add"), 0)
                self.val("add(1)", True)
                self.until("F.toast()", "said")
                self.assertEqual(self.toast_text(), FULL)
                self.assertEqual([c for c in self.calls() if c["path"] == "/api/section-image"], [])
                self.val(f"document.querySelector({json.dumps(BIN.format(2))}).click()")
                self.until("document.querySelectorAll('.tpl-gal-tile').length === 5", "gone")
                self.assertEqual(self.text(".tpl-gal-add"), "+" + ADD, "the add tile is back")

    def test_an_image_added_after_a_removal_goes_at_the_end_of_the_displayed_order(self):
        self.mount(many(6))           # only slot 2 is free: it would show before the last image, so the order is said first
        self.val(f"document.querySelector({json.dumps(BIN.format(2))}).click()")
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 5", "gone")
        self.val("add(1)", True)
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 6", "added")
        self.assertEqual(self.val("[...document.querySelectorAll('.tpl-gal-tile')].map(e => e.dataset.slot)"), ["1", "3", "4", "5", "6", "2"])
        self.assertEqual(self.body()["order"], ["1", "3", "4", "5", "6", "2"])
        self.mount(many(4))           # slots after the last image are free: it goes there, no order needed
        self.val(f"document.querySelector({json.dumps(BIN.format(2))}).click()")
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 3", "gone")
        self.val("add(1)", True)
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 4", "added")
        self.assertEqual(self.val("[...document.querySelectorAll('.tpl-gal-tile')].map(e => e.dataset.slot)"), ["1", "3", "4", "5"])
        self.assertNotIn("order", self.body())
        self.assertEqual(gallery.check(self.body(), None)["v"], 2)

    def test_a_version_1_body_appends_in_a_later_slot_and_stays_version_1(self):
        self.mount(json.dumps({"v": 1, "pictures": {"1": PIC, "2": PIC, "3": PIC}}))
        self.val(f"document.querySelector({json.dumps(BIN.format(2))}).click()")
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 2", "gone")
        self.val("add(1)", True)
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 3", "added")
        self.assertEqual(self.val("[...document.querySelectorAll('.tpl-gal-tile')].map(e => e.dataset.slot)"), ["1", "3", "4"])
        self.assertEqual(self.body()["v"], 1)


class Size(Page):          # AP18, the page half: the copy sent is at most 1,600 px wide and a small one is not enlarged
    def test_a_wide_image_is_sent_at_most_1600_wide_and_a_small_one_as_it_is(self):
        for page in (1400, 900):
            with self.subTest(page):
                self.mount(many(1), page)
                self.val("add(1, 3000, 1000)", True)
                self.until("F.server.calls.length >= 1", "sent")
                self.val("add(1, 200, 150)", True)
                self.until("F.server.calls.length >= 2", "sent")
                sent = [png_width(c["image"]) for c in self.calls()]
                self.assertLessEqual(sent[0], 1600)
                self.assertGreater(sent[0], 1000, "made smaller only as far as the limit asks")
                self.assertEqual(sent[1], 200, "a small image is not enlarged")


if __name__ == "__main__":
    unittest.main()
