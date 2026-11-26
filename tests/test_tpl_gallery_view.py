"""Row 1233, Image gallery: the published view. The view part drawn on a bare page from fixture data at 1400 and 900 px wide, in light and
dark: three across at full width, two across at half width and at 900 px, the one shape for all, each image as framed (its own pixels, no
filter), the caption only when there is one, no tools, a click or Enter opens the large view with its caption, Esc, a click outside and
the close button close it, and the page does not scroll sideways. Also what gallery.published() hands the file. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_gallery_view
Needs Chrome (the #33 harness) for the page tests (export CLARK_CHROME=${CREAITE_CHROME:-/usr/local/bin/creaite-chrome}).
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from _pictures import GOOD, GOOD_JPEG, published
from clark.section_kinds import gallery
from test_server import Running, chrome, wait
from test_tpl_imagecap_full_view import png, uri

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "gallery_view_demo.jsx"
_PAGE = {}
COLOURS = [(200, 30, 30), (30, 200, 30), (30, 30, 200), (200, 200, 30), (30, 200, 200), (200, 30, 200)]


def page_html():
    if "html" not in _PAGE:
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        import esbuild
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8") + (PAGE_SRC.parent / "shell.css").read_text(encoding="utf-8")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB" data-theme="light"><head><meta charset="utf-8"><title>t</title><style>{css}</style></head>\n'
                         f'<body><main style="max-width:1100px;margin:0 auto;padding:0 16px"><div id="root"></div></main>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def pictures(n, caps=(), alts=True, size=(160, 120)):
    """n fictional images, each its own colour (left half one, right half the next), with a caption where `caps` says."""
    out = []
    for i in range(n):
        a, b = COLOURS[i % 6], COLOURS[(i + 1) % 6]
        out.append({"image": uri(png(size[0], size[1], a, b)), "caption": f"Fictional caption {i + 1}" if i in caps else "",
                    "alt": f"Fictional description {i + 1}" if alts else ""})
    return out


class Published(unittest.TestCase):
    def test_columns_and_shape_pass_through_only_when_valid(self):
        body = {"v": 1, "pictures": {"1": GOOD}}
        self.assertEqual(published("gallery", body)["content"], {"pictures": [{"image": GOOD, "caption": "", "alt": ""}]}, "none said: as 1.0.7")
        got = published("gallery", {**body, "columns": 2, "shape": "square"})["content"]
        self.assertEqual((got["columns"], got["shape"]), (2, "square"))
        for bad in ({"columns": 4}, {"columns": "3"}, {"columns": True}, {"shape": "tall"}, {"shape": ["4:3"]}):
            with self.subTest(bad=bad):
                self.assertEqual(gallery.published({**body, **bad}, None)["content"].keys(), {"pictures"})
        self.assertIsNone(gallery.published({"columns": 3, "shape": "square"}, None), "no image, nothing in the report")


class PublishedEveryValue(unittest.TestCase):
    """Row 1233 killer tests: every shape and both column counts reach the file, and only those."""

    def test_every_shape_and_both_column_counts_pass_through(self):
        body = {"v": 1, "pictures": {"1": GOOD}}
        for shape in ("4:3", "square", "16:9", "whole"):
            with self.subTest(shape=shape):
                self.assertEqual(published("gallery", {**body, "shape": shape})["content"]["shape"], shape)
                self.assertEqual(gallery.published({**body, "shape": shape}, None)["content"]["shape"], shape)
        for columns in (2, 3):
            with self.subTest(columns=columns):
                self.assertEqual(published("gallery", {**body, "columns": columns})["content"]["columns"], columns)
        self.assertEqual(gallery.SHAPES, ("4:3", "square", "16:9", "whole"))
        self.assertEqual(gallery.COLUMNS, (2, 3))


class View(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.G", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, code):
        return self.cdp.js(code, self.sid)

    def draw(self, pics, width=1400, theme="light", cls="", **more):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
        self.js(f"G.mount({json.dumps({'id': 'ABC-S-001', 'type': 'gallery', 'content': {'pictures': pics, **more}})}, {json.dumps(cls)})")
        n = len(pics)
        self.assertTrue(wait(lambda: self.js(f"(function(){{var l=[...document.querySelectorAll('.tpl-gal-fig img')];return l.length=={n} && l.every(function(i){{return i.complete && i.naturalWidth>0}})}})()")), "the images loaded")

    def measure(self):
        return self.js("""(function(){
          var imgs=[...document.querySelectorAll('.tpl-gal-fig img')], g=document.querySelector('.tpl-gal'), m=document.querySelector('main');
          var lefts=[...new Set(imgs.map(function(i){return Math.round(i.getBoundingClientRect().left)}))].sort(function(a,b){return a-b});
          var mr=m.getBoundingClientRect();
          var px=imgs.map(function(i){var c=document.createElement('canvas');c.width=i.naturalWidth;c.height=i.naturalHeight;var x=c.getContext('2d');x.drawImage(i,0,0);
            var a=x.getImageData(1,1,1,1).data,b=x.getImageData(c.width-2,1,1,1).data;return [a[0],a[1],a[2],b[0],b[1],b[2]]});
          var caps=[...document.querySelectorAll('.tpl-gal-fig')].map(function(f){var c=f.querySelector('figcaption');return c?c.textContent:null});
          var first=imgs[0].getBoundingClientRect();
          return {across:lefts.length, n:imgs.length, px:px, caps:caps, alts:imgs.map(function(i){return i.getAttribute('alt')}),
                  ratio:first.width/first.height, scroll:[document.documentElement.scrollWidth, document.documentElement.clientWidth],
                  filter:imgs.map(function(i){return getComputedStyle(i).filter+'|'+getComputedStyle(i).opacity}),
                  inside:imgs.every(function(i){var r=i.getBoundingClientRect();return r.left>=mr.left-1 && r.right<=mr.right+1}),
                  tools:document.querySelectorAll('input,textarea,select,[role=toolbar],[draggable=true],.miss,.hdl,.del,.focus,.addtile').length,
                  buttons:document.querySelectorAll('button').length, capSize:Math.min.apply(null,[...document.querySelectorAll('figcaption')].map(function(c){return parseFloat(getComputedStyle(c).fontSize)}).concat([99])),
                  breakInside:getComputedStyle(document.querySelector('.tpl-gal-fig')).breakInside, cls:g.className};})()""")

    def test_shown_and_empty(self):
        self.assertTrue(self.js("G.ready"))
        body = {"v": 1, "pictures": {"2": GOOD, "1": GOOD_JPEG}, "items": {"2": {"caption": "Fictional", "alt": "A"}}, "columns": 2, "shape": "16:9"}
        want = published("gallery", body)["content"]
        self.assertEqual(self.js(f"G.shown({json.dumps(body)})"), want, "the page's shown() is what published() puts in the file")
        bad = {**body, "columns": 5, "shape": "odd"}
        self.assertEqual(self.js(f"G.shown({json.dumps(bad)})"), published("gallery", bad)["content"])
        self.assertIsNone(self.js(f"G.shown({json.dumps({'v': 1, 'columns': 2})})"))
        for sec, empty in (({"type": "gallery", "body": json.dumps({"v": 1})}, True), ({"type": "gallery", "content": {"pictures": [{"image": "http://x/y.png"}]}}, True),
                           ({"type": "gallery", "content": {"pictures": [{"image": GOOD}]}}, False), ({"type": "gallery", "body": json.dumps(body)}, False)):
            self.assertIs(self.js(f"G.isEmpty({json.dumps(sec)})"), empty, sec)

    def test_three_across_at_1400_two_at_900_in_both_themes_with_the_same_pixels(self):
        pics = pictures(6, caps=(0, 2, 4))
        for width, across in ((1400, 3), (900, 2)):
            for theme in ("light", "dark"):
                self.draw(pics, width, theme, columns=3)
                m = self.measure()
                with self.subTest(width=width, theme=theme):
                    self.assertEqual((m["n"], m["across"]), (6, across))
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1], "no sideways scroll")
                    self.assertTrue(m["inside"])
                    self.assertEqual(set(m["filter"]), {"none|1"}, "the theme does not change an image")
                    for i, px in enumerate(m["px"]):
                        self.assertEqual(px, list(COLOURS[i]) + list(COLOURS[(i + 1) % 6]), "each image in its own order and pixels")
                    self.assertEqual(m["alts"], [p["alt"] for p in pics])
                    self.assertEqual(m["caps"], ["Fictional caption 1", None, "Fictional caption 3", None, "Fictional caption 5", None])
                    self.assertEqual(m["tools"], 0, "no tool, dot, bin or red mark")
                    self.assertGreaterEqual(m["capSize"], 13)
                    self.assertEqual(m["breakInside"], "avoid", "an image does not split across a printed page")

    def test_columns_two_gives_two_across_and_a_half_width_section_is_two_across(self):
        self.draw(pictures(6), 1400, columns=2)
        self.assertEqual(self.measure()["across"], 2)
        self.draw(pictures(6), 1400, "light", "slot-left", columns=3)
        self.assertEqual(self.measure()["across"], 2, "half width, even when three across is said")
        self.draw(pictures(4), 1400, "dark", "slot-right")
        self.assertEqual(self.measure()["across"], 2, "none said, half width")
        self.draw(pictures(1), 900, columns=3)
        self.assertEqual(self.measure()["across"], 1, "one image is one across")

    def test_fewer_images_than_columns_fill_the_row_not_a_third_each(self):
        """Row 1233 killer: three across said with two images is two across (each half the row); with one image it is the whole row."""
        for n, cls in ((1, "c-1"), (2, "c-2"), (3, "c-3")):
            self.draw(pictures(n), 1400, columns=3)
            m = self.measure()
            with self.subTest(n=n):
                self.assertIn(cls, m["cls"].split())
                row = self.js("document.querySelector('.tpl-gal').getBoundingClientRect().width")
                img = self.js("document.querySelector('.tpl-gal-fig img').getBoundingClientRect().width")
                self.assertGreater(img, row / n * 0.9, "each image takes its share of the whole row")

    def test_a_closed_large_view_does_not_close_the_next_one_opened_at_once(self):
        """Row 1233 killer: the late close event of the dialog taken away must not close the one opened right after."""
        self.draw(pictures(3, caps=(0, 1, 2), size=(1200, 900)))
        for _ in range(3):
            self.js("document.querySelectorAll('.tpl-gal-open')[0].click()")
            self.assertTrue(wait(lambda: self.state()["open"]))
            self.js("document.querySelector('.tpl-gal-x').click()")
            self.assertTrue(wait(lambda: not self.state()["open"]))
            self.js("document.querySelectorAll('.tpl-gal-open')[1].click()")
            self.assertTrue(wait(lambda: self.state()["open"]))
            self.assertFalse(wait(lambda: not self.state()["open"], 0.6), "still open after the first one's close event has arrived (a poll that ends at once if it closes)")
            self.assertEqual(self.state()["caption"], "Fictional caption 2")
            self.js("document.querySelector('.tpl-gal-x').click()")
            self.assertTrue(wait(lambda: not self.state()["open"]))

    def test_a_close_event_of_a_dialog_already_taken_away_is_ignored(self):
        """Row 1233 guard: `if (live.current) onClose()` -- the stale dialog's close event, delivered after the next one is open, must not close it.
        The event is delivered by hand to the kept old element, so the order does not depend on when the browser queues the real one."""
        self.draw(pictures(3, caps=(0, 1, 2), size=(1200, 900)))
        self.js("document.querySelectorAll('.tpl-gal-open')[0].click()")
        self.assertTrue(wait(lambda: self.state()["open"]))
        self.js("window.__old = document.querySelector('dialog.tpl-gal-large')")
        self.js("document.querySelector('.tpl-gal-x').click()")
        self.assertTrue(wait(lambda: not self.state()["open"]))
        self.assertTrue(self.js("!window.__old.isConnected"), "the first dialog is gone from the page")
        self.js("document.querySelectorAll('.tpl-gal-open')[1].click()")
        self.assertTrue(wait(lambda: self.state()["open"]))
        self.assertTrue(self.js("document.querySelector('dialog.tpl-gal-large') !== window.__old"), "the open one is the second dialog")
        self.js("window.__old.dispatchEvent(new Event('close'))")
        self.assertFalse(wait(lambda: not self.state()["open"], 0.6), "the stale close event closed the second dialog")
        self.assertEqual(self.state()["caption"], "Fictional caption 2")
        self.js("document.querySelector('.tpl-gal-x').click()")
        self.assertTrue(wait(lambda: not self.state()["open"]))

    def test_a_new_gallery_as_clark_publishes_it_is_4_3_three_across_and_two_at_half_width_and_900(self):
        """Row 1233 ruling, end to end: the content comes from the real gallery model (a new body with real PNGs), not from a fixture."""
        from clark.section_kinds import gallery
        body = {"v": 2}
        for n in range(1, 4):
            body = gallery.check(gallery.with_picture(body, str(n), uri(png(160, 90, COLOURS[n], COLOURS[n + 1]))), None)
        content = gallery.published(body, None)["content"]
        self.assertEqual((content["columns"], content["shape"]), (3, "4:3"))
        for width, cls, across in ((1400, "", 3), (900, "", 2), (1400, "slot-left", 2), (1400, "slot-right", 2)):
            self.draw(content["pictures"], width, "light", cls, columns=content["columns"], shape=content["shape"])
            m = self.measure()
            with self.subTest(width=width, cls=cls):
                self.assertEqual(m["across"], across)
                self.assertAlmostEqual(m["ratio"], 4 / 3, 1)
        old = gallery.published({"v": 1, "pictures": {"1": uri(png(160, 90)), "2": uri(png(160, 90))}}, None)["content"]
        self.assertEqual(set(old), {"pictures"})
        self.draw(old["pictures"], 1400)
        m = self.measure()
        self.assertEqual((m["across"], round(m["ratio"], 2), "n-2" in m["cls"]), (2, 1.33, True), "an old gallery is drawn as it was")

    def test_old_gallery_with_nothing_said_is_drawn_as_it_was(self):
        for n, across in ((1, 1), (2, 2), (3, 3), (6, 3)):
            self.draw(pictures(n))
            m = self.measure()
            self.assertEqual((m["across"], round(m["ratio"], 2)), (across, 1.33), n)
            self.assertIn(f"n-{min(n, 3)}", m["cls"])

    def test_one_shape_for_all(self):
        for shape, ratio in (("4:3", 1.33), ("square", 1.0), ("16:9", 1.78)):
            self.draw(pictures(3), 1400, columns=3, shape=shape)
            self.assertAlmostEqual(self.measure()["ratio"], ratio, 1, shape)
        self.draw([{"image": uri(png(160, 60)), "caption": "", "alt": "x"}], 1400, columns=2, shape="whole")
        self.assertAlmostEqual(self.measure()["ratio"], 160 / 60, 1, "whole: the image's own shape")

    def test_no_caption_no_description_and_text_never_markup(self):
        self.draw(pictures(2, alts=False))
        m = self.measure()
        self.assertEqual((m["caps"], m["alts"]), ([None, None], ["", ""]), "no description is read as decoration, never invented")
        self.draw([{"image": uri(png(80, 60)), "caption": "<b>Fictional</b> & plan", "alt": "<i>x</i>"}])
        self.assertEqual(self.js("document.querySelector('figcaption').textContent"), "<b>Fictional</b> & plan")
        self.assertEqual(self.js("document.querySelectorAll('figcaption b, img[alt] i').length"), 0)

    def test_the_view_never_shows_the_red_no_description_mark_of_the_edit(self):
        for theme in ("light", "dark"):
            self.draw(pictures(2, alts=False), 1400, theme)
            self.assertEqual(self.js("document.querySelectorAll('.tpl-gal-nodesc').length"), 0, f"no mark on undescribed images in the view, {theme}")
            self.assertEqual(self.js("document.querySelectorAll('.tpl-gal-fig').length"), 2, "the images are drawn")
            self.assertNotIn("No description yet", self.js("document.body.textContent"))

    def test_an_address_that_is_not_a_real_image_draws_nothing(self):
        for bad in ("http://example.com/a.png", "javascript:alert(1)", "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=", "data:image/gif;base64,R0lGODlhAQABAAAAACw="):
            self.js(f"G.mount({json.dumps({'id': 'ABC-S-001', 'type': 'gallery', 'content': {'pictures': [{'image': bad, 'caption': 'Fictional'}]}})})")
            self.assertEqual(self.js("document.querySelectorAll('img, figure, button').length"), 0, bad)

    def key(self, name, code):
        for kind in ("keyDown", "keyUp"):
            self.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": name, "windowsVirtualKeyCode": code, **({"text": "\r"} if name == "Enter" and kind == "keyDown" else {})}, self.sid)

    def state(self):
        return self.js("""(function(){var d=document.querySelector('dialog.tpl-gal-large');var o=d&&d.open;
          return {open:!!o, caption:o&&d.querySelector('p')?d.querySelector('p').textContent:null, big:o?d.querySelector('img').getBoundingClientRect().width:0,
                  focus:document.activeElement?document.activeElement.className:'', isClose:!!(o&&document.activeElement===d.querySelector('.tpl-gal-x')),
                  src:o?d.querySelector('img').getAttribute('src'):null, alt:o?d.querySelector('img').getAttribute('alt'):null};})()""")

    def test_click_opens_the_large_view_and_esc_outside_click_and_the_button_close_it(self):
        pics = pictures(3, caps=(1,), size=(1200, 900))
        self.draw(pics)
        self.assertFalse(self.state()["open"])
        self.js("document.querySelectorAll('.tpl-gal-open')[1].click()")
        self.assertTrue(wait(lambda: self.state()["open"]))
        s = self.state()
        self.assertEqual((s["caption"], s["src"], s["alt"]), ("Fictional caption 2", pics[1]["image"], "Fictional description 2"))
        self.assertTrue(s["isClose"], "the close button is the first thing Tab reaches")
        self.assertGreater(s["big"], self.measure_small(), "larger than in the grid")
        self.key("Escape", 27)
        self.assertTrue(wait(lambda: not self.state()["open"]), "Esc closes")
        self.assertTrue(wait(lambda: self.js("document.activeElement.className") == "tpl-gal-open"), "focus goes back to the image")
        # an image with no caption: the large view has no caption line
        self.js("document.querySelectorAll('.tpl-gal-open')[0].click()")
        self.assertTrue(wait(lambda: self.state()["open"]))
        self.assertIsNone(self.state()["caption"])
        # a click outside the image closes it
        self.js("document.querySelector('dialog.tpl-gal-large').dispatchEvent(new MouseEvent('click', {bubbles: true}))")
        self.assertTrue(wait(lambda: not self.state()["open"]), "a click outside closes")
        # a click on the image itself does not
        self.js("document.querySelectorAll('.tpl-gal-open')[2].click()")
        self.assertTrue(wait(lambda: self.state()["open"]))
        self.js("document.querySelector('dialog.tpl-gal-large img').click()")
        self.assertTrue(self.state()["open"], "a click on the image keeps it open")
        self.js("document.querySelector('.tpl-gal-x').click()")
        self.assertTrue(wait(lambda: not self.state()["open"]), "the close button closes")

    def measure_small(self):
        return self.js("document.querySelector('.tpl-gal-fig img').getBoundingClientRect().width")

    def test_enter_on_an_image_opens_it_and_the_large_view_fits_900_dark(self):
        self.draw(pictures(3, caps=(0,)), 900, "dark")
        self.js("document.querySelectorAll('.tpl-gal-open')[0].focus()")
        self.key("Enter", 13)
        self.assertTrue(wait(lambda: self.state()["open"]), "Enter opens")
        self.assertEqual(self.state()["caption"], "Fictional caption 1")
        self.assertEqual(self.js("[document.documentElement.scrollWidth <= document.documentElement.clientWidth, getComputedStyle(document.querySelector('dialog.tpl-gal-large img')).filter]"), [True, "none"])
        self.assertGreaterEqual(self.js("parseFloat(getComputedStyle(document.querySelector('dialog.tpl-gal-large p')).fontSize)"), 13)
        self.key("Escape", 27)
        self.assertTrue(wait(lambda: not self.state()["open"]))

    def test_print_emulation_keeps_each_image_whole_and_hides_the_large_view(self):
        self.draw(pictures(6, caps=(0,)))
        self.cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, self.sid)
        try:
            m = self.measure()
            self.assertEqual(m["breakInside"], "avoid")
            self.assertEqual(m["px"][0][:3], list(COLOURS[0]))
        finally:
            self.cdp.call("Emulation.setEmulatedMedia", {"media": ""}, self.sid)


if __name__ == "__main__":
    unittest.main()
