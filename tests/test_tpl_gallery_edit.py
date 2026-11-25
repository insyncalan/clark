"""Row 1233 slice 2 (AP1 to AP6, AP11): the Image gallery's Edit page (Classic), in a real browser on a bare page, at 1400 and 900 px. The Edit part and
its CSS (shell.css, edit.css and the Classic rules.css, rules-2.css) are bundled with a stand-in for clark's routes that keeps the section in memory and
logs every call (tests/fixtures/gallery_edit_demo.jsx). What clark's server does with an image is test_gallery_v2_server.py.

Run: python3 dev/run_tests.py test_tpl_gallery_edit
Needs Chrome (the #33 harness): fails, never skips, without it. Fictional data only.
"""
import contextlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from test_server import Running, chrome, wait
from clark.section_kinds import gallery

PAGE = SRC / "clark" / "page"
DEMO = ROOT / "tests" / "fixtures" / "gallery_edit_demo.jsx"
WORDS_JS = PAGE / "src" / "logic" / "galleryWords.js"
_HTML = {}
ID = "ABC-S-1"

EMPTY = "Choose images, or drop them here (up to six)"
ADD = "Add an image"
FULL = "A gallery holds up to six images. Remove one to add another."
BIG = "That file is too big. Choose one under 10 MB."
COUNT = "{n} of 6 images. Each is made smaller to keep the file light (up to 1,600 px wide). The published page carries only the part you see in each tile."

HELPERS = """
window.png = (w, h, name) => new Promise(r => { const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d');
  g.fillStyle = 'rgb(40,160,60)'; g.fillRect(0, 0, w, h); c.toBlob(b => r(new File([b], name || 'fictional.png', { type: 'image/png' })), 'image/png'); });
window.give = async (files) => { const dt = new DataTransfer(); files.forEach(f => dt.items.add(f));
  const i = document.querySelector('input[type=file]'); i.files = dt.files; i.dispatchEvent(new Event('change', { bubbles: true })); return true; };
window.add = async (n, w, h) => { const files = []; for (let k = 0; k < n; k++) files.push(await window.png(w || 200, h || 150, 'f' + k + '.png')); return window.give(files); };
window.mixed = async () => window.give([new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'huge.png', { type: 'image/png' }), await window.png(200, 150, 'ok.png')]);
window.big = () => window.give([new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'huge.png', { type: 'image/png' })]);
window.cs = (sel, props) => { const e = document.querySelector(sel); const k = getComputedStyle(e); return props.map(p => k[p]); };
"""

PIC = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def many(n, extra=None):
    return json.dumps({"v": 2, "pictures": {str(i): PIC for i in range(1, n + 1)}, **(extra or {})})


