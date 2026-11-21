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
from test_server import chrome, wait

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

    FILE = """(async () => {{
      const c = document.createElement('canvas'); c.width = {w}; c.height = {h};
      const g = c.getContext('2d'); g.fillStyle = 'rgb(40,90,160)'; g.fillRect(0, 0, {w}, {h});
      const blob = await new Promise(r => c.toBlob(r, {kind}));
      const dt = new DataTransfer(); dt.items.add(new File([blob], 'fictional', {{ type: {kind} }}));
      const input = document.querySelector({sel}); input.files = dt.files;
      input.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()"""

    def choose(self, p, sel, w, h, kind="image/png"):
        p.js(self.FILE.format(w=w, h=h, kind=json.dumps(kind), sel=json.dumps(f"{sel} input[type=file]")))

    def test_a_chosen_file_is_added_or_replaced_with_its_own_words_and_a_large_one_keeps_the_width_it_had(self):
        for width in (1400, 900):
            added = self.add({"v": 2, "html": WORDS}, f"Fictional empty {width}")
            ref = self.add(self.with_image(), f"Fictional full {width}")
            with chrome() as cdp:
                p = self.visit(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                a = f"[data-id={json.dumps(added)}]"
                p.until(f"!!document.querySelector('{a} [data-act=pick]')", "the drop area")
                self.choose(p, a, 4000, 1000)
                p.until(f"!!document.querySelector('{a} .ti-bar')", "the image is in")
                self.assertEqual(p.toast(), "Image added.", width)
                self.assertTrue(wait(lambda: self.body(added).get("from_w"), 10), "the second write lands")
                self.assertEqual(self.body(added)["from_w"], 4000, "the width the file had is saved")
                p.clear_toast()
                sel = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector('{sel} .ti-bar')", "the toolbar is drawn")
                self.choose(p, sel, 2400, 1200)
                p.toast_is("Image replaced.")
                self.assertNotEqual(self.body(ref)["pictures"]["original"], GOOD, "the file took the place of the old one")

    def test_a_shape_click_says_the_framing_is_saved_and_a_cut_shape_turns_a_jpeg_original_into_a_png(self):
        for width in (1400, 900):
            ref = self.add(self.with_image(), f"Fictional cut {width}")
            with chrome() as cdp:
                p = self.visit(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                sel = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector('{sel} .ti-bar')", "the toolbar is drawn")
                self.choose(p, sel, 1200, 600, "image/jpeg")
                p.toast_is("Image replaced.")
                p.until(f"!!document.querySelector('{sel} .ti-bar')", "the toolbar is back")
                self.assertTrue(self.body(ref)["pictures"]["original"].startswith("data:image/jpeg"), "a JPEG original")
                p.clear_toast()
                p.js(f"document.querySelector('{sel} .ti-bar [data-act=shape-square]').click()")
                p.toast_is("Image framing saved.")
                self.assertTrue(wait(lambda: self.body(ref).get("shape"), 10), "the choice is saved after the new original")
                got = self.body(ref)
                self.assertEqual(got["shape"], "square")
                self.assertTrue(got["pictures"]["original"].startswith("data:image/png"), "a cut shape is cut from a PNG")

    def test_a_file_that_is_not_an_image_is_refused_and_nothing_is_changed(self):
        for width in (1400, 900):
            ref = self.add({"v": 2, "html": WORDS}, f"Fictional refuse {width}")
            with chrome() as cdp:
                p = self.visit(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                sel = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector('{sel} [data-act=pick]')", "the drop area")
                start = self.applies()
                p.js(f"""(() => {{ const dt = new DataTransfer(); dt.items.add(new File(['fictional'], 'notes.txt', {{ type: 'text/plain' }}));
                  const input = document.querySelector('{sel} input[type=file]'); input.files = dt.files; input.dispatchEvent(new Event('change', {{ bubbles: true }})); }})()""")
                p.toast_is("That file isn't an image that can go in the report. Choose a PNG, JPEG or WebP image.")
                self.assertEqual(self.applies(), start)
                self.assertEqual(self.body(ref), {"v": 2, "html": WORDS})

    def test_the_words_are_sent_without_line_breaks_and_say_text_saved(self):
        for width in (1400, 900):
            ref = self.add(self.with_image(), f"Fictional words {width}")
            with chrome() as cdp:
                p, sel = self.open_edit(cdp, ref)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.js("window.__sent = []; var f = window.fetch; window.fetch = function (u, o) { if (o && typeof o.body === 'string') window.__sent.push(o.body); return f.apply(this, arguments); }; true")
                p.js(f"document.querySelector('{sel} [data-rich]').click()")
                p.until(f"!!document.querySelector('{sel} .ProseMirror')", "the editor opens")
                p.js(f"document.querySelector('{sel} .ProseMirror').cxed.editor.commands.setContent({{type: 'doc', content: [{{type: 'paragraph', content: [{{type: 'text', text: 'Fictional line one\\nline two'}}]}}]}}); true")
                self.assertIn("\n", p.js(f"document.querySelector('{sel} .ProseMirror').cxed.editor.getHTML()"), "the editor itself holds a line break")
                p.key("Enter", 4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
                p.saved()
                self.assertEqual(p.toast(), "Text saved.")
                sent = p.js("window.__sent.filter(b => b.indexOf('Fictional line') >= 0)")
                self.assertTrue(sent and all("\\n" not in b and "\\r" not in b for b in sent), sent)
                self.assertEqual(self.body(ref)["html"], "<p>Fictional line one line two</p>")


if __name__ == "__main__":
    unittest.main()
