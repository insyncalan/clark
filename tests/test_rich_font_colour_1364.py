"""Row 1364: font colour in the Classic rich text editor (toolbar and bubble button, palette, storage, save, the published file, Word, Excel).

Run: python3 dev/run_tests.py test_rich_font_colour_1364
The editor is the real RichText on a bare page (tests/_rich_page.py) with the Classic theme's CSS laid over the page's own (the app draws it
that way; the font colour rules live in the Theme, so the Cards page's style stays byte for byte), driven with real key events in headless
Chrome at 1400 and 900 px, light and dark. Fictional text only. The cleaners are tested in tests/test_rich_html_sanitise.py and
tests/test_clean_html_parity.py.
"""
import hashlib
import io
import json
import re
import sys
import unittest
import zipfile

import _rich_page as rp
from _demo import USER, DemoStore
from _paths import ROOT
from _publish import PublishedFile
from test_dark_contrast import ratio
from test_report_editor import EMPTY_BRANDING  # noqa: F401
from test_server import chrome, wait

from clark import changes, docx_build, excel, page, publish, sanitise, section_bodies
from clark import theme as themes

sys.path.insert(0, str(rp.TOOLS))

NAMES = ["Grey", "Brand", "Red", "Amber", "Green", "Blue"]
TOKEN = {"grey": "text-muted", "brand": "brand-blue", "red": "tone-red-text", "amber": "tone-amber-text", "green": "tone-green-text", "blue": "tone-blue-text"}
RULES = ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css"
TEXT = "<p>Some words to pick from</p>"
THEME_CSS = themes.css(themes.CLASSIC)


def rgb(text):
    return tuple(int(float(x)) for x in re.findall(r"[\d.]+", text)[:3])