def page_html():
    if "html" not in _HTML:
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        import esbuild
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE / 'src'}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        THEME = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
        css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "clark" / "brand" / "tokens.css", PAGE / "shell.css", PAGE / "src" / "edit" / "edit.css", THEME / "rules.css", THEME / "rules-2.css") if p.is_file())
        _HTML["html"] = ('<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title>'
                         f'<style id="theme">{css}</style></head>\n<body><script id="clark-boot" type="application/json">{{"token":"t"}}</script>'
                         f'<div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _HTML["html"]


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.F", cls.sid)), "the test bundle ran"
        cls.cdp.js(HELPERS, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr, promise=False):
        if promise:
            self.cdp.js(f"window.__got = undefined; Promise.resolve({expr}).then(v => window.__got = JSON.stringify(v === undefined ? null : v), e => window.__got = 'ERROR ' + e.message)", self.sid)
            self.assertTrue(wait(lambda: self.cdp.js("window.__got !== undefined", self.sid), 20), expr)
            got = self.cdp.js("window.__got", self.sid)
        else:
            got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertFalse(str(got).startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got) if got and got != "undefined" else None

    def until(self, expr, what, seconds=15):
        self.assertTrue(wait(lambda: self.cdp.js(f"!!({expr})", self.sid), seconds), what)

    def mount(self, body="", page=1400, slot=""):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": page, "height": 1400, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.val(f"F.mount({{id: {json.dumps(ID)}, body: {json.dumps(body)}}}, {min(page - 100, 1300)}, {json.dumps(slot)})")
        self.until("document.querySelector('#root').children.length", "drawn")

    def body(self):
        return self.val(f"F.body({json.dumps(ID)})")

    def text(self, sel):
        return self.val(f"document.querySelector({json.dumps(sel)}).textContent")

    def count(self, sel):
        return self.val(f"document.querySelectorAll({json.dumps(sel)}).length")

    def style(self, sel, *props):
        return self.val(f"cs({json.dumps(sel)}, {json.dumps(list(props))})")

    def widths(self, sel):
        return self.val(f"[...document.querySelectorAll({json.dumps(sel)})].map(e => Math.round(e.getBoundingClientRect().width * 10) / 10)")

    def tops(self, sel):
        return self.val(f"[...document.querySelectorAll({json.dumps(sel)})].map(e => Math.round(e.getBoundingClientRect().top))")

    def dark(self, on=True):
        self.cdp.js(f"document.documentElement.setAttribute('data-theme', {json.dumps('dark' if on else 'light')})", self.sid)
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "dark" if on else "light"}]}, self.sid)

    def token(self, name):
        """The colour a token resolves to on the page now (so dark values come from the page's own tokens)."""
        return self.val(f"(function(){{ const e = document.createElement('i'); e.style.color = 'var({name})'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; }})()")

    def calls(self):
        return self.val("F.server.calls")

    def toast_text(self):
        return self.val("(F.toast() || {}).text")


WIDTHS = ((1400, 3), (900, 2))       # page width, tiles across (the sheet goes to two across at 900)


