"""Row 1232, Text and Image Side by Side: its Edit toolbar in the page (a textimage section with a body of version 2): Shape, Position (this width's
two choices, then Swap), Image width (full width only), Replace and Remove, the heading box, and the names. Each choice is one saved change with one
Undo; each width keeps its own choice. At 1400 and 900 px wide. An older (version 1) section keeps its own Edit part. Not here yet (later slices):
Crop and Reset, the focus dot, the arrow keys on the dot, the Word export.

Run: CLARK_CHROME=${CREAITE_CHROME:-/usr/local/bin/creaite-chrome} python3 dev/run_tests.py test_tpl_textimage_side_edit
Needs Chrome (the #33 harness). Fictional data only.
"""
import json
import sqlite3
import unittest

from _demo import USER
from _pictures import GOOD
from clark import changes
from test_report_editor import Base as PageBase
from test_server import chrome

KIND = "textimage"
WORDS = "<p>Fictional site visit on Tuesday.</p>"
NAMES_FULL = ["Fill the height of the text", "Shape 4:3", "Shape square", "Whole image", "Image on the left", "Image on the right", "Swap image and text",
              "Image takes a third", "Image takes a half", "Image takes two thirds", "Replace the image", "Remove the image"]
NAMES_HALF = ["Wide (16:9)", "Shape 4:3", "Shape square", "Whole image", "Image on top", "Image underneath", "Swap image and text",
              "Replace the image", "Remove the image"]


