"""Row 1223, Full width image (an imagecap section with a body of version 2): the published side. The view part drawn on a bare page at 1400 and 900 px wide, in light and dark (the
image's own pixels do not change; no sideways scroll; no tools; the caption only when there is one; a small image centred with a fill each
side; the figure is not split across a printed page), and the Word report (the image as framed, its bytes in the file, the cropped part
not in it). Fictional data only.

Run: python3 dev/run_tests.py test_tpl_imagecap_full_view
Needs Chrome (the #33 harness) for the page tests.
"""
import base64
import contextlib
import io
import json
import re
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from _paths import ROOT, SRC
from clark import docx_build, docx_fullimage
from test_server import Running, chrome, wait

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "imagecap_full_view_demo.jsx"
_PAGE = {}


def chunk(name, data):
    import zlib
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)


def png(w, h, left=(200, 30, 30), right=(30, 30, 200)):
    """A real PNG, w x h, the left half one colour and the right half another."""
    import zlib
    row = b"\x00" + bytes(left) * (w // 2) + bytes(right) * (w - w // 2)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(row * h)) + chunk(b"IEND", b"")


def jpeg(w, h):
    """A JPEG's header as docx_fullimage reads it: SOI, a start-of-frame with the size, end."""
    return b"\xff\xd8\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00" + b"\xff\xd9"


def uri(raw, kind="png"):
    return f"data:image/{kind};base64," + base64.b64encode(raw).decode()


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
        assert wait(lambda: cls.cdp.js("!!window.F", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, code):
        return self.cdp.js(code, self.sid)

    def draw(self, content, width=1400, theme="light"):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
        self.js(f"F.mount({json.dumps({'id': 'ABC-S-001', 'type': 'imagecap', 'content': {**content, 'full': 1}})})")
        self.assertTrue(wait(lambda: self.js("(function(){var i=document.querySelector('.tpl-fullimg-img');return !!i && i.complete && i.naturalWidth>0})()")), "the image loaded")

    def measure(self):
        return self.js("""(function(){
          var f=document.querySelector('.tpl-fullimg'), i=document.querySelector('.tpl-fullimg-img'), m=document.querySelector('main');
          var r=f.getBoundingClientRect(), ir=i.getBoundingClientRect(), mr=m.getBoundingClientRect();
          var c=document.createElement('canvas'); c.width=i.naturalWidth; c.height=i.naturalHeight;
          var g=c.getContext('2d'); g.drawImage(i,0,0); var a=g.getImageData(1,1,1,1).data, b=g.getImageData(c.width-2,1,1,1).data;
          var cap=f.querySelector('figcaption');
          return {fig:[r.left,r.right,r.width], img:[ir.left,ir.right,ir.width,ir.height], main:[mr.left,mr.right],
                  natural:[i.naturalWidth,i.naturalHeight], scroll:[document.documentElement.scrollWidth, document.documentElement.clientWidth],
                  px:[a[0],a[1],a[2],b[0],b[1],b[2]], filter:getComputedStyle(i).filter, opacity:getComputedStyle(i).opacity,
                  alt:i.getAttribute('alt'), caption:cap?cap.textContent:null, capColor:cap?getComputedStyle(cap).color:null,
                  nfig:document.querySelectorAll('.tpl-fullimg').length, kids:f.children.length,
                  tools:document.querySelectorAll('button,input,textarea,select,[role=toolbar],[role=button]').length,
                  imgs:document.querySelectorAll('img').length, hidden:[...document.querySelectorAll('img[aria-hidden=true]')].length,
                  breakInside:getComputedStyle(f).breakInside, text:f.innerText};})()""")

    def test_shown_and_empty(self):
        self.assertTrue(self.js("F.ready"))
        big = uri(png(40, 10))
        self.assertIsNone(self.js(f"F.shown({json.dumps({'v': 2, 'caption': 'Fictional'})})"))
        self.assertEqual(self.js(f"F.shown({json.dumps({'v': 2, 'pictures': {'image': big}, 'alt': 'A'})})"), {"image": big, "caption": "", "alt": "A", "full": 1})
        self.assertEqual(self.js(f"F.shown({json.dumps({'v': 2, 'pictures': {'image': big}, 'fit': 'stretch', 'fill': 'brand'})})"),
                         {"image": big, "caption": "", "alt": "", "full": 1, "fit": "stretch", "fill": "brand"})
        self.assertEqual(self.js(f"F.shown({json.dumps({'v': 2, 'pictures': {'image': big}, 'fit': 'odd', 'fill': 'odd'})})"), {"image": big, "caption": "", "alt": "", "full": 1})
        # the old Image with caption is drawn and shown as it was
        self.assertEqual(self.js(f"F.shown({json.dumps({'v': 1, 'pictures': {'image': big}, 'alt': 'A', 'fill': 'brand'})})"), {"image": big, "caption": "", "alt": "A"})
        for sec, empty in (({"type": "imagecap", "body": json.dumps({"v": 2})}, True), ({"type": "imagecap", "content": {"image": "http://x/y.png", "full": 1}}, True),
                           ({"type": "imagecap", "content": {"image": big, "full": 1}}, False), ({"type": "imagecap", "body": json.dumps({"v": 1})}, True)):
            self.assertIs(self.js(f"F.isEmpty({json.dumps(sec)})"), empty, sec)

    def test_the_old_image_with_caption_is_drawn_as_before(self):
        self.js(f"F.mount({json.dumps({'id': 'ABC-S-001', 'type': 'imagecap', 'content': {'image': uri(png(40, 10)), 'caption': 'Fictional', 'alt': 'A'}})})")
        self.assertEqual(self.js("[document.querySelectorAll('.tpl-cap figure.tpl-fig img').length, document.querySelectorAll('.tpl-fullimg').length]"), [1, 0])

    def test_fills_the_width_at_1400_and_900_in_both_themes_with_the_same_pixels(self):
        content = {"image": uri(png(1600, 400)), "caption": "Fictional caption", "alt": "Fictional description"}
        seen = []
        for width in (1400, 900):
            for theme in ("light", "dark"):
                self.draw(content, width, theme)
                m = self.measure()
                with self.subTest(width=width, theme=theme):
                    self.assertLessEqual(abs(m["img"][2] - m["fig"][2]), 1, "the image fills the section's width")
                    self.assertLessEqual(abs(m["img"][3] * 4 - m["img"][2]), 4, "its shape (4:1) is kept")
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1], "no sideways scroll")
                    self.assertGreaterEqual(m["img"][0], m["main"][0] - 1)
                    self.assertLessEqual(m["img"][1], m["main"][1] + 1)
                    self.assertEqual((m["filter"], m["opacity"]), ("none", "1"), "the theme does not change the image")
                    self.assertEqual(m["px"][:3], [200, 30, 30])
                    self.assertEqual(m["px"][3:], [30, 30, 200])
                    self.assertEqual(m["alt"], "Fictional description")
                    self.assertEqual(m["caption"], "Fictional caption")
                    self.assertEqual(m["tools"], 0)
                    self.assertEqual(m["breakInside"], "avoid", "not split across a printed page")
                seen.append((width, round(m["img"][2])))
        self.assertLess(seen[2][1], seen[0][1], "at 900 px it is narrower")

    def test_no_caption_draws_nothing_under_the_image(self):
        self.draw({"image": uri(png(1600, 400)), "caption": "", "alt": ""})
        m = self.measure()
        self.assertIsNone(m["caption"])
        self.assertEqual((m["kids"], m["nfig"], m["text"]), (1, 1, ""))
        self.assertEqual(m["alt"], "", "no description is read as decoration, never invented")

    def test_an_address_that_is_not_a_real_image_draws_nothing(self):
        for bad in ("http://example.com/a.png", "javascript:alert(1)", "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=", "data:image/gif;base64,R0lGODlhAQABAAAAACw="):
            self.js(f"F.mount({json.dumps({'id': 'ABC-S-001', 'type': 'imagecap', 'content': {'image': bad, 'caption': 'Fictional', 'full': 1}})})")
            self.assertEqual(self.js("document.querySelectorAll('img, figure').length"), 0, bad)

    def test_caption_is_small_grey_text_never_markup(self):
        self.draw({"image": uri(png(800, 400)), "caption": "<b>Fictional</b> & plan", "alt": "x"})
        m = self.measure()
        self.assertEqual(m["caption"], "<b>Fictional</b> & plan")
        self.assertEqual(self.js("document.querySelectorAll('figcaption b').length"), 0)
        self.assertEqual(self.js("(function(){var s=getComputedStyle(document.querySelector('figcaption'));return parseFloat(s.fontSize) < parseFloat(getComputedStyle(document.body).fontSize) + 0.01})()"), True)
        self.assertNotEqual(m["capColor"], self.js("getComputedStyle(document.body).color"), "a quiet grey, not the body ink")

    def test_a_small_image_is_centred_at_its_own_size_with_a_fill_each_side(self):
        for fill in ("blur", "brand", "plain"):
            for width in (1400, 900):
                self.draw({"image": uri(png(600, 300)), "alt": "x", "fill": fill}, width)
                m = self.measure()
                with self.subTest(fill=fill, width=width):
                    self.assertEqual(round(m["img"][2]), 600, "its own size, not stretched")
                    left, right = m["img"][0] - m["fig"][0], m["fig"][1] - m["img"][1]
                    self.assertGreater(left, 20)
                    self.assertLessEqual(abs(left - right), 1, "centred")
                    self.assertEqual(m["imgs"], 2 if fill == "blur" else 1)
                    self.assertEqual(m["hidden"], 1 if fill == "blur" else 0, "the blurred copy is hidden from a screen reader")
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1])
                    bg = self.js("getComputedStyle(document.querySelector('.tpl-fullimg-frame')).backgroundColor")
                    self.assertEqual(bg == "rgba(0, 0, 0, 0)", fill == "plain", bg)
        self.draw({"image": uri(png(600, 300)), "alt": "x", "fill": "blur", "fit": "stretch"})
        m = self.measure()
        self.assertLessEqual(abs(m["img"][2] - m["fig"][2]), 1, "stretch fills the width")
        self.assertEqual(m["imgs"], 1)

    def test_a_small_image_wider_than_the_page_keeps_inside_at_900(self):
        self.draw({"image": uri(png(1100, 300)), "alt": "x", "fill": "plain"}, 900)
        m = self.measure()
        self.assertLessEqual(m["img"][1], m["main"][1] + 1)
        self.assertLessEqual(m["scroll"][0], m["scroll"][1])

    def test_print_emulation_keeps_the_figure_whole_and_the_same_pixels(self):
        self.draw({"image": uri(png(1600, 400)), "caption": "Fictional", "alt": "x"})
        self.cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, self.sid)
        try:
            m = self.measure()
            self.assertEqual(m["breakInside"], "avoid")
            self.assertEqual(m["px"][:3], [200, 30, 30])
        finally:
            self.cdp.call("Emulation.setEmulatedMedia", {"media": ""}, self.sid)

    def test_a_500_px_image_is_centred_and_a_700_px_image_keeps_its_own_width_at_1400_and_900(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.draw({"image": uri(png(500, 250)), "alt": "x", "fill": "plain"}, width, theme)
                    m = self.measure()
                    self.assertEqual(round(m["img"][2]), 500, "under 600 px: its own size, not stretched")
                    self.assertLessEqual(abs((m["img"][0] - m["fig"][0]) - (m["fig"][1] - m["img"][1])), 1, "centred: the gap each side is the same")
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1], "no sideways scroll")
                    self.draw({"image": uri(png(700, 350)), "alt": "x", "fill": "plain"}, width, theme)
                    m = self.measure()
                    self.assertLessEqual(abs(m["img"][2] - min(m["fig"][2], 700)), 1, "700 px: its own width, never wider than the section (row 1580 ruling: it does not fill)")
                    self.assertLessEqual(abs((m["img"][0] - m["fig"][0]) - (m["fig"][1] - m["img"][1])), 1, "centred: the gap each side is the same")
                    self.assertLessEqual(m["scroll"][0], m["scroll"][1], "no sideways scroll")

    def test_dark_mode_does_not_change_the_image_in_the_view_or_the_editor(self):
        content = {"image": uri(png(1600, 400)), "caption": "Fictional caption", "alt": "Fictional description"}
        for width in (1400, 900):
            seen = {}
            for theme in ("light", "dark"):
                self.draw(content, width, theme)
                m = self.measure()
                with self.subTest(width=width, theme=theme):
                    self.assertEqual((m["filter"], m["opacity"]), ("none", "1"), "no filter, opacity 1")
                    self.assertEqual(m["px"][:3], [200, 30, 30])
                    self.assertEqual(m["px"][3:], [30, 30, 200])
                seen[theme] = (m["px"], m["filter"], m["opacity"], m["img"][2])
            self.assertEqual(seen["light"], seen["dark"], "the dark view draws the same pixels as the light view")