class Grid(Page):          # AP1, AP2
    def test_gallery_edit_grid(self):
        for page, across in WIDTHS:
            with self.subTest(page):
                self.mount(many(6), page)
                self.assertEqual(self.count(".tpl-gal-tile"), 6)
                self.assertEqual(self.style(".tpl-gal-tiles", "display", "columnGap", "rowGap"), ["grid", "12px", "12px"])
                cols = self.style(".tpl-gal-tiles", "gridTemplateColumns")[0].split()
                self.assertEqual(len(cols), across, cols)
                px = [float(c[:-2]) for c in cols]
                self.assertLess(max(px) - min(px), 0.6, "the columns are equal (minmax(0, 1fr))")
                top = self.tops(".tpl-gal-tile")
                self.assertEqual(top[:across], [top[0]] * across)
                self.assertGreater(top[across], top[0], "the next one is on the next row")
                w = self.widths(".tpl-gal-tile")
                self.assertAlmostEqual(w[0], w[1], delta=0.6)

    def test_columns_two_gives_two_across_and_a_half_width_section_is_two_across(self):
        for what, body, page, slot in (("columns 2 at full width", many(6, {"columns": 2}), 1400, ""), ("half width", many(6), 1400, "left"),
                                       ("900 px", many(6), 900, ""), ("one version 1 body at 1400 is three", json.dumps({"v": 1, "pictures": {"1": PIC, "2": PIC, "3": PIC}}), 1400, "")):
            with self.subTest(what):
                self.mount(body, page, slot)
                want = 3 if what.startswith("one") else 2
                tops = self.tops(".tpl-gal-tile")
                self.assertEqual(len([t for t in tops if t == tops[0]]), want, tops)
                self.assertFalse(self.val("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "no sideways scroll")

    def test_the_shape_for_all_sets_the_frame_ratio(self):
        for page, shape, ratio, cls in ((p, *r) for p, _ in WIDTHS for r in (("square", 1, "s11"), ("16:9", 16 / 9, "s169"), ("4:3", 4 / 3, None))):
            with self.subTest(f"{shape} at {page}"):
                self.mount(many(3, {"shape": shape}), page)
                if cls:
                    self.assertTrue(self.val(f"document.querySelector('.tpl-gal-tiles').classList.contains({json.dumps(cls)})"), "the shape class is applied")
                else:
                    self.assertFalse(self.val("/\\bs(11|169|whole)\\b/.test(document.querySelector('.tpl-gal-tiles').className)"), "4:3 is the default: no shape class")
                w, h = self.val("(function(){const r = document.querySelector('.tpl-gal-frame').getBoundingClientRect(); return [r.width, r.height];})()")
                self.assertAlmostEqual(w / h, ratio, delta=0.03)


class Parts(Page):         # AP3, AP4, AP5, AP6, AP11
    def test_tile_at_both_widths_radius_12_border_2_selected_is_accent(self):
        for page in (1400, 900):
            self.mount(many(3), page)
            self.assertEqual(self.style(".tpl-gal-tile:nth-child(1)", "borderTopLeftRadius", "borderTopWidth", "borderTopStyle", "borderTopColor"),
                             ["12px", "2px", "solid", "rgb(91, 71, 216)"], "the first is selected")
            self.assertEqual(self.style(".tpl-gal-tile:nth-child(2)", "borderTopWidth", "borderTopColor"), ["2px", "rgba(0, 0, 0, 0)"])
            self.val("document.querySelector('.tpl-gal-tile:nth-child(2)').click()")
            self.until("document.querySelector('.tpl-gal-tile:nth-child(2).sel')", "a click selects")
            self.assertEqual(self.style(".tpl-gal-tile:nth-child(2)", "borderTopColor"), ["rgb(91, 71, 216)"])
            self.assertEqual(self.style(".tpl-gal-tile:nth-child(1)", "borderTopColor"), ["rgba(0, 0, 0, 0)"])

    def test_tiles_are_reached_by_tab_and_enter_or_space_selects(self):
        self.mount(many(3))
        self.assertEqual(self.val("[...document.querySelectorAll('.tpl-gal-tile')].map(e => e.tabIndex)"), [0, 0, 0])
        for key in ("Enter", " "):
            self.val("document.querySelector('.tpl-gal-tile:nth-child(1)').click()")
            self.val(f"document.querySelector('.tpl-gal-tile:nth-child(3)').dispatchEvent(new KeyboardEvent('keydown', {{key: {json.dumps(key)}, bubbles: true}}))")
            self.until("document.querySelector('.tpl-gal-tile:nth-child(3).sel')", f"{key!r} selects")

    def test_frame_radius_9_cover_and_the_blue_grey_ground(self):
        for page in (1400, 900):
            self.mount(many(2), page)
            self.assertEqual(self.style(".tpl-gal-frame", "borderTopLeftRadius", "overflow", "backgroundColor"), ["9px", "hidden", "rgb(230, 235, 246)"])   # --grey-100 (the mock-up draws #E8EDF8, a hex the Classic guards refuse)
            self.assertEqual(self.style(".tpl-gal-frame img", "objectFit"), ["cover"])

    def test_add_tile_is_dashed_and_gone_at_six(self):
        for page, _ in WIDTHS:
            with self.subTest(page):
                self.add_tile_at(page)

    def add_tile_at(self, page):
        self.mount(many(3), page)
        self.assertEqual(self.text(".tpl-gal-add"), "+" + ADD)
        self.assertEqual(self.val("document.querySelector('.tpl-gal-add').getAttribute('aria-label')"), ADD)
        self.assertEqual(self.style(".tpl-gal-add", "borderTopStyle", "borderTopWidth", "borderTopColor", "borderTopLeftRadius"), ["dashed", "2px", "rgb(196, 206, 227)", "12px"])   # --grey-300 (the mock-up draws #b8c1dc: no hex in the Classic block)
        self.assertGreaterEqual(self.val("document.querySelector('.tpl-gal-add').getBoundingClientRect().height"), 120)
        self.assertEqual(self.style(".tpl-gal-add b", "fontSize")[0], "26px")
        self.assertEqual(self.style(".tpl-gal-add span", "fontSize")[0], "13px")
        self.mount(many(6), page)
        self.assertEqual(self.count(".tpl-gal-add"), 0)

    def test_the_empty_area_is_one_large_dashed_area_with_the_words(self):
        for page in (1400, 900):
            self.mount("", page)
            self.assertEqual(self.count(".tpl-gal-tile"), 0)
            self.assertEqual(self.text(".tpl-gal-empty span"), EMPTY)
            self.assertEqual(self.style(".tpl-gal-empty", "borderTopStyle", "borderTopWidth", "borderTopColor", "borderTopLeftRadius"), ["dashed", "2px", "rgb(196, 206, 227)", "12px"])
            self.assertGreaterEqual(self.val("document.querySelector('.tpl-gal-empty').getBoundingClientRect().height"), 200)
            w = self.val("[document.querySelector('.tpl-gal-empty').getBoundingClientRect().width, document.querySelector('#root').getBoundingClientRect().width]")
            self.assertAlmostEqual(w[0], w[1], delta=2, msg="full width")
            self.assertEqual(self.style(".tpl-gal-empty b", "fontSize")[0], "28px")
            self.assertEqual(self.style(".tpl-gal-empty span", "fontSize")[0], self.style(".tpl-gal-empty", "fontSize")[0], "the words keep the inherited size")

    def test_caption_13px_muted_margin_8_2_0_at_both_widths(self):
        for page in (1400, 900):
            self.mount(many(2, {"items": {"1": {"caption": "Fictional site visit"}}}), page)
            self.assertEqual(self.count(".tpl-gal-tcap"), 1, "only an image with a caption has one")
            self.assertEqual(self.text(".tpl-gal-tcap"), "Fictional site visit")
            self.assertEqual(self.style(".tpl-gal-tcap", "fontSize", "color", "marginTop", "marginRight", "marginBottom", "marginLeft", "textAlign"),
                             ["13px", "rgb(71, 85, 119)", "8px", "2px", "0px", "2px", "start"])


class Dark(Page):          # the key colours again in the dark theme, read from the page's own tokens
    def tearDown(self):
        self.dark(False)

    def test_dark_selected_border_dashed_add_tile_and_caption_use_the_dark_tokens(self):
        for page, _ in WIDTHS:
            with self.subTest(page):
                self.dark(False)
                self.mount(many(3, {"items": {"1": {"caption": "Fictional"}}}), page)
                light = (self.token("--brand-blue"), self.token("--grey-300"), self.token("--text-muted"))
                self.dark()
                dk = (self.token("--brand-blue"), self.token("--grey-300"), self.token("--text-muted"))
                self.assertNotEqual(light[1:], dk[1:], "the page has dark values for these tokens")
                self.assertEqual(self.style(".tpl-gal-tile:nth-child(1)", "borderTopColor"), [dk[0]])
                self.assertEqual(self.style(".tpl-gal-tile:nth-child(2)", "borderTopColor"), ["rgba(0, 0, 0, 0)"])
                self.assertEqual(self.style(".tpl-gal-add", "borderTopStyle", "borderTopColor"), ["dashed", dk[1]])
                self.assertEqual(self.style(".tpl-gal-tcap", "color"), [dk[2]])
                self.assertEqual(self.style(".tpl-gal-add", "color"), [dk[2]])


class Adding(Page):        # the file picker, the drop, the refusals
    def test_the_picker_takes_several_files_each_one_call_to_the_next_free_slot(self):
        self.mount("")
        self.assertTrue(self.val("document.querySelector('input[type=file]').multiple"))
        self.val("add(3)", True)
        self.until("F.server.calls.length >= 3", "three images sent")
        self.assertEqual([c["slot"] for c in self.calls()], ["1", "2", "3"])
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 3", "three tiles")
        self.assertEqual(sorted(self.body()["pictures"]), ["1", "2", "3"])

    def test_the_seventh_is_refused_in_words_and_some_of_several_are_added(self):
        self.mount(many(6))
        self.val("add(1)", True)
        self.until("F.toast()", "said")
        self.assertEqual(self.toast_text(), FULL)
        self.assertEqual(self.calls(), [])
        self.mount(many(4))
        self.val("add(5)", True)
        self.until("F.server.calls.length >= 2", "two fit")
        self.until("(F.toast() || {}).text && F.toast().text.startsWith('Added')", "said what was added")
        self.assertEqual(self.toast_text(), "Added 2 of the 5 files. A gallery holds up to six images.")
        self.assertEqual(len(self.calls()), 2)
        self.mount(many(5))
        self.assertIsNone(self.toast_text(), "mounting clears the last toast")
        self.val("add(3)", True)
        self.until("(F.toast() || {}).text && F.toast().text.startsWith('Added')", "said")
        self.assertEqual(self.toast_text(), "Added 1 of the 3 files. A gallery holds up to six images.", "the gallery is now full")
        self.mount(many(2))
        self.val("mixed()", True)
        self.until("(F.toast() || {}).text && F.toast().text.indexOf('Added') >= 0", "said")
        self.assertEqual(self.toast_text(), BIG + " Added 1 of the 2 files.", "not full: no second sentence; the refused file's reason stays in the one toast")

    def test_a_file_over_10_mb_is_refused_with_the_ruled_words(self):
        self.mount("")
        self.val("big()", True)
        self.until("F.toast()", "said")
        self.assertEqual(self.toast_text(), BIG)
        self.assertEqual(self.calls(), [])

    def test_open_and_publish_do_not_rewrite_a_v1_body_and_adding_keeps_it_v1(self):
        v1 = json.dumps({"v": 1, "items": {"1": {"caption": "Fictional", "alt": "A room"}}, "pictures": {"1": PIC}})
        self.mount(v1)
        self.assertEqual(self.count(".tpl-gal-tile"), 1)
        self.assertEqual(self.calls(), [], "opening sends nothing")
        self.assertEqual(self.body(), json.loads(v1))
        self.val("add(1)", True)
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 2", "added")
        calls = self.calls()
        self.assertEqual([(c["path"], c["slot"]) for c in calls], [("/api/section-image", "2")], "one image call to slot 2 and nothing else (no body write that could set a version)")
        self.assertGreater(calls[0]["bytes"], 0)
        self.assertEqual(self.body()["v"], 1, "the stand-in keeps the version itself: this only shows it was not changed")
        got = gallery.published(gallery.check(json.loads(v1), None), None)       # publishing a version 1 body: as 1.0.7 did
        self.assertEqual(gallery.check(json.loads(v1), None)["v"], 1)
        self.assertNotIn("columns", got["content"])
        self.mount(many(1))
        self.val("add(1)", True)
        self.until("document.querySelectorAll('.tpl-gal-tile').length === 2", "added")
        self.assertEqual([(c["path"], c["slot"]) for c in self.calls()], [("/api/section-image", "2")])
        self.assertEqual(self.body()["v"], 2)


class Words(Page):         # the fields and the count line
    def test_description_caption_then_the_count_line_last_and_no_300(self):
        self.mount(many(3))
        kids = self.val("[...document.querySelector('.tpl-gal-edit').children].map(e => e.className || e.tagName)")
        self.assertLess(kids.index("tpl-gal-fields"), self.val("[...document.querySelector('.tpl-gal-edit').children].findIndex(e => e.hasAttribute('data-count'))"))
        labels = self.val("[...document.querySelectorAll('.tpl-gal-fields label, .tpl-gal-fields .tpl-pic-lbl')].map(e => e.textContent)")
        self.assertEqual(labels, ["Selected image 1: describe it for people who cannot see it", "Caption optional"])
        self.assertEqual(self.text("[data-alt-note]"), "No description yet.")
        line = self.text("[data-count]")
        self.assertEqual(line, COUNT.format(n=3))
        self.assertNotIn("300", line, "the line has no 300")
        self.mount(many(1))
        self.assertTrue(self.text("[data-count]").startswith("1 of 6 images."))

    def test_the_words_file_has_no_300_and_the_numbers_come_from_the_constants(self):
        text = WORDS_JS.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"\b300\b", "no 300 dpi anywhere in the gallery words")
        for name, number in (("PICTURE_MAX", gallery.PICTURE_MAX), ("ORIGINAL_MAX", gallery.ORIGINAL_MAX), ("WIDTH_MAX", gallery.WIDTH_MAX), ("V1_MOST", gallery.V1_PICTURE_MAX)):
            got = re.search(rf"export const {name} = ([^;]+);", text).group(1).split("//")[0].strip()
            self.assertEqual(eval(got), number, name)       # noqa: S307 (a product of the file's own integers)
        server = (SRC / "clark" / "server.py").read_text(encoding="utf-8")
        self.assertRegex(server, r"IMAGE_FILE_MB = 10\b")
        self.assertEqual(gallery.FRAMED_MAX, 512 * 1024)
        self.assertEqual(gallery.PICTURE_MAX, 10 * 1024 * 1024)
        self.assertEqual(gallery.ORIGINAL_MAX, 1024 * 1024)

    def test_the_gallery_code_says_no_300_dpi(self):
        self.assertNotIn("300 dpi", (SRC / "clark" / "section_kinds" / "gallery.py").read_text(encoding="utf-8"))


class ApprovedWords(Page):     # every approved string of the Edit page, character for character (NEW-WORDS :1484, :1595-1596, :1900, :1979-1980, :1996-2000, :2142)
    def test_a_partial_add_says_added_n_of_the_files_with_the_count_from_the_real_numbers(self):
        self.mount(many(4))
        self.val("add(5)", True)
        self.until("(F.toast() || {}).text && F.toast().text.startsWith('Added')", "said")
        self.assertEqual(self.toast_text(), "Added 2 of the 5 files. A gallery holds up to six images.")
        self.mount(many(5))
        self.val("add(5)", True)
        self.until("(F.toast() || {}).text && F.toast().text.startsWith('Added')", "said")
        self.assertEqual(self.toast_text(), "Added 1 of the 5 files. A gallery holds up to six images.", "full after one: the second sentence")

    def test_the_field_words_name_the_selected_image_by_its_number(self):
        self.mount(many(3))
        self.assertEqual(self.val("document.querySelector('.tpl-gal-fields label').textContent"), "Selected image 1: describe it for people who cannot see it")
        self.assertEqual(self.text(".tpl-gal-fields label .quiet"), "for people who cannot see it")
        self.val("document.querySelectorAll('.tpl-gal-tile')[2].click()")
        self.until("document.querySelector('.tpl-gal-fields label').textContent.startsWith('Selected image 3: describe it')", "image 3 selected")
        self.assertEqual(self.val("document.querySelector('.tpl-gal-fields label').textContent"), "Selected image 3: describe it for people who cannot see it")
        self.assertEqual(self.val("[...document.querySelectorAll('.tpl-gal-tile')].map(e => e.getAttribute('aria-label'))"), ["Image 1", "Image 2", "Image 3"])
        self.assertEqual(self.text(".tpl-gal-fields label[for$='caption-3'] .quiet, .tpl-gal-fields .tpl-pic-lbl .quiet"), "optional")
        caption = self.val("[...document.querySelectorAll('.tpl-gal-fields label, .tpl-gal-fields .tpl-pic-lbl')].map(e => e.textContent)")
        self.assertEqual(caption[1], "Caption optional")
        self.assertEqual(self.text("[data-alt-note]"), "No description yet.")

    def test_image_added_is_said_after_one_image_is_added(self):
        self.mount("")
        self.val("add(1)", True)
        self.until("F.server.calls.length >= 1", "sent")
        self.until("(F.toast() || {}).text === 'Image added.'", "said")
        self.assertEqual(self.toast_text(), "Image added.")

    def test_making_the_image_ready_shows_in_the_empty_area_while_the_image_is_made(self):
        self.mount("")
        self.cdp.js("window.__seen = []; new MutationObserver(() => { const s = document.querySelector('.tpl-gal-empty span'); if (s) window.__seen.push(s.textContent); }).observe(document.getElementById('root'), {subtree: true, childList: true, characterData: true});", self.sid)
        self.val("add(1)", True)
        self.until("F.server.calls.length >= 1", "sent")
        self.assertIn("Making the image ready\u2026", self.cdp.js("window.__seen", self.sid))

    def test_description_saved_is_said_after_a_description_is_typed(self):
        self.mount(many(2))
        self.val("(function(){ const i = document.querySelector('.tpl-gal-fields input[type=text]'); i.focus(); i.value = 'A fictional room'; i.blur(); return 1; })()")
        self.until("(F.toast() || {}).text === 'Description saved.'", "said")
        self.assertEqual(self.toast_text(), "Description saved.")
        self.assertEqual(self.body()["items"]["1"]["alt"], "A fictional room")


if __name__ == "__main__":
    unittest.main()