def hexof(text):
    return "#%02X%02X%02X" % rgb(text)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = rp.Harness(chrome).__enter__()
        cls.h.ev(f"(function(){{ var s = document.createElement('style'); s.id = 'theme'; s.textContent = {json.dumps(THEME_CSS)}; document.head.appendChild(s); return true; }})()")

    @classmethod
    def tearDownClass(cls):
        cls.h.__exit__(None, None, None)

    def setUp(self):
        self.h.resize(1400)
        self.h.theme("light")

    def tearDown(self):
        self.h.ev("window.unmount(); true")
        self.h.resize(1400)
        self.h.theme("light")

    # --- helpers
    def probe(self, value, prop="color"):
        """What the browser makes of `value` (a var(--token), say) as a computed `prop`, so a token is compared by what it draws."""
        return self.h.ev(f"(function(){{ var e = document.createElement('i'); document.body.appendChild(e); e.style.{prop} = {json.dumps(value)};"
                         f"var c = getComputedStyle(e).{prop}; e.remove(); return c; }})()")

    def both(self):
        for width in (1400, 900):
            self.h.resize(width)
            yield width

    def settle(self):
        self.h.ev("window.settled = false; requestAnimationFrame(function(){ requestAnimationFrame(function(){ window.settled = true; }); }); true")
        self.assertTrue(self.h.until("window.settled === true"))

    def mount_selected(self, html=TEXT):
        self.h.mount(html)
        self.h.select_all()
        self.assertTrue(self.h.until("!!document.querySelector('.rt-bubble')"))

    def btn(self, where=".rt-bar"):
        return f"{where} [aria-label='Font colour']"

    def open_palette(self, where=".rt-bar"):
        self.h.ev(f"document.querySelector({json.dumps(self.btn(where))}).click(); true")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-pal')"), "the palette opened")

    def pick(self, name, where=".rt-bar"):
        self.open_palette(where)
        self.h.ev(f"document.querySelector('.rt-pal [aria-label={name}]').click(); true")
        self.assertTrue(self.h.until("!document.querySelector('.rt-pal')"), "the palette closed after the choice")
        self.settle()

    def press(self, key, vk, text=None, modifiers=0):
        for kind in ("keyDown", "keyUp"):
            args = {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": vk, "modifiers": modifiers}
            if text and kind == "keyDown":
                args["text"] = text
            self.h.cdp.call("Input.dispatchKeyEvent", args, self.h.sid)

    def rect(self, selector):
        return self.h.ev(f"(function(){{ var r = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return {{x: r.left, y: r.top, w: r.width, h: r.height, b: r.bottom, r: r.right}}; }})()")

    def style(self, selector, *props):
        return self.h.ev(f"(function(){{ var c = getComputedStyle(document.querySelector({json.dumps(selector)})); return [{', '.join('c.' + p for p in props)}]; }})()")


class Ui(Base):
    def test_button_after_strikethrough_toolbar_and_bubble(self):
        """AP1: after Strikethrough, 32 x 32 like its neighbours, in the toolbar and in the bubble, at 1400 and 900."""
        for width in self.both():
            with self.subTest(width=width):
                self.mount_selected()
                bar = self.h.ev("[...document.querySelectorAll('.rt-bar > button, .rt-bar > .rt-colour > button')].map(function(b){ return b.getAttribute('aria-label'); })")
                self.assertEqual(bar[bar.index("Strikethrough") + 1], "Font colour", bar)
                self.assertEqual(bar.count("Font colour"), 1)
                bubble = self.h.ev("[...document.querySelectorAll('.rt-bubble > button, .rt-bubble > .rt-colour > button')].map(function(b){ return b.getAttribute('aria-label'); })")
                self.assertEqual(bubble, ["Bold", "Italic", "Strikethrough", "Font colour", "Link"])
                for where in (".rt-bar", ".rt-bubble"):
                    r, s = self.rect(self.btn(where)), self.rect(f"{where} [aria-label=Strikethrough]")
                    self.assertEqual((r["w"], r["h"]), (32, 32), where)
                    self.assertEqual((r["w"], r["h"]), (s["w"], s["h"]), "like its neighbour")
                self.h.ev("window.unmount(); true")

    def test_existing_buttons_keep_their_order_size_and_keys(self):
        """AP21: the toolbar's other buttons keep their order and size with the new one added (test_rich_editor and test_sizes run unchanged beside this)."""
        self.h.mount(TEXT)
        labels = self.h.ev("[...document.querySelectorAll('.rt-bar button')].map(function(b){ return b.getAttribute('aria-label'); })")
        self.assertEqual(labels, ["Text style: Text", "Bold", "Italic", "Strikethrough", "Font colour", "Bulleted list", "Numbered list", "Checklist", "Quote", "Divider",
                                  "Link", "Undo", "Redo"])
        for name in ("Bold", "Italic", "Strikethrough", "Bulleted list", "Undo"):
            r = self.rect(f".rt-bar [aria-label='{name}']")
            self.assertEqual((r["w"], r["h"]), (32, 32), name)
        # Tab walks the toolbar in that order: Strikethrough, then Font colour, then the list button
        self.h.ev("document.querySelector(\".rt-bar [aria-label='Strikethrough']\").focus(); true")
        self.press("Tab", 9)
        self.assertEqual(self.h.ev("document.activeElement.getAttribute('aria-label')"), "Font colour")
        self.press("Tab", 9)
        self.assertEqual(self.h.ev("document.activeElement.getAttribute('aria-label')"), "Bulleted list")

    def test_glyph_underline_follows_current_colour(self):
        """AP2: a bold A with a 3px underline: the text colour when Automatic, the colour of the text at the selection otherwise."""
        for width in self.both():
            with self.subTest(width=width):
                self.mount_selected()
                w, bw, bs, bc = self.style(f"{self.btn()} .rt-A", "fontWeight", "borderBottomWidth", "borderBottomStyle", "borderBottomColor")
                self.assertEqual(w, "700")
                self.assertEqual((bw, bs), ("3px", "solid"))
                self.assertEqual(self.h.ev(f"document.querySelector({json.dumps(self.btn() + ' .rt-A')}).textContent"), "A")
                self.assertEqual(bc, self.probe("var(--text)"), "Automatic: the text colour")
                for n in NAMES:
                    self.pick(n)
                    self.assertEqual(self.style(f"{self.btn()} .rt-A", "borderBottomColor")[0], self.probe(f"var(--{TOKEN[n.lower()]})"), n)
                self.pick("Red")
                self.open_palette()
                self.h.ev("document.querySelector('.rt-pal-auto').click(); true")
                self.settle()
                self.assertEqual(self.style(f"{self.btn()} .rt-A", "borderBottomColor")[0], self.probe("var(--text)"), "back to Automatic")
                self.h.ev("window.unmount(); true")

    def test_palette_box_values(self):
        """AP3: 208 wide, padding 8, 1px grey-200 border, radius 8, the shadow, opening under the button; in the toolbar and in the bubble."""
        for width in self.both():
            for where in (".rt-bar", ".rt-bubble"):
                with self.subTest(width=width, where=where):
                    self.mount_selected()
                    self.open_palette(where)
                    pal, b = self.rect(".rt-pal"), self.rect(self.btn(where))
                    self.assertEqual(pal["w"], 208)
                    self.assertEqual((pal["y"] - b["b"], pal["x"]), (4, b["x"]), "under the button, its left edge on the button's")
                    self.assertLessEqual(pal["r"], width)
                    pad = self.style(".rt-pal", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft")
                    self.assertEqual(pad, ["8px"] * 4)
                    bw, bs, bc, rad, shadow = self.style(".rt-pal", "borderTopWidth", "borderTopStyle", "borderTopColor", "borderTopLeftRadius", "boxShadow")
                    self.assertEqual((bw, bs, rad), ("1px", "solid", "8px"))
                    self.assertEqual(bc, self.probe("var(--grey-200)"))
                    self.assertEqual(shadow, "rgba(14, 36, 48, 0.12) 0px 6px 18px 0px")
                    self.h.ev("window.unmount(); true")

    def test_automatic_line_size_tick(self):
        """AP4: the first line says Automatic, 32 high, with a tick when it is the choice."""
        for width in self.both():
            with self.subTest(width=width):
                self.mount_selected()
                self.open_palette()
                self.assertEqual(self.h.ev("document.querySelector('.rt-pal').firstElementChild === document.querySelector('.rt-pal-auto')"), True)
                self.assertEqual(self.h.ev("document.querySelector('.rt-pal-auto').firstChild.textContent"), "Automatic")
                self.assertEqual(self.rect(".rt-pal-auto")["h"], 32)
                self.assertEqual(self.h.ev("document.querySelector('.rt-pal-auto .rt-tick').textContent"), "✓", "no colour: Automatic is the choice")
                self.assertEqual(self.h.ev("document.querySelector('.rt-pal-auto').getAttribute('aria-checked')"), "true")
                self.h.key("Escape", 0, "Escape", 27)
                self.pick("Red")
                self.open_palette()
                self.assertEqual(self.h.ev("document.querySelector('.rt-pal-auto .rt-tick').textContent"), "", "a colour is chosen: no tick on Automatic")
                self.assertEqual(self.h.ev("document.querySelector('.rt-pal-auto').getAttribute('aria-checked')"), "false")
                self.h.ev("window.unmount(); true")

    def test_swatch_grid_layout(self):
        """AP5: six swatches, four to a row filling the grid (repeat(4, 1fr), column gap 6; 208 outer less border 2 and padding 16 is 190, so 43 wide), each 32 high, gap 6, radius 6, a 1px line, an A in the colour on the surface."""
        for width in self.both():
            with self.subTest(width=width):
                self.mount_selected()
                self.open_palette()
                sw = self.h.ev("[...document.querySelectorAll('.rt-pal .rt-sw')].map(function(e){ var r = e.getBoundingClientRect(), c = getComputedStyle(e);"
                               "return {x: r.left, y: r.top, w: r.width, h: r.height, text: e.textContent, border: c.borderTopWidth + ' ' + c.borderTopStyle, radius: c.borderTopLeftRadius, color: c.color}; })")
                self.assertEqual(len(sw), 6)
                grid = self.h.ev("(function(){ var g = document.querySelector('.rt-pal .rt-grid'), r = g.getBoundingClientRect(), p = document.querySelector('.rt-pal'), c = getComputedStyle(g), pc = getComputedStyle(p);"
                                 "return {gw: r.width, pw: p.getBoundingClientRect().width, pad: pc.paddingLeft, cols: c.gridTemplateColumns.split(' ').length, colgap: c.columnGap, rowgap: c.rowGap}; })()")
                self.assertEqual((grid["pw"], grid["pad"], grid["gw"], grid["cols"], grid["colgap"], grid["rowgap"]), (208, "8px", 190, 4, "6px", "6px"))
                self.assertTrue(all(s["h"] == 32 and abs(s["w"] - 43) < 0.01 for s in sw), "cells 43 wide (190 less three gaps of 6, over four), 32 high")
                self.assertAlmostEqual(sw[3]["x"] + sw[3]["w"] - sw[0]["x"], 190, 2, "four columns fill the grid (208 less 2 border and 16 padding; the ruling's 192 leaves out the 1px border)")
                self.assertEqual([s["y"] for s in sw[:4]], [sw[0]["y"]] * 4, "four in the first row")
                self.assertEqual(sw[4]["y"], sw[5]["y"])
                self.assertEqual(sw[4]["y"] - sw[0]["y"], 32 + 6, "two in the second row, a gap of 6 below")
                self.assertEqual([round(sw[i + 1]["x"] - sw[i]["x"] - sw[i]["w"], 2) for i in range(3)], [6] * 3, "a gap of 6 across")
                self.assertEqual(sw[4]["x"], sw[0]["x"])
                self.assertEqual(self.rect(".rt-pal-auto")["b"] + 6, sw[0]["y"], "the grid sits 6 under Automatic")
                self.assertTrue(all(s["border"] == "1px solid" and s["radius"] == "6px" and s["text"] == "A" for s in sw))
                for s, n in zip(sw, NAMES):
                    self.assertEqual(s["color"], self.probe(f"var(--{TOKEN[n.lower()]})"), n)
                self.h.ev("window.unmount(); true")

    def test_chosen_swatch_outline(self):
        """AP6: the chosen swatch has a 2px brand outline, offset 1; the others have none."""
        for width in self.both():
            with self.subTest(width=width):
                self.mount_selected()
                self.pick("Amber")
                self.open_palette()
                self.h.ev("document.querySelector('.rt-pal-auto').focus(); true")               # the focus ring is on Automatic, not on the swatch under test
                out = self.h.ev("[...document.querySelectorAll('.rt-pal .rt-sw')].map(function(e){ var c = getComputedStyle(e);"
                                "return [e.getAttribute('aria-label'), c.outlineStyle, c.outlineWidth, c.outlineOffset, c.outlineColor, e.getAttribute('aria-checked')]; })")
                for name, style, w, off, colour, checked in out:
                    if name == "Amber":
                        self.assertEqual((style, w, off, checked), ("solid", "2px", "1px", "true"))
                        self.assertEqual(colour, self.probe("var(--brand-blue)"))
                    else:
                        self.assertEqual((style, checked), ("none", "false"), name)
                self.h.ev("window.unmount(); true")

    def test_swatches_are_tokens_no_hex(self):
        """AP7: each class and each swatch is its token (Grey text-muted, Brand brand-blue, Red tone-red-text, Amber, Green, Blue), and none of the rules, the code or the stored text holds a hex."""
        css = RULES.read_text(encoding="utf-8")
        block = css[css.index("/* Row 1364"):]
        for name, token in TOKEN.items():
            self.assertIn(f".rt-c-{name} {{ color: var(--{token}); }}", block)
            self.assertRegex(block, rf"\.rt-A\[data-colour=\"{name}\"\] \{{ border-bottom-color: var\(--{token}\); \}} \.rt-sw-{name} \{{ color: var\(--{token}\); \}}")
        self.assertEqual(re.findall(r"#[0-9A-Fa-f]{3,8}\b", block), [], "no hex in the font colour rules")
        self.assertEqual(len(re.findall(r"\.rt-c-\w+ \{", block)), 6)
        for src in ("edit/RichText.jsx", "core/richHtml.js", "core/editor.js"):
            text = (rp.PAGE_SRC / src).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"""["']#[0-9A-Fa-f]{3,8}["']""", text), [], f"{src} holds no hex colour")
        self.mount_selected()
        for n in NAMES:
            self.pick(n)
        html = self.h.ev("document.querySelector('.ProseMirror').cxed.written()")
        self.assertEqual(re.findall(r"#|style=|rgb", html), [])
        self.assertEqual(self.h.ev("document.querySelectorAll('.ProseMirror [style]').length"), 0, "no style attribute in the editor's own text")
        for theme in ("light", "dark"):
            self.h.theme(theme)
            for n in NAMES:
                self.h.ev(f"document.querySelector('.ProseMirror').cxed.run('colour', {json.dumps(n.lower())}); true")
                self.assertEqual(self.style(".ProseMirror span", "color")[0], self.probe(f"var(--{TOKEN[n.lower()]})"), (theme, n))

    def test_swatch_contrast_4_5_light_and_dark(self):
        """AP8: each swatch's A against the swatch's surface, and each coloured word against the field's surface, is at least 4.5:1, light and dark, as drawn."""
        for theme in ("light", "dark"):
            self.h.theme(theme)
            self.mount_selected("<p>Some words</p>")
            self.open_palette()
            sw = self.h.ev("[...document.querySelectorAll('.rt-pal .rt-sw')].map(function(e){ var c = getComputedStyle(e); return [e.getAttribute('aria-label'), c.color, c.backgroundColor]; })")
            auto = self.h.ev("(function(){ var c = getComputedStyle(document.querySelector('.rt-pal')); return c.backgroundColor; })()")
            self.assertEqual(len(sw), 6)
            for name, fg, bg in sw:
                self.assertNotIn("rgba", bg, "the swatch has a solid surface")
                self.assertGreaterEqual(ratio(hexof(fg), hexof(bg)), 4.5, f"{theme} {name} {fg} on {bg}")
            surface = self.h.ev("getComputedStyle(document.querySelector('.rt')).backgroundColor")
            for n in NAMES:
                self.h.ev(f"document.querySelector('.ProseMirror').cxed.run('colour', {json.dumps(n.lower())}); true")
                colour = self.style(".ProseMirror span", "color")[0]
                self.assertGreaterEqual(ratio(hexof(colour), hexof(surface)), 4.5, f"{theme} {n} text on the field")
            self.assertEqual(hexof(auto), hexof(surface))
            self.h.ev("window.unmount(); true")

    def test_words_exact(self):
        """AP9: Font colour on the button; Grey, Brand, Red, Amber, Green, Blue as tooltip and aria-label; the first line Automatic; no other new word."""
        self.mount_selected()
        for where in (".rt-bar", ".rt-bubble"):
            self.assertEqual(self.h.ev(f"[document.querySelector({json.dumps(self.btn(where))}).getAttribute('aria-label'), document.querySelector({json.dumps(self.btn(where))}).title]"),
                             ["Font colour", "Font colour"])
        self.open_palette()
        self.assertEqual(self.h.ev("[...document.querySelectorAll('.rt-pal .rt-sw')].map(function(e){ return [e.getAttribute('aria-label'), e.title]; })"),
                         [[n, n] for n in NAMES])
        self.assertEqual(self.h.ev("document.querySelector('.rt-pal').getAttribute('aria-label')"), "Font colour")
        self.assertEqual(self.h.ev("[...document.querySelectorAll('.rt-pal button')].length"), 7)
        self.assertEqual(self.h.ev("document.querySelector('.rt-pal').innerText.replace(/\\s+/g, ' ').trim()"), "Automatic ✓ A A A A A A")

    def test_keyboard_open_move_choose_esc_focus_returns(self):
        """AP10: Tab reaches the button; Enter or Down opens the palette; arrows move over Automatic and the grid; Enter chooses; Esc closes with the focus on the button."""
        for width in self.both():
            with self.subTest(width=width):
                self.mount_selected("<p>Some words</p>")
                label = "document.activeElement.getAttribute('aria-label')"
                self.settle()
                self.h.ev("document.querySelector(\".rt-bar [aria-label='Strikethrough']\").focus(); true")
                self.assertTrue(self.h.until("document.activeElement.getAttribute('aria-label') === 'Strikethrough'"))
                self.press("Tab", 9)
                self.assertTrue(self.h.until("document.activeElement.getAttribute('aria-label') === 'Font colour'"), "Tab reaches the button")
                self.press("Enter", 13, "\r")
                self.assertTrue(self.h.until("!!document.querySelector('.rt-pal')"), "Enter opens it")
                self.assertEqual(self.h.ev("document.activeElement.classList.contains('rt-pal-auto')"), True)
                seen = []
                for key, vk in (("ArrowDown", 40), ("ArrowRight", 39), ("ArrowDown", 40), ("ArrowUp", 38), ("ArrowLeft", 37), ("ArrowUp", 38), ("ArrowLeft", 37)):
                    self.press(key, vk)
                    seen.append(self.h.ev("document.activeElement.getAttribute('aria-label') || document.activeElement.textContent.slice(0, 9)"))
                self.assertEqual(seen, ["Grey", "Brand", "Blue", "Brand", "Grey", "Automatic", "Blue"])
                self.press("Enter", 13, "\r")
                self.assertTrue(self.h.until("!document.querySelector('.rt-pal') && !!document.querySelector('.ProseMirror span.rt-c-blue')"), "Enter chooses")
                self.assertTrue(self.h.until("document.activeElement.classList.contains('ProseMirror')"), "the text has the focus again")
                self.h.ev("document.querySelector(\".rt-bar [aria-label='Font colour']\").focus(); true")
                self.press("ArrowDown", 40)
                self.assertTrue(self.h.until("!!document.querySelector('.rt-pal')"), "Down opens it")
                self.assertEqual(self.h.ev("document.activeElement.getAttribute('aria-label')"), "Blue", "it opens on the colour in use")
                self.press("Escape", 27)
                self.assertTrue(self.h.until("!document.querySelector('.rt-pal')"))
                self.assertEqual(self.h.ev(label), "Font colour", "Esc: the focus is back on the button")
                self.assertEqual(self.h.ev("window.ended"), 0, "Esc closed the palette, not the field")
                self.assertEqual(self.h.ev("window.saves.length"), 0)
                self.h.ev("window.unmount(); true")

    def test_apply_swatch_and_automatic_removes_span(self):
        """AP11: select text, pick a swatch, the text takes the colour (whole or part); Automatic removes the span and the text is the normal colour again."""
        for width in self.both():
            with self.subTest(width=width):
                self.mount_selected("<p>Some words to pick from</p>")
                normal = self.style(".ProseMirror p", "color")[0]
                self.pick("Red")
                self.assertEqual(self.h.ev("document.querySelector('.ProseMirror').cxed.written()"), '<p><span class="rt-c-red">Some words to pick from</span></p>')
                self.assertEqual(self.style(".ProseMirror span.rt-c-red", "color")[0], self.probe("var(--tone-red-text)"))
                self.assertEqual(self.h.ev("document.querySelectorAll('.ProseMirror span').length"), 1, "one span")
                self.pick("Green")                                                           # a new colour replaces the old: still one span
                self.assertEqual(self.h.ev("document.querySelector('.ProseMirror').cxed.written()"), '<p><span class="rt-c-green">Some words to pick from</span></p>')
                self.pick_automatic()
                self.assertEqual(self.h.ev("document.querySelector('.ProseMirror').cxed.written()"), TEXT)
                self.assertEqual(self.h.ev("document.querySelectorAll('.ProseMirror span').length"), 0, "Automatic removed the span")
                self.assertEqual(self.style(".ProseMirror p", "color")[0], normal)
                # part of the text, from the bubble
                self.h.ev("(function(){ var e = document.querySelector('.ProseMirror').cxed.editor; e.commands.setTextSelection({from: 6, to: 11}); return true; })()")
                self.assertTrue(self.h.until("!!document.querySelector('.rt-bubble')"))
                self.pick("Blue", ".rt-bubble")
                self.assertEqual(self.h.ev("document.querySelector('.ProseMirror').cxed.written()"), '<p>Some <span class="rt-c-blue">words</span> to pick from</p>')
                self.h.key("Enter", self.h.mod, "Enter", 13)
                self.assertTrue(self.h.until("window.saves.length === 1"))
                self.assertEqual(self.h.ev("window.saves"), ['<p>Some <span class="rt-c-blue">words</span> to pick from</p>'])
                self.h.ev("window.unmount(); true")

    def pick_automatic(self, where=".rt-bar"):
        self.open_palette(where)
        self.h.ev("document.querySelector('.rt-pal-auto').click(); true")
        self.assertTrue(self.h.until("!document.querySelector('.rt-pal')"))
        self.settle()

    def test_a_stored_colour_opens_coloured_and_untouched(self):
        """AP15 (the editor's half): a stored coloured field opens with the colour, comes back byte for byte, and the button shows its colour at the caret."""
        stored = '<p>a <span class="rt-c-red">red</span> and <span class="rt-c-grey">grey</span></p>'
        self.h.mount(stored)
        self.assertEqual(self.h.ev("document.querySelector('.ProseMirror').cxed.html()"), stored)
        self.assertEqual(self.h.ev("[...document.querySelectorAll('.ProseMirror span')].map(function(e){ return e.className; })"), ["rt-c-red", "rt-c-grey"])
        self.assertEqual(self.h.ev("document.querySelector('.ProseMirror').cxed.written()"), stored)

    def test_the_colour_button_is_Classic_only(self):
        """Review of PR 2196: the Cards page has no palette CSS, so with no Classic theme layer (no style#theme) the bar and the bubble have no colour button."""
        self.h.ev("document.getElementById('theme').id = 'theme-held'; true")
        try:
            self.mount_selected()
            self.assertEqual(self.h.ev("document.querySelectorAll('.rt-colour').length"), 0, "no colour button in the bar or the bubble on Cards")
            self.assertGreater(self.h.ev("document.querySelectorAll('.rt-bar button').length"), 3, "the rest of the bar is still there")
        finally:
            self.h.ev("window.unmount(); document.getElementById('theme-held').id = 'theme'; true")
        self.mount_selected()
        self.assertGreaterEqual(self.h.ev("document.querySelectorAll('.rt-colour').length"), 2, "Classic: one in the bar, one in the bubble")


