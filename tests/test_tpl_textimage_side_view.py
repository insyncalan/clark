"""Row 1232, Text and Image Side by Side (a textimage section with a body of version 2): the published view (the read-only render) only. The view part drawn on a bare
page from fixture content at 1400 and 900 px wide, in light and dark: the image left or right taking a half, a third or two thirds at full width (filling the
height of the words by default), above or below at half width, stacked at 900 px (left puts the image above, right below), no sideways scroll, no tools, the caption only
when there is one, the words only with no image, the image only with no words, nothing with neither, and the old Text and image drawn as it was. The editor and the
server piece (what is stored and published) are not part of this file. Fictional data only.

Run: CLARK_CHROME=${CREAITE_CHROME:-/usr/local/bin/creaite-chrome} python3 dev/run_tests.py test_tpl_textimage_side_view
Needs Chrome (the #33 harness).
"""
import base64
import contextlib
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from _paths import ROOT, SRC
from clark import theme
from test_server import Running, chrome, wait

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "textimage_side_view_demo.jsx"
_PAGE = {}
WORDS = "".join(f"<p>Fictional paragraph {i}: the first phase is built, the nightly loads ran for a week and the reports match the old figures.</p>" for i in range(1, 7))


def chunk(name, data):
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)


def png(w, h, left=(200, 30, 30), right=(30, 30, 200)):
    row = b"\x00" + bytes(left) * (w // 2) + bytes(right) * (w - w // 2)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(row * h)) + chunk(b"IEND", b"")


def uri(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode()


IMG = uri(png(1200, 800))


def page_html(classic=False):
    key = "classic" if classic else "cards"
    if key not in _PAGE:
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
        layer = f'<style id="theme">{theme.css("prototype-2.0")}</style>' if classic else ""
        _PAGE[key] = (f'<!doctype html>\n<html lang="en-GB" data-theme="light"><head><meta charset="utf-8"><title>t</title><style>{css}</style>{layer}</head>\n'
                         f'<body><main style="max-width:1100px;margin:0 auto;padding:0 16px"><div id="root"></div></main>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE[key]


def content(**kw):
    """What a published file carries for this section: the cleaned words and the image as framed."""
    base = {"words": [], "side": "right", "html": WORDS, "image": IMG, "caption": "Fictional caption", "alt": "Fictional description", "sbs": 1}
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


MEASURE = """(function(){
  var r = function(e){ if(!e) return null; var b=e.getBoundingClientRect(); return {l:b.left, r:b.right, t:b.top, b:b.bottom, w:b.width, h:b.height}; };
  var q = function(s){ return document.querySelector(s); };
  var i = q('.tpl-sbs-frame img'), cap = q('figcaption');
  var c = null;
  if (i) { var k=document.createElement('canvas'); k.width=i.naturalWidth; k.height=i.naturalHeight; var g=k.getContext('2d'); g.drawImage(i,0,0);
           var a=g.getImageData(1,1,1,1).data, b=g.getImageData(k.width-2,1,1,1).data; c=[a[0],a[1],a[2],b[0],b[1],b[2]]; }
  return {box:r(q('.tpl-sbs')), fig:r(q('.tpl-sbs-fig')), frame:r(q('.tpl-sbs-frame')), img:r(i), words:r(q('.tpl-sbs-words')), main:r(q('main')),
          cap:cap?cap.textContent:null, capColor:cap?getComputedStyle(cap).color:null, alt:i?i.getAttribute('alt'):null, px:c,
          pos:i?getComputedStyle(i).objectPosition:null, filter:i?getComputedStyle(i).filter:null, opacity:i?getComputedStyle(i).opacity:null,
          scroll:[document.documentElement.scrollWidth, document.documentElement.clientWidth],
          tools:document.querySelectorAll('button,input,textarea,select,[role=toolbar],[role=button],[contenteditable]').length,
          breakInside:q('.tpl-sbs-fig')?getComputedStyle(q('.tpl-sbs-fig')).breakInside:null, nfig:document.querySelectorAll('figure').length,
          nwords:document.querySelectorAll('.tpl-sbs-words').length};})()"""


class Plumbing:
    classic = False
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=lambda: page_html(cls.classic))
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.F", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, code):
        return self.cdp.js(code, self.sid)

    def draw(self, c, width=1400, theme="light", slot="full"):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
        self.js(f"F.mount({json.dumps({'id': 'ABC-S-001', 'type': 'textimage', 'content': c})}, {json.dumps(slot)})")
        if c.get("image") and c["image"] == IMG:
            self.assertTrue(wait(lambda: self.js("(function(){var i=document.querySelector('.tpl-sbs-frame img, .tpl-fig img');return !!i && i.complete && i.naturalWidth>0})()")), "the image loaded")

    def measure(self):
        return self.js(MEASURE)


class View(Plumbing, unittest.TestCase):
    # ---- what is drawn from what

    def test_shown_and_empty(self):
        self.assertTrue(self.js("F.ready"))
        old = self.js(f"F.shown({json.dumps({'v': 1, 'html': '<p>x</p>', 'side': 'left', 'pictures': {'image': IMG}, 'caption': 'c', 'alt': 'a', 'share': 'third', 'half': 'bottom'})})")
        for k in ("sbs", "share", "half", "shape", "fx", "fy"):
            self.assertNotIn(k, old, "the old Text and image is shown as it was")
        got = self.js(f"F.shown({json.dumps({'v': 2, 'html': '<p>x</p>', 'pictures': {'image': IMG}, 'caption': 'c', 'alt': 'a'})})")
        self.assertEqual(got, {"words": [], "side": "right", "html": "<p>x</p>", "image": IMG, "caption": "c", "alt": "a", "sbs": 1})
        got = self.js(f"F.shown({json.dumps({'v': 2, 'html': '<p>x</p>', 'side': 'left', 'half': 'bottom', 'share': 'two', 'shape': 'square', 'fx': 200, 'fy': 900, 'pictures': {'image': IMG}})})")
        self.assertEqual({k: got[k] for k in ("side", "half", "share", "shape", "fx", "fy", "sbs")}, {"side": "left", "half": "bottom", "share": "two", "shape": "square", "fx": 200, "fy": 900, "sbs": 1})
        got = self.js(f"F.shown({json.dumps({'v': 2, 'html': '<p>x</p>', 'half': 'middle', 'share': 'odd', 'shape': 'odd', 'fx': 5000, 'fy': 'a', 'pictures': {'image': IMG}})})")
        for k in ("half", "share", "shape", "fx", "fy"):
            self.assertNotIn(k, got, f"{k}: a value that is not one of the choices is not carried")
        self.assertEqual(self.js(f"F.shown({json.dumps({'v': 2, 'html': '<p>x</p>', 'share': 'third', 'shape': 'square', 'fx': 1})})"), {"words": [], "side": "right", "html": "<p>x</p>", "sbs": 1},
                         "no image, no image settings")
        self.assertIsNone(self.js(f"F.shown({json.dumps({'v': 2, 'caption': 'only a caption'})})"))
        for sec, empty in (({"type": "textimage", "body": json.dumps({"v": 2})}, True), ({"type": "textimage", "content": {"sbs": 1, "words": [], "html": "<p> </p>"}}, True),
                           ({"type": "textimage", "content": {"sbs": 1, "words": [], "image": "http://x/y.png"}}, True), ({"type": "textimage", "content": content(image=None)}, False),
                           ({"type": "textimage", "content": content(html=None)}, False)):
            self.assertIs(self.js(f"F.isEmpty({json.dumps(sec)})"), empty, sec)

    def test_the_old_text_and_image_is_drawn_as_before(self):
        self.draw({"words": ["Fictional old words"], "side": "left", "image": IMG, "caption": "c", "alt": "a"})
        self.assertEqual(self.js("[document.querySelectorAll('.tpl-ti').length, document.querySelectorAll('.tpl-sbs').length, document.querySelectorAll('.tpl-ti.pic-left').length]"), [1, 0, 1])

    # ---- full width, 1400

    def test_full_width_puts_the_image_left_or_right_and_the_shares_are_a_half_a_third_and_two_thirds(self):
        for side in ("left", "right"):
            for share, part in (("half", 0.5), ("third", 1 / 3), ("two", 2 / 3)):
                self.draw(content(side=side, **({} if share == "half" else {"share": share})), 1400)
                m = self.measure()
                with self.subTest(side=side, share=share):
                    gap = abs(m["words"]["l"] - m["fig"]["r"]) if side == "left" else abs(m["fig"]["l"] - m["words"]["r"])
                    self.assertLessEqual(abs(m["fig"]["w"] + m["words"]["w"] + gap - m["box"]["w"]), 1)
                    self.assertLessEqual(abs((m["fig"]["w"] / (m["fig"]["w"] + m["words"]["w"])) - part), 0.01, "the image takes its share of the width")
                    if side == "left":
                        self.assertLess(m["fig"]["r"], m["words"]["l"] + 1)
                    else:
                        self.assertLess(m["words"]["r"], m["fig"]["l"] + 1)
                    self.assertGreater(m["fig"]["w"], 100)
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1], "no sideways scroll")
                    self.assertGreaterEqual(m["box"]["l"], m["main"]["l"] - 1)
                    self.assertLessEqual(m["box"]["r"], m["main"]["r"] + 1)

    def test_fill_the_height_matches_the_words_and_the_other_shapes_keep_their_proportions(self):
        self.draw(content(), 1400)
        m = self.measure()
        self.assertLessEqual(abs(m["frame"]["t"] - m["words"]["t"]), 1, "the image starts with the words")
        self.assertLessEqual(abs(m["img"]["h"] - (m["words"]["h"] - (m["fig"]["h"] - m["frame"]["h"]))), 2, "as tall as the words (the caption under it is extra)")
        self.assertGreater(m["img"]["h"], 230)
        for shape, ratio in (("4:3", 4 / 3), ("square", 1.0)):
            self.draw(content(shape=shape), 1400)
            m = self.measure()
            with self.subTest(shape=shape):
                self.assertLessEqual(abs(m["img"]["w"] / m["img"]["h"] - ratio), 0.02)
        self.draw(content(shape="whole", image=uri(png(1200, 300))), 1400)
        self.assertTrue(wait(lambda: self.js("(function(){var i=document.querySelector('.tpl-sbs-frame img, .tpl-fig img');return !!i && i.complete && i.naturalWidth>0})()")))
        m = self.measure()
        self.assertLessEqual(abs(m["img"]["w"] / m["img"]["h"] - 4), 0.05, "the whole image is not cut")
        self.assertLessEqual(abs(m["frame"]["h"] - m["img"]["h"]), 1)
        self.draw(content(html="<p>Fictional short words.</p>"), 1400)
        m = self.measure()
        self.assertGreaterEqual(m["img"]["h"], 229, "never shorter than a small least height beside a very short text")

    def test_the_focus_sets_what_stays_in_view_and_the_framed_pixels_are_unchanged(self):
        self.draw(content(fx=200, fy=900), 1400)
        m = self.measure()
        self.assertEqual(m["pos"], "20% 90%")
        self.assertEqual(m["px"][:3], [200, 30, 30])
        self.assertEqual(m["px"][3:], [30, 30, 200])
        self.draw(content(), 1400)
        self.assertEqual(self.measure()["pos"], "50% 50%")

    def test_the_focus_edges_zero_and_one_thousand_are_carried_and_drawn_and_one_past_is_not(self):
        got = self.js(f"F.shown({json.dumps({'v': 2, 'html': '<p>x</p>', 'fx': 1000, 'fy': 0, 'pictures': {'image': IMG}})})")
        self.assertEqual(got["fx"], 1000, "1000 is the far edge and is kept")
        self.assertEqual(got["fy"], 0, "0 is a real focus, carried unless it is the centre")
        got = self.js(f"F.shown({json.dumps({'v': 2, 'html': '<p>x</p>', 'fx': 0, 'fy': 1000, 'pictures': {'image': IMG}})})")
        self.assertEqual([got["fx"], got["fy"]], [0, 1000])
        got = self.js(f"F.shown({json.dumps({'v': 2, 'html': '<p>x</p>', 'fx': 1001, 'fy': -1, 'pictures': {'image': IMG}})})")
        self.assertNotIn("fx", got)
        self.assertNotIn("fy", got)
        self.draw(content(fx=1000, fy=0), 1400)
        self.assertEqual(self.measure()["pos"], "100% 0%")

    def test_text_beside_a_short_image_starts_at_the_top(self):
        self.draw(content(shape="square", share="third"), 1400)
        m = self.measure()
        self.assertLessEqual(abs(m["words"]["t"] - m["fig"]["t"]), 1)

    # ---- themes, tools, text

    def test_both_themes_leave_the_image_alone_and_nothing_can_be_edited(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                self.draw(content(), width, theme)
                m = self.measure()
                with self.subTest(width=width, theme=theme):
                    self.assertEqual((m["filter"], m["opacity"]), ("none", "1"))
                    self.assertEqual(m["px"][:3], [200, 30, 30])
                    self.assertEqual(m["tools"], 0, "no tool, no dot, no description box")
                    self.assertEqual(m["alt"], "Fictional description")
                    self.assertEqual(m["cap"], "Fictional caption")
                    self.assertNotEqual(m["capColor"], self.js("getComputedStyle(document.querySelector('.tpl-sbs-words')).color"), "the caption is quieter than the words")
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1])
                    self.assertEqual(m["breakInside"], "avoid", "the image is not split across a printed page")

    def test_the_caption_is_one_line_of_text_never_markup_and_none_draws_nothing(self):
        self.draw(content(caption="<b>Fictional</b> & plan"), 1400)
        self.assertEqual(self.measure()["cap"], "<b>Fictional</b> & plan")
        self.assertEqual(self.js("document.querySelectorAll('figcaption b').length"), 0)
        self.draw(content(caption=""), 1400)
        self.assertIsNone(self.measure()["cap"])
        self.assertEqual(self.js("document.querySelectorAll('figcaption').length"), 0, "no empty box under the image")
        self.draw(content(alt=""), 1400)
        self.assertEqual(self.measure()["alt"], "", "no description is read as decoration, never invented")

    def test_old_lines_are_text_and_an_address_that_is_not_an_image_draws_nothing(self):
        self.draw(content(html=None, words=["Fictional <b>line</b> one", "Fictional line two"]), 1400)
        self.assertEqual(self.js("[...document.querySelectorAll('.tpl-sbs-words p')].map(function(e){return e.textContent})"), ["Fictional <b>line</b> one", "Fictional line two"])
        self.assertEqual(self.js("document.querySelectorAll('.tpl-sbs-words b').length"), 0)
        for bad in ("http://example.com/a.png", "javascript:alert(1)", "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=", "data:image/gif;base64,R0lGODlhAQABAAAAACw="):
            self.draw(content(image=bad), 1400)
            self.assertEqual(self.js("document.querySelectorAll('img, figure').length"), 0, bad)
            self.assertEqual(self.js("document.querySelectorAll('.tpl-sbs.no-pic').length"), 1, "the words are drawn alone")

    # ---- missing parts

    def test_no_image_is_the_words_only_no_words_is_the_image_only_and_neither_is_not_drawn(self):
        self.draw(content(image=None, caption=None, alt=None), 1400)
        m = self.measure()
        self.assertEqual((m["nfig"], m["nwords"]), (0, 1))
        self.assertLessEqual(abs(m["words"]["l"] - m["box"]["l"]), 1)
        self.assertLessEqual(abs(m["words"]["w"] - m["box"]["w"]), 1, "the words have the whole width")
        self.assertLessEqual(abs(m["box"]["h"] - m["words"]["h"]), 1, "no space above or below")
        self.draw(content(image=None, side="right", share="third"), 1400)
        self.assertLessEqual(abs(self.measure()["words"]["w"] - self.measure()["box"]["w"]), 1, "whatever the share")
        self.draw(content(html=None, side="right", share="third"), 1400)
        m = self.measure()
        self.assertEqual((m["nfig"], m["nwords"]), (1, 0))
        self.assertLessEqual(abs(m["fig"]["w"] - m["box"]["w"]), 1, "the image has the whole width")
        self.assertLessEqual(abs(m["fig"]["h"] - m["box"]["h"]), 1)
        self.js("F.mount({'id': 'ABC-S-001', 'type': 'textimage', 'content': {'sbs': 1, 'words': [], 'html': '<p> </p>'}}, 'full')")
        self.assertEqual(self.js("document.getElementById('root').innerHTML"), "", "nothing at all")

    # ---- half width

    def test_half_width_is_top_or_bottom_the_image_spans_the_section_and_fill_is_sixteen_by_nine(self):
        for slot in ("left", "right"):
            for hpos in ("top", "bottom"):
                # side and share are the FULL width choices: they change nothing here
                self.draw(content(half=hpos, side="left" if hpos == "top" else "right", share="third"), 1400, slot=slot)
                m = self.measure()
                with self.subTest(slot=slot, hpos=hpos):
                    self.assertLessEqual(abs(m["fig"]["w"] - m["box"]["w"]), 1, "the image spans the section")
                    self.assertLessEqual(abs(m["words"]["w"] - m["box"]["w"]), 1)
                    self.assertLessEqual(abs(m["img"]["w"] / m["img"]["h"] - 16 / 9), 0.02, "Wide (16:9)")
                    if hpos == "top":
                        self.assertLessEqual(m["fig"]["b"], m["words"]["t"] + 1)
                    else:
                        self.assertLessEqual(m["words"]["b"], m["fig"]["t"] + 1)
                    self.assertLess(m["box"]["w"], m["main"]["w"] * 0.55, "it is the half width cell")
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1])

    def test_each_width_keeps_its_own_choice(self):
        # one content, drawn full and half: the full width choice (left, a third) and the half width choice (bottom) are both in it
        c = content(side="left", share="third", half="bottom")
        self.draw(c, 1400)
        m = self.measure()
        self.assertLess(m["fig"]["r"], m["words"]["l"] + 1)
        self.assertLessEqual(abs(m["fig"]["w"] / (m["fig"]["w"] + m["words"]["w"]) - 1 / 3), 0.01)
        self.draw(c, 1400, slot="left")
        m = self.measure()
        self.assertLessEqual(m["words"]["b"], m["fig"]["t"] + 1, "half width: underneath")
        self.draw(c, 1400)
        m = self.measure()
        self.assertLess(m["fig"]["r"], m["words"]["l"] + 1, "back at full width: still left")
        self.assertLessEqual(abs(m["fig"]["w"] / (m["fig"]["w"] + m["words"]["w"]) - 1 / 3), 0.01, "and still a third")

    # ---- 900

    def test_at_900_a_full_width_section_stacks_left_above_and_right_below(self):
        for side, above in (("left", True), ("right", False)):
            for share in ("half", "third", "two"):
                self.draw(content(side=side, share=share), 900)
                m = self.measure()
                with self.subTest(side=side, share=share):
                    self.assertLessEqual(abs(m["fig"]["w"] - m["box"]["w"]), 1)
                    self.assertLessEqual(abs(m["words"]["w"] - m["box"]["w"]), 1)
                    if above:
                        self.assertLessEqual(m["fig"]["b"], m["words"]["t"] + 1)
                    else:
                        self.assertLessEqual(m["words"]["b"], m["fig"]["t"] + 1)
                    self.assertLessEqual(abs(m["img"]["w"] / m["img"]["h"] - 16 / 9), 0.02, "filling the height of words that are no longer beside it is Wide")
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1], "no sideways scroll")
                    self.assertGreaterEqual(m["box"]["l"], m["main"]["l"] - 1)
                    self.assertLessEqual(m["box"]["r"], m["main"]["r"] + 1)

    def test_at_900_a_half_width_section_keeps_its_top_or_bottom_and_stays_inside(self):
        for hpos in ("top", "bottom"):
            self.draw(content(half=hpos, side="left" if hpos == "bottom" else "right"), 900, slot="right")
            m = self.measure()
            with self.subTest(hpos=hpos):
                if hpos == "top":
                    self.assertLessEqual(m["fig"]["b"], m["words"]["t"] + 1)
                else:
                    self.assertLessEqual(m["words"]["b"], m["fig"]["t"] + 1)
                self.assertLessEqual(m["scroll"][0], m["scroll"][1])
                self.assertLessEqual(m["box"]["r"], m["main"]["r"] + 1)

    def test_half_width_bottom_from_the_servers_own_published_content_draws_under_the_words(self):
        # not hand-made content: a body with half-width position bottom goes through the server's own check and publish, and the View draws exactly what comes out
        from clark.section_kinds import textimage
        stored = textimage._check_v2({"v": 2, "html": WORDS, "half": "bottom", "pictures": {"original": IMG}})
        published = textimage._published_v2(stored)["content"]
        self.assertEqual(published.get("half"), "bottom", "the server publishes the half width position under the name the View reads")
        for width in (1400, 900):
            for how in ("published", "stored"):
                with self.subTest(width=width, how=how):
                    if how == "published":
                        self.draw(published, width, slot="right")      # exactly the content the server publishes, nothing added by hand
                        self.assertTrue(wait(lambda: self.js("(function(){var i=document.querySelector('.tpl-sbs-frame img');return !!i && i.complete && i.naturalWidth>0})()")), "the side by side layout drew the image")
                    else:
                        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                        self.js(f"F.mount({json.dumps({'id': 'ABC-S-001', 'type': 'textimage', 'body': json.dumps(stored)})}, 'right')")      # the stored body, as the editor and the served View read it
                        self.assertTrue(wait(lambda: self.js("(function(){var i=document.querySelector('.tpl-sbs-frame img');return !!i && i.complete && i.naturalWidth>0})()")))
                    m = self.measure()
                    self.assertLessEqual(m["words"]["b"], m["fig"]["t"] + 1, "half width bottom: the image is below the words")

    def test_other_shapes_at_900_stay_inside_and_keep_their_proportions(self):
        for shape, ratio in (("4:3", 4 / 3), ("square", 1.0)):
            self.draw(content(shape=shape, share="two"), 900)
            m = self.measure()
            with self.subTest(shape=shape):
                self.assertLessEqual(abs(m["img"]["w"] / m["img"]["h"] - ratio), 0.02)
                self.assertLessEqual(m["scroll"][0], m["scroll"][1])
                self.assertLessEqual(m["img"]["r"], m["main"]["r"] + 1)

    def test_a_long_word_does_not_push_the_page_sideways(self):
        for width in (1400, 900):
            self.draw(content(html="<p>" + "Fictional" * 40 + "</p>"), width)
            m = self.measure()
            self.assertLessEqual(m["scroll"][0], m["scroll"][1], width)

    def test_print_emulation_keeps_the_image_whole_and_the_same_pixels(self):
        self.draw(content(), 1400)
        self.cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, self.sid)
        try:
            m = self.measure()
            self.assertEqual(m["breakInside"], "avoid")
            self.assertEqual(m["px"][:3], [200, 30, 30])
        finally:
            self.cdp.call("Emulation.setEmulatedMedia", {"media": ""}, self.sid)


