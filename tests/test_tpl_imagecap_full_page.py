"""Row 1223 Full width image (store type 'imagecap', body version 2): the page parts, in a real browser on a bare page. The page's View and Edit parts
and its CSS are bundled with a stand-in for clark's two image/word routes that keeps the sections in memory and logs every call
(tests/fixtures/imagecap_full_demo.jsx), so the tests see exactly what the page sends and draws, at 1400 and 900 px, light and dark.
What clark's server does with those calls (the original slot, the framing numbers, the framed copy it makes) is the server part's own test
(test_imagecap_full_server.py); here the stand-in keeps the original as the framed copy, so the tests check what the page SENDS.

Run: python3 dev/run_tests.py test_tpl_imagecap_full_page
Needs Chrome (the #33 harness): fails, never skips, without it. Fictional data only.
"""
import base64
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from test_server import Running, chrome, wait

PAGE = SRC / "clark" / "page"
DEMO = ROOT / "tests" / "fixtures" / "imagecap_full_demo.jsx"
_HTML = {}

HELPERS = """
window.mk = (w, h, kind) => { const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d');
  g.fillStyle = 'rgb(40,160,60)'; g.fillRect(0, 0, w, h);
  if (kind === 'bands') { g.fillStyle = 'rgb(220,30,30)'; g.fillRect(0, 0, w, h / 6); g.fillStyle = 'rgb(30,30,220)'; g.fillRect(0, h * 5 / 6, w, h / 6); }
  if (kind === 'quad') { g.fillStyle = 'rgb(220,30,30)'; g.fillRect(0, 0, w / 2, h / 2); g.fillStyle = 'rgb(30,30,220)'; g.fillRect(w / 2, h / 2, w / 2, h / 2); }
  return c; };
window.drop = async (w, h, kind) => { const blob = await new Promise(r => window.mk(w, h, kind).toBlob(r, 'image/png'));
  const dt = new DataTransfer(); dt.items.add(new File([blob], 'fictional.png', { type: 'image/png' }));
  const i = document.querySelector('input[type=file]'); i.files = dt.files; i.dispatchEvent(new Event('change', { bubbles: true })); return true; };
window.px = (url) => new Promise(res => { const im = new Image(); im.onload = () => { const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight;
  const g = c.getContext('2d'); g.drawImage(im, 0, 0); const d = g.getImageData(0, 0, c.width, c.height).data; let red = 0, blue = 0, green = 0;
  for (let i = 0; i < d.length; i += 4) { if (d[i] > 150 && d[i + 1] < 90) red++; else if (d[i + 2] > 150 && d[i] < 90) blue++; else if (d[i + 1] > 100 && d[i] < 90) green++; }
  res({ w: im.naturalWidth, h: im.naturalHeight, red, blue, green }); }; im.src = url; });
"""


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
        css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "clark" / "brand" / "tokens.css", PAGE / "shell.css", PAGE / "src" / "edit" / "edit.css"))
        _HTML["html"] = ('<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title>'
                         f'<style>{css}</style></head>\n<body><script id="clark-boot" type="application/json">{{"token":"t"}}</script>'
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

    # -- helpers --
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

    def setup_page(self, width=1400, theme="light"):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1400, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", self.sid)

    def mount(self, body=None, mode="edit", width=1300, page=1400, theme="light"):
        self.setup_page(page, theme)
        text = json.dumps(json.dumps(body)) if body else '""'      # built first: Python 3.9 takes no same-type quote inside an f-string
        self.val(f"F.mount({{id: 'ABC-S-1', body: {text}}}, {json.dumps(mode)}, {width})")
        self.until("document.querySelector('#root').children.length", "drawn")

    def calls(self):
        return self.val("F.server.calls")

    def body(self):
        return self.val("F.body('ABC-S-1')")

    def width_of(self, url):
        raw = base64.b64decode(url.split(",", 1)[1])
        return int.from_bytes(raw[16:20], "big") if raw[:8] == b"\x89PNG\r\n\x1a\n" else None

    def add(self, w=2400, h=1200, kind="bands"):
        self.mount()
        self.val(f"drop({w}, {h}, {json.dumps(kind)})", True)
        self.until("document.querySelector('.fi-stage') && document.querySelector('[role=toolbar]')", "the image is in")
        return self.body()

    def settled(self, n):
        self.until(f"F.server.calls.length >= {n}", f"{n} calls, got {[(c.get('slot'), c.get('op'), c.get('bytes')) for c in self.calls()]}; page: {self.val('document.body.innerText.slice(-300)')}")
        self.until("!document.querySelector('.fi-bar[data-busy]') || document.querySelector('.fi-crop')", "no longer busy")

    def click(self, sel):
        self.val(f"document.querySelector({json.dumps(sel)}).click()")

    def height(self):
        return self.val("document.querySelector('.fi-stage').getBoundingClientRect().height")

    def mouse(self, kind, x, y, buttons=0):
        self.cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left" if kind != "mouseMoved" or buttons else "none", "buttons": buttons, "clickCount": 1 if kind != "mouseMoved" else 0}, self.sid)

    def drag(self, sel, dx, dy, move=True):
        self.val(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{block: 'center'}})")
        r = self.val(f"(function(){{const r = document.querySelector({json.dumps(sel)}).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];}})()")
        x, y = r
        self.mouse("mouseMoved", x, y)
        self.mouse("mousePressed", x, y, 1)
        if move:
            for i in range(1, 5):
                self.mouse("mouseMoved", x + dx * i / 4, y + dy * i / 4, 1)
        self.mouse("mouseReleased", x + (dx if move else 0), y + (dy if move else 0))

    def press(self, key):
        self.val(f"(function(){{const e = document.activeElement; e.dispatchEvent(new KeyboardEvent('keydown', {{key: {json.dumps(key)}, bubbles: true, cancelable: true}})); return true;}})()")

    def key(self, sel, key, shift=False):
        self.val(f"(function(){{const e = document.querySelector({json.dumps(sel)}); e.focus(); e.dispatchEvent(new KeyboardEvent('keydown', {{key: {json.dumps(key)}, shiftKey: {str(shift).lower()}, bubbles: true, cancelable: true}})); return true;}})()")

    # -- the empty state, the toolbar, the words --
    def test_no_image_is_one_drop_area_and_nothing_else(self):
        self.mount()
        self.assertEqual(self.val("[...document.querySelectorAll('[role=toolbar]')].length"), 0)
        self.assertEqual(self.val("document.querySelector('.fi-drop button').textContent"), "Choose an image")
        self.assertTrue(self.val("/drop one here/.test(document.querySelector('.fi-drop').textContent)"))
        self.assertEqual(self.val("document.querySelectorAll('[data-rich=caption], .ProseMirror').length"), 0)
        self.assertEqual(self.val("document.querySelectorAll('.fi-stage').length"), 0)
        self.assertEqual(self.val("F.view.isEmpty({id: 'x', type: 'imagecap', body: '{\"v\":2,\"caption\":\"Fictional\"}'})"), True)

    def test_one_toolbar_with_names_tips_and_arrow_keys(self):
        self.add()
        self.assertEqual(self.val("document.querySelectorAll('[role=toolbar]').length"), 1)
        names = self.val("[...document.querySelectorAll('[role=toolbar] button')].map(b => b.getAttribute('aria-label'))")
        self.assertEqual(names[:6], ["Whole image", "Shape 16:9", "Strip 3:1", "Free height", "Crop...", "Reset"])
        self.assertEqual(names[-2:], ["Replace image", "Remove image"])
        self.assertEqual(self.val("[...document.querySelectorAll('[role=toolbar] button')].every(b => b.getAttribute('aria-label') && b.dataset.tip)"), True)
        self.assertEqual(self.val("[...document.querySelectorAll('[role=toolbar] button')].filter(b => b.tabIndex === 0).length"), 1, "one tab stop")
        self.assertEqual(self.val("document.querySelectorAll('[role=toolbar] button[data-act^=fit], [role=toolbar] button[data-act^=fill]').length"), 0, "a big image has no Centre, Stretch or Fill")
        first = self.val("(function(){const b = document.querySelector('[role=toolbar] button'); b.focus(); return b.getAttribute('aria-label');})()")
        self.assertEqual(first, "Whole image")
        self.press("ArrowRight")
        self.assertEqual(self.val("document.activeElement.getAttribute('aria-label')"), "Shape 16:9")
        self.press("End")
        self.assertEqual(self.val("document.activeElement.getAttribute('aria-label')"), "Remove image")
        self.press("ArrowRight")
        self.assertEqual(self.val("document.activeElement.getAttribute('aria-label')"), "Whole image", "it wraps")

    def test_the_word_is_image_never_picture(self):
        self.add()
        self.click("[data-act=caption-add]")
        text = self.val("document.body.innerText + [...document.querySelectorAll('[aria-label], [data-tip], [title], [placeholder]')].map(e => [e.getAttribute('aria-label'), e.dataset.tip, e.title, e.placeholder].join(' ')).join(' ')")
        self.assertNotIn("picture", text.lower())
        self.assertIn("Describe the image", text)

    # -- adding an image: what is sent, and what the file note says --
    def test_adding_sends_only_the_original_never_a_framed_copy_and_never_the_words_with_it(self):
        body = self.add(2400, 1200)
        calls = self.calls()
        self.assertEqual([(c["path"], c.get("slot")) for c in calls], [("/api/section-image", "original")], "one image, one step, one Undo")
        self.assertEqual(self.width_of(body["pictures"]["original"]), 2400)
        self.assertEqual(body["v"], 2)
        self.assertNotIn("info", body)
        self.assertNotIn("frame", body)
        self.assertIn("2,400 px", self.val("document.querySelector('[data-file-note]').textContent"))

    def test_a_large_image_is_made_smaller_a_middle_one_is_left_and_a_small_one_not_enlarged(self):
        big = self.add(5200, 1300, "quad")
        self.assertEqual(self.width_of(big["pictures"]["original"]), 3000)
        self.assertEqual(big["from_w"], 5200, "the width it had is a note kept with the words")
        self.assertEqual([(c["path"], c.get("slot")) for c in self.calls()], [("/api/section-image", "original"), ("/api/section-body", None)])
        self.until("document.querySelector('[data-file-note]').textContent.indexOf('made smaller') > 0", "the note")
        self.assertEqual(self.val("document.querySelector('[data-file-note]').textContent"), "5,200 px, made smaller for print to 3,000 px")
        mid = self.add(1800, 900)
        self.assertEqual(self.width_of(mid["pictures"]["original"]), 1800)
        self.assertNotIn("from_w", mid)
        note = self.val("document.querySelector('[data-file-note]').textContent")
        self.assertIn("1,800 px: sharp on screen, about 180 dpi if printed full width, below the 300 dpi target", note)
        small = self.add(500, 300)
        self.assertEqual(self.width_of(small["pictures"]["original"]), 500)
        self.assertIn("centred at its own size", self.val("document.querySelector('[data-file-note]').textContent"))

    # -- framing: whole numbers sent with the words; clark makes the framed copy --
    def test_the_banner_shape_is_sent_as_a_number_and_the_original_is_kept_whole(self):
        self.add(2400, 1200, "bands")
        orig = self.body()["pictures"]["original"]
        self.click("[data-act=shape-banner]")
        self.settled(2)
        body = self.body()
        self.assertEqual(body["shape"], "banner")
        for key in ("fx", "fy", "crop", "ratio", "fit", "fill"):
            self.assertNotIn(key, body, "a default is not stored")
        self.assertEqual(body["pictures"]["original"], orig, "the original is not touched")
        self.assertEqual([(c["path"], c.get("slot")) for c in self.calls()], [("/api/section-image", "original"), ("/api/section-body", None)], "no image sent: clark makes the framed copy")
        self.assertNotIn("pictures", json.loads(self.calls()[1]["changes"]["body"]), "the words never carry an image")
        self.assertEqual(self.val("document.querySelector('[data-act=shape-banner]').getAttribute('aria-pressed')"), "true")

    def test_a_jpeg_original_is_sent_as_a_png_before_a_shape_because_clark_cuts_only_a_png(self):
        self.setup_page()
        jpeg = self.val("window.mk(1200, 600, 'bands').toDataURL('image/jpeg', 0.9)")
        self.mount({"v": 2, "pictures": {"original": jpeg, "image": jpeg}}, "edit")
        self.until("document.querySelector('[role=toolbar]')", "the image")
        self.click("[data-act=shape-banner]")
        self.settled(2)
        calls = self.calls()
        self.assertEqual([(c["path"], c.get("slot")) for c in calls], [("/api/section-image", "original"), ("/api/section-body", None)])
        self.assertTrue(calls[0]["image"].startswith("data:image/png;base64,"))
        self.assertEqual(self.body()["shape"], "banner")
        # and a whole-image change (a fill) of a JPEG sends no image at all
        self.mount({"v": 2, "pictures": {"original": jpeg, "image": jpeg}}, "edit")
        self.until("document.querySelector('[role=toolbar]')", "the image")
        self.click("[data-act=reset]")                      # nothing to reset: the button is off
        self.assertEqual(self.calls(), [])

    def test_the_focus_dot_is_sent_as_thousandths_and_reset_takes_the_framing_off(self):
        self.add(2400, 1200, "bands")
        self.click("[data-act=shape-banner]")
        self.settled(2)
        self.assertEqual(self.val("document.querySelectorAll('[data-focus-dot]').length"), 1)
        for _ in range(10):
            self.key("[data-focus-dot]", "ArrowUp")
        self.settled(3)
        body = self.body()
        self.assertEqual(body["fy"], 0)
        self.assertNotIn("fx", body)
        n = len(self.calls())
        self.click("[data-act=reset]")
        self.settled(n + 1)
        back = self.body()
        for key in ("shape", "fx", "fy", "crop", "ratio"):
            self.assertNotIn(key, back)
        self.assertEqual(back["pictures"]["original"], body["pictures"]["original"])
        self.assertEqual(self.val("document.querySelector('[data-act=reset]').disabled"), True, "nothing left to reset")

    def test_crop_is_sent_as_a_box_of_thousandths_and_the_whole_image_comes_back(self):
        self.add(2400, 1200, "quad")
        self.click("[data-act=crop]")
        self.until("document.querySelector('.fi-crop-box')", "the crop box")
        self.assertEqual(self.val("document.querySelectorAll('[role=toolbar]').length"), 0, "the bar steps aside while cropping")
        self.assertEqual(self.val("document.querySelectorAll('.fi-crop-h[title]').length"), 4, "each corner has its name")
        self.click("[data-act=crop-cancel]")
        self.until("document.querySelector('[role=toolbar]')", "back")
        self.assertEqual(len(self.calls()), 1, "Cancel saves nothing")
        self.click("[data-act=crop]")
        self.until("document.querySelector('.fi-crop-box')", "the crop box")
        self.key("[data-crop-box]", "ArrowRight")                      # move the box by 2 percent
        self.click("[data-act=crop-apply]")
        self.settled(2)
        self.assertEqual(self.body()["crop"], [120, 100, 920, 900])
        self.click("[data-act=crop]")
        self.until("document.querySelector('.fi-crop-box')", "the crop box")
        self.key("[data-crop-box]", "ArrowRight", shift=True)          # with Shift it resizes: 2 percent wider
        self.val("document.querySelector('[data-act=crop-apply]').click()")
        self.until("F.body('ABC-S-1').crop && F.body('ABC-S-1').crop[2] === 940", "resized")
        self.until("!document.querySelector('.fi-bar[data-busy]')", "done")
        self.click("[data-act=crop]")
        self.until("document.querySelector('.fi-crop-box')", "the crop box")
        self.click("[data-act=crop-whole]")
        self.until("document.querySelector('[role=toolbar]')", "back")
        self.until("!F.body('ABC-S-1').crop", "whole again")

    def test_free_starts_from_the_current_height(self):
        self.add(2400, 1200, "bands")
        before = self.height()                # the whole image: a ratio of 2, not any stored one
        self.click("[data-act=shape-free]")
        self.until("F.body('ABC-S-1').shape === 'free'", "free")
        self.assertAlmostEqual(self.height(), before, delta=1)
        self.assertAlmostEqual(self.body()["ratio"] / 1000, 1300 / before, places=2)
        self.assertIsInstance(self.body()["ratio"], int)

    # -- the height handle --
    def test_the_height_handle_picking_up_does_not_move_and_dragging_40_moves_40(self):
        self.add(2400, 1200, "bands")
        before = self.height()
        n = len(self.calls())
        self.drag("[data-height-handle]", 0, 0, move=False)
        self.assertEqual(self.height(), before, "picked up without moving: the same height")
        self.assertEqual(len(self.calls()), n, "and nothing is saved")
        self.drag("[data-height-handle]", 0, 40)
        self.until("F.body('ABC-S-1').shape === 'free'", "saved as free")
        self.until("!document.querySelector('.fi-bar[data-busy]')", "done")
        self.assertAlmostEqual(self.height(), before + 40, delta=1.5)

    def test_the_height_handle_on_a_small_image_goes_by_the_drawn_width(self):
        self.add(500, 300, "bands")
        before = self.height()
        self.assertAlmostEqual(before, 300, delta=1)                      # drawn at its own width, 500 wide (under 600 px: small)
        self.drag("[data-height-handle]", 0, 40)
        self.until("F.body('ABC-S-1').shape === 'free'", "saved")
        self.until("!document.querySelector('.fi-bar[data-busy]')", "done")
        self.assertAlmostEqual(self.height(), 340, delta=1.5)

    def test_the_height_has_limits_and_arrow_keys_move_it(self):
        self.add(2400, 1200, "bands")
        self.drag("[data-height-handle]", 0, -900)                        # far too flat: not flatter than 4:1
        self.until("F.body('ABC-S-1').shape === 'free'", "saved")
        self.until("!document.querySelector('.fi-bar[data-busy]')", "done")
        self.assertAlmostEqual(self.height(), 1300 / 4, delta=1.5)
        self.assertGreaterEqual(self.body()["ratio"], 250)
        self.assertLessEqual(self.body()["ratio"], 4000)
        self.drag("[data-height-handle]", 0, 1500)                        # too tall: at most 70 percent of the window
        self.until("!document.querySelector('.fi-bar[data-busy]')", "done")
        self.until("Math.abs(document.querySelector('.fi-stage').getBoundingClientRect().height - 980) < 2", "the 70 percent limit (of the 1400 px window)")
        h = self.height()
        self.key("[data-height-handle]", "ArrowUp")
        self.until(f"document.querySelector('.fi-stage').getBoundingClientRect().height < {h} - 5", "the arrow key made it lower")

    # -- a small image: centred at its own size, with a fill --
    def test_a_small_image_is_centred_with_a_fill_and_has_its_own_controls(self):
        self.add(500, 300, "bands")
        acts = self.val("[...document.querySelectorAll('[role=toolbar] button')].map(b => b.dataset.act)")
        for a in ("fit-centre", "fit-stretch", "fill-blur", "fill-brand", "fill-plain"):
            self.assertIn(a, acts)
        box = self.val("(function(){const s = document.querySelector('.fi-stage').getBoundingClientRect(), b = document.querySelector('.fi-box').getBoundingClientRect(); return [s.width, b.width, b.left - s.left, s.right - b.right];})()")
        self.assertAlmostEqual(box[1], 500, delta=1)
        self.assertAlmostEqual(box[2], box[3], delta=1)
        self.assertEqual(self.val("document.querySelectorAll('.fi-bg').length"), 1, "blurred copy by default")
        self.click("[data-act=fill-brand]")
        self.until("F.body('ABC-S-1').fill === 'brand'", "brand")
        self.until("!document.querySelector('.fi-bar[data-busy]')", "done")
        self.assertEqual(self.val("document.querySelectorAll('.fi-bg').length"), 0)
        self.assertEqual([(c["path"], c.get("slot")) for c in self.calls()], [("/api/section-image", "original"), ("/api/section-body", None)], "a fill is one change of words: no image is sent")
        self.click("[data-act=fit-stretch]")
        self.until("F.body('ABC-S-1').fit === 'stretch'", "stretch")
        self.until("!document.querySelector('.fi-bar[data-busy]')", "done")
        self.assertEqual(self.val("document.querySelectorAll('[data-act^=fill]').length"), 0, "no fill when it fills the width")
        self.assertAlmostEqual(self.val("document.querySelector('.fi-box').getBoundingClientRect().width"), 1300, delta=1)

    # -- row 1580: the small-image width is 600 px; the description is only asked for; the original is kept; dark mode --
    def test_the_small_image_rule_is_600_px_at_1400_and_900(self):
        small_acts = ("fit-centre", "fit-stretch", "fill-blur", "fill-brand", "fill-plain")
        for page, width in ((1400, 1300), (900, 800)):
            for theme in ("light", "dark"):
                with self.subTest(page=page, theme=theme):
                    self.mount(None, "edit", width, page, theme)
                    self.val("drop(500, 300, 'bands')", True)
                    self.until("document.querySelector('.fi-stage') && document.querySelector('[role=toolbar]')", "the 500 px image is in")
                    self.until("document.querySelector('.fi-pic').complete", "loaded")
                    acts = self.val("[...document.querySelectorAll('[role=toolbar] button')].map(b => b.dataset.act)")
                    for a in small_acts:
                        self.assertIn(a, acts, "a 500 px image is small: it has the small-image controls")
                    box = self.val("(function(){const s = document.querySelector('.fi-stage').getBoundingClientRect(), b = document.querySelector('.fi-box').getBoundingClientRect(); return [b.width, b.left - s.left, s.right - b.right];})()")
                    self.assertAlmostEqual(box[0], 500, delta=1, msg="drawn at its own size")
                    self.assertAlmostEqual(box[1], box[2], delta=1, msg="centred")
                    self.mount(None, "edit", width, page, theme)
                    self.val("drop(700, 400, 'bands')", True)
                    self.until("document.querySelector('.fi-stage') && document.querySelector('[role=toolbar]')", "the 700 px image is in")
                    self.until("document.querySelector('.fi-pic').complete", "loaded")
                    acts = self.val("[...document.querySelectorAll('[role=toolbar] button')].map(b => b.dataset.act)")
                    for a in small_acts:
                        self.assertNotIn(a, acts, "a 700 px image is not small: no small-image controls")
                    self.assertTrue(self.val("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_no_description_shows_the_quiet_red_note_and_a_description_removes_it(self):
        for page, width in ((1400, 1300), (900, 800)):
            for theme in ("light", "dark"):
                with self.subTest(page=page, theme=theme):
                    self.mount(None, "edit", width, page, theme)
                    self.val("drop(2400, 1200, 'bands')", True)
                    self.until("document.querySelector('.fi-stage') && document.querySelector('[role=toolbar]')", "the image is in")
                    self.assertEqual(self.val("document.querySelectorAll('[data-alt-note]').length"), 1, "no description: the note shows")
                    self.assertEqual(self.val("document.querySelector('label[for=\"tpl-ABC-S-1-alt\"]').textContent"), "Describe the image")
                    self.val("(function(){const i = document.querySelector('#tpl-ABC-S-1-alt'); i.value = 'x'; i.dispatchEvent(new Event('blur')); return true;})()")
                    self.until("F.body('ABC-S-1').alt === 'x'", "the description is saved")
                    self.until("!document.querySelector('[data-alt-note]')", "one character removes the note")

    def test_reset_after_a_save_and_reload_returns_the_whole_original(self):
        for page, width in ((1400, 1300), (900, 800)):
            for theme in ("light", "dark"):
                with self.subTest(page=page, theme=theme):
                    self.mount(None, "edit", width, page, theme)
                    self.val("drop(2400, 1200, 'quad')", True)
                    self.until("document.querySelector('.fi-stage') && document.querySelector('[role=toolbar]')", "the image is in")
                    self.click("[data-act=crop]")
                    self.until("document.querySelector('.fi-crop-box')", "the crop box")
                    self.key("[data-crop-box]", "ArrowRight")
                    self.click("[data-act=crop-apply]")
                    self.settled(2)
                    saved = self.body()
                    self.assertTrue(saved.get("crop"), "the crop is saved")
                    self.mount(saved, "edit", width, page, theme)                  # the reload: the editor opens on what was stored
                    self.until("document.querySelector('[role=toolbar]')", "the editor is back")
                    self.assertEqual(len(self.body()["pictures"]), 2, "the original and the framed copy are both stored")
                    self.until("!document.querySelector('[data-act=reset]').disabled", "Reset is on")
                    self.click("[data-act=reset]")
                    self.until("!F.body('ABC-S-1').crop", "the crop is off")
                    got = self.val("window.px(F.body('ABC-S-1').pictures.original)", True)
                    self.assertEqual((got["w"], got["h"]), (2400, 1200), "the whole original is back")

    def test_dark_mode_does_not_change_the_image_in_the_editor(self):
        for page, width in ((1400, 1300), (900, 800)):
            seen = []
            for theme in ("light", "dark"):
                self.mount(None, "edit", width, page, theme)
                self.val("drop(2400, 1200, 'bands')", True)
                self.until("document.querySelector('.fi-pic') && document.querySelector('.fi-pic').complete", "loaded")
                m = self.val("(function(){const p = document.querySelector('.fi-pic'), c = getComputedStyle(p); return [c.filter, c.opacity, p.getBoundingClientRect().width];})()")
                self.assertEqual(m[:2], ["none", "1"], (page, theme))
                seen.append(m)
            self.assertEqual(seen[0], seen[1], "dark draws the image as light does")

    # -- replacing and removing --
    def test_remove_takes_the_image_out_in_one_step_and_a_new_one_starts_from_no_framing(self):
        self.add(2400, 1200, "bands")
        self.click("[data-act=shape-banner]")
        self.settled(2)
        self.val("drop(1200, 600, 'bands')", True)
        self.until("F.server.calls.length >= 3", "replaced")
        self.until("!F.body('ABC-S-1').shape", "the new image starts whole")
        self.assertEqual(self.width_of(self.body()["pictures"]["original"]), 1200)
        self.click("[data-act=remove]")
        self.until("!F.body('ABC-S-1').pictures", "taken out")
        self.assertEqual(self.calls()[-1]["image"], None)
        self.assertEqual(self.body(), {"v": 2})
        self.until("document.querySelector('.fi-drop')", "back to the drop area")

    # -- the caption and the description --
    def test_a_caption_is_added_and_removed_and_nothing_is_drawn_without_one(self):
        self.add()
        self.assertEqual(self.val("document.querySelectorAll('.tpl-full-edit .ProseMirror, [data-rich=caption]').length"), 0)
        self.assertEqual(self.val("document.querySelector('[data-act=caption-add]').textContent"), "+ Add a caption")
        self.click("[data-act=caption-add]")
        self.until("document.querySelector('[data-rich=caption]')", "the caption field")
        self.assertEqual(self.val("document.querySelector('[data-act=caption-out]').textContent"), "Remove caption")
        n = len(self.calls())
        self.val("F.server.sections[0].body = JSON.stringify({...F.body('ABC-S-1'), caption: 'Fictional caption'}); true")
        self.val("document.querySelector('[data-act=caption-out]').click()")
        self.until(f"F.server.calls.length > {n}", "removed")
        self.until("!F.body('ABC-S-1').caption", "no caption stored")
        self.assertEqual(self.body()["v"], 2, "the words keep their version")
        self.until("!document.querySelector('[data-rich=caption]')", "the field is gone")
        self.assertEqual(self.val("document.querySelectorAll('[data-act=caption-add]').length"), 1)

    def test_remove_caption_sends_the_body_without_the_caption_and_keeps_the_rest(self):
        self.add()
        self.val("(function(){const i = document.querySelector('#tpl-ABC-S-1-alt'); i.value = 'Fictional plan'; i.dispatchEvent(new Event('blur')); return true;})()")
        self.until("F.body('ABC-S-1').alt === 'Fictional plan'", "the description is saved")
        self.click("[data-act=caption-add]")
        self.until("document.querySelector('[data-rich=caption]')", "the caption field")
        n = len(self.calls())
        self.val("F.server.sections[0].body = JSON.stringify({...F.body('ABC-S-1'), caption: 'Fictional caption'}); true")
        self.click("[data-act=caption-out]")
        self.until(f"F.server.calls.length > {n}", "removed")
        sent = json.loads(self.calls()[-1]["changes"]["body"])
        self.assertNotIn("caption", sent)
        self.assertEqual(sent["alt"], "Fictional plan")
        self.assertEqual(sent["v"], 2)

    def test_the_description_note_shows_until_there_is_one(self):
        self.add()
        self.assertEqual(self.val("document.querySelector('[data-alt-note]').textContent"), "Add a description, so someone who cannot see the image knows what it shows.")
        self.val("(function(){const i = document.querySelector('#tpl-ABC-S-1-alt'); i.value = 'Fictional plan'; i.dispatchEvent(new Event('blur')); return true;})()")
        self.until("F.body('ABC-S-1').alt === 'Fictional plan'", "saved")
        self.until("!document.querySelector('[data-alt-note]')", "the note is gone")
        self.assertEqual(self.body()["v"], 2)

    # -- the one View, as the published report draws it --
    def framed(self, w=1200, h=600, kind="bands"):
        return self.val(f"window.mk({w}, {h}, {json.dumps(kind)}).toDataURL('image/png')")

    def test_view_draws_the_image_and_a_caption_only_when_there_is_one(self):
        url = self.framed(1200, 600)
        for caption in ("Fictional caption", ""):
            body = {"v": 2, "alt": "Fictional plan", "pictures": {"image": url}, **({"caption": caption} if caption else {})}
            self.mount(body, "view")
            self.until("document.querySelector('.tpl-fullimg img.tpl-fullimg-img')", "the image")
            self.assertEqual(self.val("document.querySelector('.tpl-fullimg-img').alt"), "Fictional plan")
            self.assertEqual(self.val("document.querySelectorAll('figcaption').length"), 1 if caption else 0)
            self.assertEqual(self.val("document.querySelector('.tpl-fullimg').children.length"), 2 if caption else 1, "no empty box under the image")
            self.assertEqual(self.val("document.querySelectorAll('button, input, [role=slider], [role=toolbar], textarea').length"), 0, "no tools in View")

    def test_view_fits_at_1400_and_900_light_and_dark_and_a_small_one_is_centred(self):
        big = self.framed(2000, 800)
        small = self.framed(600, 300)
        for page, width in ((1400, 1300), (900, 800)):
            for theme in ("light", "dark"):
                self.mount({"v": 2, "pictures": {"image": big}}, "view", width, page, theme)
                self.until("document.querySelector('.tpl-fullimg-img').complete", "loaded")
                m = self.val("(function(){const i = document.querySelector('.tpl-fullimg-img').getBoundingClientRect(); return {fits: document.documentElement.scrollWidth <= window.innerWidth, img: i.width, filter: getComputedStyle(document.querySelector('.tpl-fullimg-img')).filter};})()")
                self.assertTrue(m["fits"], (page, theme))
                self.assertAlmostEqual(m["img"], width, delta=1)
                self.assertEqual(m["filter"], "none", "the theme does not change the image")
                self.mount({"v": 2, "pictures": {"image": small}}, "view", width, page, theme)
                self.until("document.querySelector('.tpl-fullimg-img').complete", "loaded")
                m = self.val("(function(){const s = document.querySelector('.tpl-fullimg-frame').getBoundingClientRect(), i = document.querySelector('.tpl-fullimg-img').getBoundingClientRect(); return {fits: document.documentElement.scrollWidth <= window.innerWidth, img: i.width, left: i.left - s.left, right: s.right - i.right, bg: document.querySelectorAll('.tpl-fullimg-blur').length};})()")
                self.assertTrue(m["fits"])
                self.assertAlmostEqual(m["img"], 600, delta=1)
                self.assertAlmostEqual(m["left"], m["right"], delta=1)
                self.assertEqual(m["bg"], 1)
                self.mount({"v": 2, "fit": "stretch", "pictures": {"image": small}}, "view", width, page, theme)
                self.until("document.querySelector('.tpl-fullimg-img').complete", "loaded")
                self.assertAlmostEqual(self.val("document.querySelector('.tpl-fullimg-img').getBoundingClientRect().width"), width, delta=1)

    def test_edit_fits_at_1400_and_900_light_and_dark(self):
        for page, width in ((1400, 1300), (900, 800)):
            for theme in ("light", "dark"):
                self.mount(None, "edit", width, page, theme)
                self.val("drop(2400, 1200, 'bands')", True)
                self.until("document.querySelector('.fi-stage')", "the stage")
                self.until("document.querySelector('.fi-pic').complete", "loaded")
                m = self.val("(function(){const s = document.querySelector('.fi-stage').getBoundingClientRect(), b = document.querySelector('.fi-bar').getBoundingClientRect(); return {fits: document.documentElement.scrollWidth <= window.innerWidth, stage: s.width, bar: b.right <= s.right + 1};})()")
                self.assertTrue(m["fits"] and m["bar"], (page, theme, m))
                self.assertAlmostEqual(m["stage"], width, delta=2)

    def test_the_published_image_is_the_framed_copy_view_reads_and_an_old_image_with_caption_still_draws(self):
        url = self.framed(900, 300, "bands")
        body = {"v": 2, "pictures": {"image": url, "original": self.framed(900, 900, "bands")}, "shape": "banner"}
        self.assertEqual(self.val(f"F.view.shown({json.dumps(body)}).image === {json.dumps(url)}"), True, "View reads the framed copy, never the original")
        self.assertEqual(self.val(f"JSON.stringify(F.view.shown({json.dumps(body)})).indexOf({json.dumps(body['pictures']['original'][40:120])})"), -1)
        self.mount({"v": 1, "caption": "Fictional old", "alt": "A", "pictures": {"image": url}}, "view")
        self.until("document.querySelector('.tpl-cap figure.tpl-fig img')", "the old Image with caption")
        self.assertEqual(self.val("document.querySelectorAll('.tpl-fullimg').length"), 0)
        self.assertEqual(self.val("document.querySelector('.tpl-cap figcaption').textContent"), "Fictional old")


if __name__ == "__main__":
    unittest.main()
