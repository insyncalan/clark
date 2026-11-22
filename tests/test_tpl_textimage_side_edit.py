"""Row 1232 Text and Image Side by Side (store type 'textimage', body version 2): the Edit part, in a real browser on a bare page, at 1400 and 900 px.
The Edit part and its CSS (shell.css, edit.css and the Classic rules.css) are bundled with a stand-in for clark's image/word routes that keeps the
section in memory and logs every call (tests/fixtures/textimage_side_demo.jsx), so the tests see exactly what the page sends and draws. What clark's
server does with those calls is test_textimage_side_server.py; the Word export is test_docx_textimage_1232.py.

Run: python3 dev/run_tests.py test_tpl_textimage_side_edit
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
DEMO = ROOT / "tests" / "fixtures" / "textimage_side_demo.jsx"
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
        css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "clark" / "brand" / "tokens.css", PAGE / "shell.css", PAGE / "src" / "edit" / "edit.css", ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css"))
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

    def mount(self, body=None, page=1400, slot=""):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": page, "height": 1400, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        text = json.dumps(json.dumps(body)) if body else '""'
        self.val(f"F.mount({{id: 'ABC-S-1', body: {text}}}, 'edit', {min(page - 100, 1300)}, {json.dumps(slot)})")
        self.until("document.querySelector('#root').children.length", "drawn")

    def with_image(self, extra=None, page=1400, slot="", w=2400, h=1200):
        self.mount({"v": 2, **(extra or {})}, page, slot)
        self.val(f"drop({w}, {h}, 'bands')", True)
        self.until("document.querySelector('.tpl-sbs-bar')", "the toolbar is drawn")
        return self.body()

    def body(self):
        return self.val("F.body('ABC-S-1')")

    def calls(self):
        return self.val("F.server.calls")

    def acts(self):
        return self.val("[...document.querySelectorAll('.tpl-sbs-bar button')].map(b => b.dataset.act)")

    def click(self, act):
        self.val(f"document.querySelector('.tpl-sbs-bar [data-act=\"{act}\"]').click()")

    def settled(self, n):
        self.until(f"F.server.calls.length >= {n}", f"{n} calls, got {[(c.get('slot'), c.get('op')) for c in self.calls()]}")
        self.until("document.querySelector('.tpl-sbs-bar [data-act=replace]:not([disabled])') || document.querySelector('.fi-crop')", "no longer busy")

    def width_of(self, url):
        raw = base64.b64decode(url.split(",", 1)[1])
        return int.from_bytes(raw[16:20], "big") if raw[:8] == b"\x89PNG\r\n\x1a\n" else None

    # -- the toolbar offers this width's choices only --
    def test_full_width_offers_left_right_swap_and_three_shares_never_top_or_bottom(self):
        self.with_image()
        a = self.acts()
        self.assertIn("place-left", a); self.assertIn("place-right", a); self.assertIn("place-left", a)
        self.assertEqual([x for x in a if x.startswith("share-")], ["share-third", "share-half", "share-two"])
        self.assertNotIn("place-top", a); self.assertNotIn("place-bottom", a)
        self.assertEqual(self.val("document.querySelectorAll('.tpl-sbs-bar [data-act=\"swap\"]').length"), 1)

    def test_half_width_offers_top_bottom_swap_wide_and_no_shares(self):
        self.with_image(slot="left")
        a = self.acts()
        self.assertIn("place-top", a); self.assertIn("place-bottom", a); self.assertIn("swap", a)
        self.assertNotIn("place-left", a); self.assertNotIn("place-right", a)
        self.assertFalse([x for x in a if x.startswith("share-")])
        self.assertEqual(self.val("document.querySelector('[data-act=\"shape-fill\"]').getAttribute('aria-label')"), self.val("F.words.WORDS.wide"))

    def test_each_width_keeps_its_own_position(self):
        self.with_image()
        self.click("place-left")
        self.settled(2)
        self.assertEqual(self.body().get("side"), "left")
        self.mount(self.body(), slot="left")
        self.click("place-bottom")
        self.until("F.server.calls.length >= 1", "saved")
        b = self.body()
        self.assertEqual((b.get("half"), b.get("side")), ("bottom", "left"), "full keeps left while half is bottom")

    def test_swap_flips_this_width(self):
        self.with_image()
        n = len(self.calls())
        self.click("swap")
        self.settled(n + 1)
        self.assertEqual(self.body().get("side"), "left")
        self.click("swap")
        self.settled(n + 2)
        self.assertNotIn("side", self.body(), "right is the default: the key is taken out")

    # -- the ruled words (Row 1232 mock-up rulings) --
    def test_the_ruled_words_are_drawn(self):
        self.with_image(); self.until("document.querySelector('.tpl-sbs-bar')", "bar")
        groups = self.val("[...document.querySelectorAll('.tpl-sbs-bar [role=group]')].map(g => g.getAttribute('aria-label'))")
        self.assertEqual(groups, ["Shape", "Where the image sits", "Width of the image", "Crop"])
        self.assertEqual(self.val("document.querySelector('.tpl-sbs-bar [data-act=crop]').getAttribute('aria-label')"), "Crop\u2026")
        self.assertEqual(self.val("document.querySelector('#tpl-ABC-S-1-heading, .tpl-pic-field input').placeholder"), "optional")
        self.assertIn("optional", self.val("[...document.querySelectorAll('.tpl-pic-field')].map(f => f.textContent).join('|')"))
        W = self.val("F.words.WORDS")
        self.assertEqual((W["removed"], W["swapped"], W["drop"]), ("Image removed.", "Image and text swapped.", "or drop one here"))
        src = (PAGE / "src" / "edit" / "templates" / "TextImageSide.jsx").read_text(encoding="utf-8")
        self.assertIn("W.swapped", src, "Swap says Image and text swapped.")
        self.assertIn("hint={W.optional}", src.split("CaptionField section")[1].split("/>")[0], "Caption carries the hint optional")
        self.assertEqual(self.val("document.querySelector('.tpl-pic-lbl').textContent.trim()"), "Caption optional", "the hint sits beside the Caption label")

    def test_a_version_2_body_hands_over_to_the_side_edit_with_no_theme_gate_and_an_older_body_keeps_its_own(self):
        src = (PAGE / "src" / "edit" / "templates" / "TextImage.jsx").read_text(encoding="utf-8")
        self.assertIn("if (v.v === 2) return <SideEdit", src)
        self.assertNotIn("classicTheme", src, "Classic is the only theme (ticket 1363): no gate")

    def test_the_focus_dot_is_28_by_28_at_1400_and_the_shared_dot_rule_is_unchanged(self):
        self.with_image()
        self.assertEqual(self.val("(function(){ const r = document.querySelector('[data-focus-dot]').getBoundingClientRect(); return [r.width, r.height]; })()"), [28, 28])
        shared = (PAGE / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
        self.assertIn(".fi-dot { position: absolute; width: 22px; height: 22px;", shared, "the Full width image dot stays 22 px")
        rules = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        self.assertIn(".tpl-sbs-edit-frame .fi-dot {", rules, "the 28 px dot is scoped under .tpl-sbs-")

    # -- names and keys --
    def test_every_button_has_a_name_and_the_arrow_keys_move_along_the_toolbar(self):
        self.with_image()
        names = self.val("[...document.querySelectorAll('.tpl-sbs-bar button')].map(b => b.getAttribute('aria-label') || '')")
        self.assertTrue(names and all(names), names)
        self.assertEqual(self.val("document.querySelector('.tpl-sbs-bar').getAttribute('role')"), "toolbar")
        self.assertEqual(self.val("document.querySelector('.tpl-sbs-bar').getAttribute('aria-label')"), self.val("F.words.WORDS.toolbar"))
        self.assertEqual(self.val("document.querySelectorAll('.tpl-sbs-bar button[tabindex=\"0\"]').length"), 1, "one tab stop")
        self.val("document.querySelector('.tpl-sbs-bar button:not([disabled])').focus()")
        first = self.val("document.activeElement.dataset.act")
        self.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}, self.sid)
        self.assertNotEqual(self.val("document.activeElement.dataset.act"), first)
        self.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End", "windowsVirtualKeyCode": 35}, self.sid)
        self.assertEqual(self.val("document.activeElement.dataset.act"), "remove")

    # -- the upload cap --
    def test_a_large_image_is_made_smaller_to_3000_px_and_the_note_says_so_a_small_one_is_left_alone(self):
        self.mount({"v": 2})
        self.val("drop(5200, 1000, 'bands')", True)
        self.until("document.querySelector('.tpl-sbs-note')", "note")
        call = self.calls()[0]
        self.assertEqual((call["slot"], self.width_of(call["image"])), ("original", 3000))
        self.assertIn("3,000 px", self.val("document.querySelector('.tpl-sbs-note').textContent"))
        self.mount({"v": 2})
        self.val("drop(1800, 600, 'bands')", True)
        self.until("document.querySelector('.tpl-sbs-note')", "note")
        self.assertEqual(self.width_of(self.calls()[0]["image"]), 1800)

    # -- framing: shape, focus, crop, reset; one change each --
    def test_shape_crop_reset_each_one_change_and_reset_restores_the_whole(self):
        self.with_image()
        n = len(self.calls())
        self.click("shape-4:3")
        self.settled(n + 1)
        self.assertEqual(self.body().get("shape"), "4:3")
        self.click("crop")
        self.until("document.querySelector('.fi-crop')", "crop box")
        self.val("document.querySelector('[data-act=crop-apply]').click()")
        self.until("!document.querySelector('.fi-crop') && document.querySelector('.tpl-sbs-bar')", "applied")
        self.until("F.server.calls.length >= %d" % (n + 2), "crop saved")
        self.assertEqual(len(self.body().get("crop") or []), 4)
        self.click("reset")
        self.settled(n + 3)
        b = self.body()
        self.assertFalse({"shape", "crop", "fx", "fy"} & set(b), b)
        self.assertEqual(len(self.calls()), n + 3, "one change for each")

    def test_focus_dot_arrow_keys_move_the_focus_in_one_saved_step(self):
        self.with_image()
        n = len(self.calls())
        self.val("document.querySelector('[data-focus-dot]').focus()")
        self.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}, self.sid)
        self.until(f"F.server.calls.length >= {n + 1}", "saved after the keys stop")
        self.assertEqual(self.body().get("fx"), 550)
        self.assertEqual(self.val("document.querySelector('[data-focus-dot]').getAttribute('aria-label')"), self.val("F.words.WORDS.focus"))

    # -- the heading, the description --
    def test_heading_box_saves_and_no_description_is_asked_for_in_red(self):
        self.with_image()
        self.assertEqual(self.val("document.querySelector('[data-act]') && document.querySelector('.tpl-sbs-red').textContent"), self.val("F.words.WORDS.noDescription"))
        self.val("(function(){ const i = document.getElementById('tpl-ABC-S-1-heading'); i.focus(); i.value = 'The site visit'; i.blur(); })()")
        self.until("F.server.calls.some(c => c.changes)", "heading sent")
        self.assertEqual(self.body().get("heading"), "The site visit")

    # -- the layout at 1400 and 900 --
    def test_full_width_is_two_columns_at_1400_and_stacks_at_900_and_half_width_stacks(self):
        cols = "getComputedStyle(document.querySelector('.tpl-sbs-edit-grid')).gridTemplateColumns.split(' ').length"
        self.with_image(page=1400)
        self.assertEqual(self.val(cols), 2)
        self.with_image(page=1400, slot="left")
        self.assertEqual(self.val(cols), 1)
        # Not proved at 900 px while PAUSED_900 is set: the test is skipped at the next line and the 1400 checks above have run.
        self.with_image(page=900)
        self.assertEqual(self.val(cols), 1)
        self.assertFalse(self.val("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "no sideways scroll at 900")

    def test_left_puts_the_image_before_the_words_and_the_shares_change_the_columns(self):
        self.with_image({"side": "left", "share": "third"})
        self.assertTrue(self.val("document.querySelector('.tpl-sbs-edit-pic').getBoundingClientRect().left < document.querySelector('.tpl-sbs-edit-words').getBoundingClientRect().left"))
        w = self.val("(function(){ const a = document.querySelector('.tpl-sbs-edit-pic').getBoundingClientRect().width, b = document.querySelector('.tpl-sbs-edit-words').getBoundingClientRect().width; return a / b; })()")
        self.assertLess(w, 0.7, "a third of the width for the image")
        self.with_image({"side": "left", "share": "two"})
        w = self.val("(function(){ const a = document.querySelector('.tpl-sbs-edit-pic').getBoundingClientRect().width, b = document.querySelector('.tpl-sbs-edit-words').getBoundingClientRect().width; return a / b; })()")
        self.assertGreater(w, 1.5, "two thirds for the image")


if __name__ == "__main__":
    unittest.main()