class Classic(Plumbing, unittest.TestCase):
    """The Classic layer is the style element with id theme (classicTheme() reads it); Cards has none."""
    classic = True

    def test_heading_is_drawn_above_and_none_draws_nothing(self):
        for color in ("light", "dark"):
            for width in (1400, 900):
                self.draw(content(heading="Fictional site visit"), width, color)
                with self.subTest(theme=color, width=width):
                    self.assertEqual(self.js("(document.querySelector('.tpl-sbs-heading')||{}).textContent"), "Fictional site visit")
                    self.assertLessEqual(self.js("document.querySelector('.tpl-sbs-heading').getBoundingClientRect().bottom"),
                                         self.js("document.querySelector('.tpl-sbs-frame').getBoundingClientRect().top + 1"))
        self.assertIsNone(self.js("document.querySelector('.tpl-sbs-heading').getAttribute('style')"), "the heading carries no inline style")
        self.assertEqual(self.js("(function(){var s = getComputedStyle(document.querySelector('.tpl-sbs-heading')); return [s.gridColumnStart, s.gridColumnEnd, s.marginTop, s.marginBottom];})()"),
                         ["1", "-1", "0px", "0px"], "the rules.css rule spans the grid with no margin")
        self.draw(content(), 1400)
        self.assertIsNone(self.js("document.querySelector('.tpl-sbs-heading')"), "no heading, none drawn")


class CardsHeading(Plumbing, unittest.TestCase):
    def test_cards_markup_has_no_heading(self):
        self.draw(content(heading="Fictional site visit"), 1400)
        self.assertIsNone(self.js("document.querySelector('.tpl-sbs-heading')"), "Cards draws what it drew before")


if __name__ == "__main__":
    unittest.main()