def published(content, title="", full=True):
    return {"as_at": "2026-11-15", "data": {"project": {"code": "FIC", "name": "Fictional project"}, "actions": [], "raid": [], "decisions": [],
                                           "milestones": [], "use_cases": [], "documents": []},
            "sections": [{"id": "FIC-S-001", "type": "imagecap", "title": title, "beside": 0, "content": {**content, "full": 1} if full else content}], "tabs": ["dashboard"]}


def word_parts(content):
    data = docx_build.build(published(content))
    z = zipfile.ZipFile(io.BytesIO(data))
    return z, z.read("word/document.xml").decode(), z.namelist()


class Word(unittest.TestCase):
    def test_the_framed_image_is_carried_whole_with_its_caption(self):
        framed = png(1600, 400)
        z, doc, names = word_parts({"image": uri(framed), "caption": "Fictional caption", "alt": "Fictional description"})
        media = [n for n in names if n.startswith("word/media/")]
        self.assertEqual(len(media), 1)
        self.assertEqual(z.read(media[0]), framed, "the bytes in the Word file are the framed copy's")
        self.assertIn('descr="Fictional description"', doc)
        self.assertIn("Fictional caption", doc)
        m = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', doc)
        self.assertEqual(int(m.group(1)), docx_build.TEXT_W * 635, "as wide as the text")
        self.assertLessEqual(abs(int(m.group(1)) - int(m.group(2)) * 4), 4, "its shape kept")
        self.assertNotIn("Heading", doc.split("Fictional project")[-1], "no heading")
        self.assertIn('Extension="png"', z.read("[Content_Types].xml").decode())

    def test_no_caption_writes_no_caption_and_a_tall_image_fits_the_page(self):
        z, doc, _ = word_parts({"image": uri(png(400, 1600)), "caption": "", "alt": ""})
        self.assertEqual(doc.count("<w:drawing>"), 1)
        m = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', doc)
        self.assertLessEqual(int(m.group(2)), docx_fullimage.MAX_HEIGHT * 635 + 635 * 4)
        self.assertNotIn("keepNext", doc.split("<wp:inline")[0].rsplit("<w:p>", 1)[-1], "nothing under it to keep it with")

    def test_a_small_image_is_centred_at_its_own_size_and_a_jpeg_has_its_type(self):
        z, doc, names = word_parts({"image": uri(jpeg(600, 300), "jpeg"), "caption": "", "alt": "x", "fill": "brand"})
        m = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', doc)
        self.assertEqual(int(m.group(1)), 600 * 15 * 635)
        self.assertIn('<w:jc w:val="center"/>', doc)
        self.assertIn("w:fill=", doc)
        self.assertTrue(any(n.endswith(".jpeg") for n in names))
        self.assertIn('Extension="jpeg"', z.read("[Content_Types].xml").decode())
        z, doc, _ = word_parts({"image": uri(png(600, 300)), "alt": "x", "fit": "stretch"})
        self.assertEqual(int(re.search(r'<wp:extent cx="(\d+)"', doc).group(1)), docx_build.TEXT_W * 635)
        self.assertNotIn('<w:jc w:val="center"/>', doc)

    def test_an_image_that_cannot_be_read_is_left_out_not_half_written(self):
        for bad in ("", "http://example.com/a.png", "data:image/png;base64,AAAA", "data:image/webp;base64,AAAA", None):
            _, doc, names = word_parts({"image": bad, "caption": "Fictional lonely caption", "alt": "x"})
            self.assertNotIn("Fictional lonely caption", doc)
            self.assertEqual([n for n in names if "media" in n], [])

    def test_an_image_with_caption_of_the_old_kind_is_not_in_the_word_report_as_it_was_not_before(self):
        data = docx_build.build(published({"image": uri(png(100, 50)), "caption": "Fictional old caption", "alt": "x"}, full=False))
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertNotIn("Fictional old caption", z.read("word/document.xml").decode())
        self.assertEqual([n for n in z.namelist() if "media" in n], [])

    def test_the_same_image_twice_is_one_part_and_the_file_is_the_same_bytes_each_time(self):
        a = word_parts({"image": uri(png(100, 50))})[0]
        b = word_parts({"image": uri(png(100, 50))})[0]
        self.assertEqual(a.read("word/document.xml"), b.read("word/document.xml"))


class Sizes(unittest.TestCase):
    def test_the_header_readers(self):
        self.assertEqual(docx_fullimage.decode(uri(png(30, 20)))[2:], (30, 20))
        self.assertEqual(docx_fullimage.decode(uri(jpeg(30, 20), "jpeg"))[2:], (30, 20))
        self.assertIsNone(docx_fullimage.decode(uri(b"not an image")))
        self.assertIsNone(docx_fullimage.decode("data:image/png;base64,@@@"))


if __name__ == "__main__":
    unittest.main()