class Colour(PublishedFile, unittest.TestCase):
    """Storage, save and reload, the published file, Word, Excel, plain-text fields and Cards, on a real store."""
    RED = '<p>See <span class="rt-c-red">the red words</span> now</p>'

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.change = changes.make_change(self.store.path, [], USER)

    def test_colour_survives_save_and_reload(self):
        """AP15: the colour goes through the real change route (every field a rich text field has) and is the same stored, read again and read by a new store."""
        action = self.demo.action(description="An action", client_message="A note for the client")
        ms = self.demo.milestone
        for kind, ref, field in (("actions", action, "latest_update"), ("milestones", ms, "description"), ("use_cases", self.demo.use_case, "standing")):
            with self.subTest(kind=kind, field=field):
                sent = self.change({"project": "ABC", "kind": kind, "op": "update", "id": ref, "changes": {field: self.RED}, "place": "peek"})
                self.assertNotIn("error", json.dumps(sent).lower()[:80], sent)
                self.assertEqual(self.store.read(kind, ref=ref)[field], self.RED)
        self.store.con.execute("UPDATE projects SET current_state = ? WHERE code = 'ABC'", (self.RED,))
        self.store.con.commit()
        self.assertEqual(self.store.read("projects", ref="ABC")["current_state"], self.RED)
        # a free class, a style and a hex written past the editor never come back
        sent = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": action, "changes": {"latest_update": '<p><span class="x" style="color:#f00">y</span></p>'}, "place": "peek"})
        self.assertEqual(self.store.read("actions", ref=action)["latest_update"], "<p>y</p>")

    def test_published_file_has_six_classes_and_colour_survives(self):
        """AP16: the published file carries the span, its stylesheet defines the six classes from the tokens, no inline style, and the colour shows."""
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", "ABC-S-005", {"body": self.RED})
        path = self.publish()
        text = path.read_text(encoding="utf-8")
        for name, token in TOKEN.items():
            self.assertRegex(text, rf"\.rt-c-{name} \{{ color: var\(--{token}\); \}}", f"the file's stylesheet defines rt-c-{name}")
        self.assertIn('\\u003cspan class=\\"rt-c-red\\"\\u003ethe red words', text, "the span is in the file's data")
        self.assertNotRegex(text, r"""<span[^>]* style=""")
        self.assertEqual(publish.outside_addresses(text), [], "the file's own checks find nothing")
        with chrome() as cdp:
            pg = self.draw(cdp, path)
            self.assertEqual(pg.js("document.querySelectorAll('span.rt-c-red').length"), 1)
            want = pg.js("(function(){ var e = document.createElement('i'); document.body.appendChild(e); e.style.color = 'var(--tone-red-text)'; var c = getComputedStyle(e).color; e.remove(); return c; })()")
            self.assertEqual(pg.js("getComputedStyle(document.querySelector('span.rt-c-red')).color"), want)
            self.assertEqual(pg.js("document.querySelectorAll('span.rt-c-red[style]').length"), 0, "no inline style")

    def test_published_peek_keeps_font_colour_1364(self):
        """AP22: a coloured run in a rich field stays coloured in the published file's data and in the peek it draws (the six fixed classes only)."""
        action = self.demo.action(description="An action", client_message="A note for the client")
        sent = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": action, "changes": {"latest_update": self.RED}, "place": "peek"})
        self.assertNotIn("error", json.dumps(sent).lower()[:80], sent)
        path = self.publish()
        text = path.read_text(encoding="utf-8")
        self.assertIn('\\u003cspan class=\\"rt-c-red\\"\\u003ethe red words', text, "the span is in the file's data")
        with chrome() as cdp:
            pg = self.draw(cdp, path)
            pg.js("[...document.querySelectorAll('.tab')].find(t => t.textContent.includes('Work items')).click()")
            self.assertTrue(wait(lambda: pg.js("!!document.querySelector('#work tr[data-id=\"%s\"]')" % action), 5), "the action's row is drawn")
            pg.js("document.querySelector('#work tr[data-id=\"%s\"]').click()" % action)
            self.assertTrue(wait(lambda: pg.js("document.querySelectorAll('aside.peek span.rt-c-red').length") == 1, 5), "the peek shows the red words")
            self.assertEqual(pg.js("document.querySelector('aside.peek span.rt-c-red').textContent"), "the red words")
            want = pg.js("(function(){ var e = document.createElement('i'); document.body.appendChild(e); e.style.color = 'var(--tone-red-text)'; var c = getComputedStyle(e).color; e.remove(); return c; })()")
            self.assertEqual(pg.js("getComputedStyle(document.querySelector('aside.peek span.rt-c-red')).color"), want)

    def test_word_export_colour_value(self):
        """AP17: Word writes each colour class as the token's concrete value of the palette in use (the committed look, and a brand's own values)."""
        def doc(colours=None, html=None):
            from test_docx_build import published, with_project
            data = docx_build.build(with_project(published(), current_state=html or "".join(f'<p><span class="rt-c-{n}">word-{n}</span></p>' for n in TOKEN)), colours)
            return zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
        palette = docx_build.palette()
        xml = doc()
        for name, token in TOKEN.items():
            self.assertRegex(xml, rf'<w:color w:val="{palette[token]}"/>(?:<w:sz [^>]*>)*</w:rPr><w:t xml:space="preserve">word-{name}<', name)
        self.assertEqual({n: docx_build.FONT_COLOUR_TOKEN[f"rt-c-{n}"] for n in TOKEN}, TOKEN, "the same six tokens as the stylesheet")
        own = {t: "%02X%02X%02X" % (i * 20 + 10, i * 20 + 20, i * 20 + 30) for i, t in enumerate(TOKEN.values())}
        xml = doc(own)
        for name, token in TOKEN.items():
            self.assertIn(f'<w:color w:val="{own[token]}"/>', xml)
            self.assertRegex(xml, rf'<w:color w:val="{own[token]}"/></w:rPr><w:t xml:space="preserve">word-{name}<')
        plain = doc(html="<p>plain words</p>")
        self.assertRegex(plain, r'<w:r><w:t xml:space="preserve">plain words</w:t></w:r>')
        after = doc(html='<p><span class="rt-c-red">red</span> then normal</p>')
        self.assertRegex(after, r'<w:r><w:t xml:space="preserve"> then normal</w:t></w:r>', "the colour ends with the span")
        self.assertNotIn("style=", xml)

    def test_excel_export_colour(self):
        """AP18 (PM ruling 22-11 02:40): Excel carries the plain words of a coloured run and no colour: no markup, and the cell's font is the plain cell's."""
        def book(html):
            rows = {"actions": [{"id": "a1", "description": "act", "latest_update": html}],
                    "use_cases": [{"id": "u1", "title": "uc", "headline": "h", "standing": html, "status": "Planned"}]}
            return excel.workbook("Demo", rows, on="2030-06-01")
        coloured, plain = book('<p>one <span class="rt-c-red">two</span> three</p>'), book("<p>one two three</p>")
        for sheet, label in (("Actions", "Latest update"), ("Use cases", "Where it stands")):
            for wb in (coloured, plain):
                ws = wb[sheet]
                col = [c.value for c in ws[1]].index(label) + 1
                self.assertEqual(ws.cell(row=2, column=col).value, "one two three")
            c1, c2 = coloured[sheet].cell(row=2, column=col), plain[sheet].cell(row=2, column=col)
            self.assertEqual((c1.font.color and c1.font.color.rgb, c1.font.b, c1.fill.fgColor.rgb), (c2.font.color and c2.font.color.rgb, c2.font.b, c2.fill.fgColor.rgb))
        cells = [str(c.value) for ws in coloured for row in ws.iter_rows() for c in row if c.value is not None]
        self.assertFalse([c for c in cells if "rt-c-" in c or "<span" in c or "<p" in c], "no markup anywhere in the workbook")
        blob = zipfile.ZipFile(io.BytesIO(self._xlsx(coloured)))
        self.assertEqual([n for n in blob.namelist() if "rt-c-" in blob.read(n).decode("utf-8", "replace")], [], "no part of the file names a colour class")

    @staticmethod
    def _xlsx(wb):
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_plain_text_fields_drop_colour(self):
        """AP19: the plain-words copy of the fields a template is handed (actions, RAID, decisions, milestones' update and client wording) never carries colour."""
        for kind in ("actions", "raid", "decisions", "milestones"):
            self.assertEqual(sanitise.rich_plain_text(self.RED), "See the red words now", kind)
        seen = {}
        real = section_bodies.Context

        def spy(rows, *a, **k):
            seen.setdefault("rows", rows)
            return real(rows, *a, **k)
        section_bodies.Context = spy
        self.addCleanup(setattr, section_bodies, "Context", real)
        self.demo.action(description="An action", client_message=self.RED, latest_update=self.RED)
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", self.demo.milestone, {"client_message": self.RED, "description": "d"})
        publish.select(publish.read_inputs(self.store, "ABC", "2026-10-29"))
        rows = seen["rows"]
        for kind, fields in (("actions", ("latest_update",)), ("milestones", ("client_message",))):
            got = [r for r in rows[kind] if any(r.get(f) for f in fields)]
            self.assertTrue(got, kind)
            for r in got:
                for f in fields:
                    self.assertNotIn("rt-c-", str(r.get(f)))
                    self.assertNotIn("<", str(r.get(f)))
        self.assertTrue(any(r.get("latest_update") == "See the red words now" for r in rows["actions"]))

    def test_cards_unchanged(self):
        """AP20: the Cards page's style is byte for byte what main has (md5 7195b310, every font colour rule is in the Classic Theme), and Cards' CSS holds no rt-c rule."""
        blocks = re.findall(r"<style[^>]*>(.*?)</style>", page.page_html(branding=page.NO_BRAND, theme=None), re.S)
        self.assertEqual([hashlib.md5(b.encode("utf-8")).hexdigest() for b in blocks], ["7195b3107c3b5022f3b40ad1dfbbe484"])
        self.assertTrue(all(".rt-c-" not in b and ".rt-pal" not in b for b in blocks))
        classic = re.findall(r"<style[^>]*>(.*?)</style>", page.page_html(branding=page.NO_BRAND, theme=themes.CLASSIC), re.S)
        self.assertTrue(any(".rt-c-red" in b and ".rt-pal" in b for b in classic), "Classic carries them")
        shell = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertNotIn("rt-c-", shell)
        self.assertNotIn("rt-pal", shell)


if __name__ == "__main__":
    unittest.main()