class SideBySideEdit(PageBase):
    def setUp(self):
        super().setUp()
        self.s.httpd.section_image = changes.make_section_image(self.store.path, [], USER)

    def add(self, body, title="Fictional site visit", beside=0, order=999):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": KIND, "title": title, "sort_order": order, "hidden": 0, "beside": beside})
            st.update("report_sections", ref, {"body": json.dumps(body)})
        return ref

    def body(self, ref):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["id"] == ref)
        return json.loads(row["body"]) if row["body"] else {}

    def applies(self):
        con = sqlite3.connect(str(self.store.path))
        try:
            return con.execute("SELECT count(*) FROM applies").fetchone()[0]
        finally:
            con.close()

    def with_image(self, **kw):
        return {"v": 2, "html": WORDS, "alt": "Fictional hall", "pictures": {"original": GOOD, "image": GOOD}, **kw}

    def open_edit(self, cdp, ref):
        p = self.visit(cdp)
        p.edit()
        sel = f"[data-id={json.dumps(ref)}]"
        p.until(f"!!document.querySelector('{sel} .ti-bar')", "the toolbar is drawn")
        return p, sel

    def names(self, p, sel):
        return p.js(f"[...document.querySelectorAll('{sel} .ti-bar button')].map(b => b.getAttribute('aria-label'))")

    def click(self, p, sel, act):
        p.js(f"document.querySelector('{sel} .ti-bar [data-act={act}]').click()")
        p.saved()

    def test_full_width_offers_left_and_right_and_the_three_widths_and_never_top_or_bottom(self):
        ref = self.add(self.with_image())
        with chrome() as cdp:
            p, sel = self.open_edit(cdp, ref)
            self.assertEqual(self.names(p, sel), NAMES_FULL)
            self.assertEqual(p.js(f"document.querySelector('{sel} .ti-bar').getAttribute('aria-label')"), "Image and layout tools")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .ti-bar [role=group]')].map(g => g.getAttribute('aria-label'))"),
                             ["Shape", "Where the image sits"] + ["Image width"])
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .ti-bar [aria-pressed=true]')].map(b => b.getAttribute('aria-label'))"),
                             ["Fill the height of the text", "Image on the right", "Image takes a half"], "the stored defaults are chosen")
            start = self.applies()
            self.click(p, sel, "swap")
            self.assertEqual(self.body(ref)["side"], "left")
            self.assertEqual(self.applies(), start + 1, "one step")
            self.assertEqual(self.body(ref)["html"], WORDS, "the words are kept")
            p.clear_toast()
            self.click(p, sel, "share-third")
            self.assertEqual(self.body(ref)["share"], "third")
            p.clear_toast()
            self.click(p, sel, "shape-square")
            self.assertEqual(self.body(ref)["shape"], "square")
            self.assertEqual(self.applies(), start + 3)
            p.until(f"document.querySelector('{sel} .tpl-sbs').classList.contains('pos-left') && document.querySelector('{sel} .tpl-sbs').classList.contains('share-third')", "the layout follows")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"!document.querySelector('{sel} .tpl-sbs.shape-square')", "one Undo takes the shape back")
            self.assertEqual(self.body(ref)["share"], "third")

    def test_half_width_offers_top_and_underneath_and_no_widths_and_each_width_keeps_its_own_choice(self):
        ref = self.add(self.with_image(side="left"), beside=1)
        self.add({"v": 1, "words": ["Fictional neighbour"]}, "Fictional neighbour", order=1000)
        with chrome() as cdp:
            p, sel = self.open_edit(cdp, ref)
            self.assertEqual(self.names(p, sel), NAMES_HALF)
            self.assertEqual(p.js(f"document.querySelectorAll('{sel} .ti-bar [data-act^=share]').length"), 0)
            self.click(p, sel, "swap")
            self.assertEqual(self.body(ref)["half"], "bottom")
            self.assertEqual(self.body(ref)["side"], "left", "full width keeps its own choice")
            p.clear_toast()
            self.click(p, sel, "pos-top")
            self.assertNotIn("half", self.body(ref), "the default is stored as nothing")
            p.clear_toast()
            self.click(p, sel, "pos-bottom")
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"beside": 0})
        with chrome() as cdp:
            p, sel = self.open_edit(cdp, ref)
            self.assertEqual(self.names(p, sel), NAMES_FULL)
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .ti-bar [aria-pressed=true]')].map(b => b.getAttribute('aria-label'))")[1], "Image on the left", "full left, half bottom, back to full: still left")
            self.assertEqual(self.body(ref)["half"], "bottom")

    def test_every_icon_has_a_name_on_hover_and_focus_and_the_arrow_keys_move_along_the_bar(self):
        ref = self.add(self.with_image())
        with chrome() as cdp:
            p, sel = self.open_edit(cdp, ref)
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .ti-bar button')].filter(b => !b.getAttribute('aria-label') || b.dataset.tip !== b.getAttribute('aria-label')).length"), 0)
            self.assertEqual(p.js(f"document.querySelectorAll('{sel} .ti-bar button[tabindex=\"0\"]').length"), 1, "one tab stop")
            p.js(f"document.querySelector('{sel} .ti-bar button').focus()")
            p.key("ArrowRight", code="ArrowRight", vk=39)
            self.assertEqual(p.js("document.activeElement.getAttribute('aria-label')"), "Shape 4:3")
            self.assertEqual(p.js("getComputedStyle(document.activeElement, '::after').opacity"), "1", "the name shows on focus")
            p.key("ArrowLeft", code="ArrowLeft", vk=37)
            p.key("ArrowLeft", code="ArrowLeft", vk=37)
            self.assertEqual(p.js("document.activeElement.getAttribute('aria-label')"), "Remove the image", "the bar wraps round")

    def test_heading_saves_and_remove_takes_the_image_out_and_the_words_stay(self):
        ref = self.add(self.with_image())
        with chrome() as cdp:
            p, sel = self.open_edit(cdp, ref)
            self.assertEqual(p.js(f"document.querySelector('{sel} label[for$=heading]').textContent"), "Headingoptional")
            p.js(f"var i = document.querySelector('{sel} #tpl-{ref}-heading'); i.focus(); i.value = 'Fictional heading'; i.blur(); true")
            p.saved()
            self.assertEqual(self.body(ref)["heading"], "Fictional heading")
            p.clear_toast()
            self.assertFalse(p.js(f"!!document.querySelector('{sel} [data-alt-note]')"), "a description is there")
            self.click(p, sel, "remove")
            self.assertNotIn("image", self.body(ref).get("pictures", {}))
            self.assertEqual(self.body(ref)["html"], WORDS)
            p.until(f"!document.querySelector('{sel} .ti-bar') && !!document.querySelector('{sel} [data-act=pick]')", "the drop area is back")

    def test_no_description_says_so_and_the_edit_fits_at_1400_and_900(self):
        ref = self.add(self.with_image(alt=""))
        with chrome() as cdp:
            p, sel = self.open_edit(cdp, ref)
            self.assertEqual(p.js(f"document.querySelector('{sel} [data-alt-note]').textContent"), "No description yet.")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                fits = p.js(f"(function(){{var s=document.querySelector('{sel}'), r=s.getBoundingClientRect();"
                            "return [s.scrollWidth, s.clientWidth, ...[...s.querySelectorAll('.tpl-edit input:not([type=file]), .ti-bar, .tpl-sbs-frame')]"
                            ".map(e => {var i=e.getBoundingClientRect(); return [e.className, Math.round(i.left - r.left), Math.round(r.right - i.right)];})];})()")
                self.assertTrue(fits[0] <= fits[1] + 1 and all(a >= -1 and b >= -1 for _, a, b in fits[2:]), (width, fits))
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            box = p.js(f"(function(){{var b=document.querySelector('{sel} .ti-bar button').getBoundingClientRect(), r=document.querySelector('{sel} .ti-bar').getBoundingClientRect();"
                       f"return {{w: b.width, h: b.height, gap: getComputedStyle(document.querySelector('{sel} .ti-bar')).columnGap, radius: getComputedStyle(document.querySelector('{sel} .ti-bar')).borderTopLeftRadius}};}})()")
            self.assertEqual((box["w"], box["h"], box["gap"], box["radius"]), (32, 30, "2px", "10px"), "the approved measures")

    def test_an_older_section_keeps_its_own_edit_part(self):
        ref = self.add({"v": 1, "html": WORDS})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sel = f"[data-id={json.dumps(ref)}]"
            p.until(f"!!document.querySelector('{sel} .tpl-ti-edit')", "the Edit part")
            self.assertTrue(p.js(f"!!document.querySelector('{sel} .tpl-side')"), "the old Right and Left choice")
            self.assertFalse(p.js(f"!!document.querySelector('{sel} .ti-bar')"))


if __name__ == "__main__":
    unittest.main()
