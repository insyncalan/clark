"""Row 1364: the rich editor's Font colour, in a real browser (Classic only: the Theme's stylesheet is layered, as the page layers it).

Run: python3 dev/run_tests.py test_font_colour_editor_1364
The real RichText on the bare test page (tests/_rich_page.py) with the Classic theme's CSS in <style id="theme">. Widths 1400 and 900; light and
dark. Fictional text only. One test per line of the ticket (select and pick, Automatic, survives save and reload, keyboard, contrast, label).
"""
import json
import sys
import unittest

import _rich_page as rp
from test_server import chrome

sys.path.insert(0, str(rp.TOOLS))
from clark import theme  # noqa: E402

SWATCHES = ["Grey", "Brand", "Red", "Amber", "Green", "Blue"]
TOKEN = {"grey": "--text-muted", "brand": "--brand-blue", "red": "--tone-red-text", "amber": "--tone-amber-text", "green": "--tone-green-text", "blue": "--tone-blue-text"}
WORDS = "<p>Hello colourful world</p>"


def box(sel):
    return f"(function(){{ var e = document.querySelector({json.dumps(sel)}); if (!e) return null; var r = e.getBoundingClientRect(); return [Math.round(r.left * 10) / 10, Math.round(r.top * 10) / 10, Math.round(r.width * 10) / 10, Math.round(r.height * 10) / 10]; }})()"


class Base(unittest.TestCase):
    classic = True

    @classmethod
    def setUpClass(cls):
        cls.h = rp.Harness(chrome).__enter__()
        if cls.classic:
            cls.h.ev(f"(function(){{ var s = document.createElement('style'); s.id = 'theme'; s.textContent = {json.dumps(theme.css('prototype-2.0'))}; document.head.appendChild(s); return true; }})()")

    @classmethod
    def tearDownClass(cls):
        cls.h.__exit__(None, None, None)

    def setUp(self):
        self.h.resize(1400)
        self.h.theme("light")

    def tearDown(self):
        self.h.ev("window.unmount(); true")

    def open_palette(self, where=".rt-bar"):
        self.h.ev(f"document.querySelector('{where} .rt-fc-btn').click(); true")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-fc-pal')"), "the palette opens")

    def pick(self, label, where=".rt-bar"):
        self.open_palette(where)
        self.h.ev("document.querySelector('.rt-fc-pal .rt-fc-auto').click(); true" if label == "Automatic" else f"document.querySelector('.rt-fc-pal [aria-label={json.dumps(label)}]').click(); true")
        self.assertTrue(self.h.until("!document.querySelector('.rt-fc-pal')"), "choosing closes the palette")
        self.assertTrue(self.h.until("document.activeElement && document.activeElement.classList.contains('ProseMirror')"), "the focus goes back to the text")
        self.h.ev("window.settled = false; requestAnimationFrame(function(){ requestAnimationFrame(function(){ window.settled = true; }); }); true")
        self.assertTrue(self.h.until("window.settled === true"))

    def written(self):
        return self.h.ev("document.querySelector('.rt-host .ProseMirror').innerHTML")

    def saved(self):
        self.h.key("Enter", self.h.mod, "Enter", 13)
        self.assertTrue(self.h.until("window.saves.length >= 1"))
        return self.h.ev("window.saves[window.saves.length - 1]")

    def press(self, key, vk, text=None):
        for kind in ("keyDown", "keyUp"):
            args = {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": vk, "modifiers": 0}
            if text and kind == "keyDown":
                args["text"] = text
            self.h.cdp.call("Input.dispatchKeyEvent", args, self.h.sid)

    def focus_label(self):
        return self.h.ev("(function(){ var a = document.activeElement; return a ? (a.getAttribute('aria-label') || a.textContent.trim()) : null; })()")


class Entry(Base):
    def test_one_button_after_strikethrough_in_the_toolbar_and_the_bubble_named_font_colour(self):
        self.h.mount(WORDS)
        self.assertEqual(self.h.ev("[...document.querySelectorAll('.rt-bar > button, .rt-bar .rt-fc > button')].map(b => b.getAttribute('aria-label')).slice(0, 8)"),
                         ["Bold", "Italic", "Strikethrough", "Font colour", "Bulleted list", "Numbered list", "Checklist", "Quote"])
        self.assertEqual(self.h.ev("document.querySelectorAll('.rt-bar .rt-fc-btn').length"), 1)
        self.h.select_all()
        self.assertTrue(self.h.until("!!document.querySelector('.rt-bubble')"))
        self.assertEqual(self.h.ev("[...document.querySelectorAll('.rt-bubble > button, .rt-bubble .rt-fc > button')].map(b => b.getAttribute('aria-label') || b.textContent).slice(0, 5)"),
                         ["Bold", "Italic", "Strikethrough", "Font colour", "Link"])

    def test_the_button_is_32_by_32_like_its_neighbours_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(w):
                self.h.resize(w)
                self.h.mount(WORDS)
                self.assertEqual(self.h.ev(box(".rt-bar .rt-fc-btn"))[2:], [32, 32])
                self.assertEqual(self.h.ev(box(".rt-bar [aria-label=Strikethrough]"))[2:], [32, 32])
                self.h.ev("window.unmount(); true")

    def test_the_glyph_is_a_bold_A_with_a_3px_underline_in_the_current_colour(self):
        self.h.mount('<p><span class="rt-c-green">Hello</span> world</p>')
        self.assertEqual(self.h.ev("getComputedStyle(document.querySelector('.rt-bar .rt-fc-g')).fontWeight"), "700")
        self.assertEqual(self.h.ev("document.querySelector('.rt-bar .rt-fc-g').textContent"), "A")
        self.assertEqual(self.h.ev(box(".rt-bar .rt-fc-bar"))[3], 3)
        self.h.ev("(function(){ var e = document.querySelector('.rt-host .ProseMirror span'); var r = document.createRange(); r.selectNodeContents(e.firstChild); var s = getSelection(); s.removeAllRanges(); s.addRange(r); return true; })()")
        self.assertTrue(self.h.until("document.querySelector('.rt-bar .rt-fc-bar').className.indexOf('rt-c-green') >= 0"), "the bar takes the colour of the selection")
        self.assertEqual(self.h.ev("getComputedStyle(document.querySelector('.rt-bar .rt-fc-bar')).backgroundColor"),
                         self.h.ev("getComputedStyle(document.documentElement).getPropertyValue('--x') || (function(){ var e = document.createElement('i'); e.style.color = 'var(--tone-green-text)'; document.body.appendChild(e); var c = getComputedStyle(e).color; e.remove(); return c; })()"))
        self.h.ev("window.unmount(); true")
        self.h.mount(WORDS)
        self.assertEqual(self.h.ev("getComputedStyle(document.querySelector('.rt-bar .rt-fc-bar')).backgroundColor"),
                         self.h.ev("(function(){ var e = document.createElement('i'); e.style.color = 'var(--text)'; document.body.appendChild(e); var c = getComputedStyle(e).color; e.remove(); return c; })()"),
                         "Automatic: the text colour")

    def test_the_screen_reader_name_is_font_colour_and_it_is_a_menu_button(self):
        self.h.mount(WORDS)
        for k, v in (("aria-label", "Font colour"), ("title", "Font colour"), ("aria-haspopup", "menu"), ("aria-expanded", "false"), ("type", "button")):
            self.assertEqual(self.h.ev(f"document.querySelector('.rt-bar .rt-fc-btn').getAttribute('{k}')"), v)
        self.open_palette()
        self.assertEqual(self.h.ev("document.querySelector('.rt-bar .rt-fc-btn').getAttribute('aria-expanded')"), "true")
        self.assertEqual(self.h.ev("document.querySelector('.rt-fc-pal').getAttribute('aria-label')"), "Font colour")


class Palette(Base):
    def test_automatic_first_then_six_named_swatches(self):
        self.h.mount(WORDS)
        self.open_palette()
        self.assertEqual(self.h.ev("[...document.querySelectorAll('.rt-fc-pal [role=menuitemradio]')].map(b => b.getAttribute('aria-label') || b.textContent.trim().replace('✓', ''))"),
                         ["Automatic"] + SWATCHES)
        self.assertEqual(self.h.ev("[...document.querySelectorAll('.rt-fc-sw')].map(b => b.title)"), SWATCHES)

    def test_the_measures_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(w):
                self.h.resize(w)
                self.h.mount(WORDS)
                self.open_palette()
                pal, btn = self.h.ev(box(".rt-fc-pal")), self.h.ev(box(".rt-bar .rt-fc-btn"))
                self.assertEqual(pal[2], 208)
                self.assertGreaterEqual(pal[1], btn[1] + btn[3], "under the button")
                self.assertEqual(self.h.ev("(function(){ var s = getComputedStyle(document.querySelector('.rt-fc-pal')); return [s.paddingLeft, s.borderTopWidth, s.borderTopLeftRadius, s.boxShadow]; })()"),
                                 ["8px", "1px", "8px", "rgba(14, 36, 48, 0.12) 0px 6px 18px 0px"])
                self.assertEqual(self.h.ev(box(".rt-fc-auto"))[3], 32)
                sw = [self.h.ev(box(f".rt-fc-sw:nth-child({i})")) for i in range(1, 7)]
                self.assertTrue(all(b[2] == 32 and b[3] == 32 for b in sw), sw)
                self.assertEqual([b[1] for b in sw], [sw[0][1]] * 4 + [sw[0][1] + 38] * 2, "4 to a row, 6 apart")
                self.assertEqual([sw[1][0] - sw[0][0], sw[3][0] - sw[2][0]], [38, 38])
                self.assertEqual(self.h.ev("getComputedStyle(document.querySelector('.rt-fc-sw')).borderRadius + ' ' + getComputedStyle(document.querySelector('.rt-fc-sw')).borderTopWidth"), "6px 1px")
                self.h.ev("window.unmount(); true")

    def test_each_swatch_draws_an_A_in_its_token_colour_on_the_surface(self):
        self.h.mount(WORDS)
        self.open_palette()
        for name, token in TOKEN.items():
            with self.subTest(name):
                got = self.h.ev(f"(function(){{ var a = document.querySelector('.rt-fc-sw .rt-c-{name}'); var e = document.createElement('i'); e.style.color = 'var({token})'; document.body.appendChild(e); var want = getComputedStyle(e).color; e.remove(); return [a.textContent, getComputedStyle(a).color === want]; }})()")
                self.assertEqual(got, ["A", True])

    def test_the_chosen_swatch_has_a_2px_brand_outline_offset_1_and_automatic_a_tick(self):
        self.h.mount('<p><span class="rt-c-red">Hello</span></p>')
        self.h.ev("(function(){ var e = document.querySelector('.rt-host .ProseMirror span'); var r = document.createRange(); r.selectNodeContents(e.firstChild); var s = getSelection(); s.removeAllRanges(); s.addRange(r); return true; })()")
        self.assertTrue(self.h.until("document.querySelector('.rt-bar .rt-fc-bar').className.indexOf('rt-c-red') >= 0"))
        self.open_palette()
        self.assertEqual(self.h.ev("document.querySelector('.rt-fc-sw.on').getAttribute('aria-label')"), "Red")
        self.assertEqual(self.h.ev("(function(){ var s = getComputedStyle(document.querySelector('.rt-fc-sw.on')); return [s.outlineWidth, s.outlineOffset, s.outlineStyle]; })()"), ["2px", "1px", "solid"])
        self.assertEqual(self.h.ev("document.querySelector('.rt-fc-auto .rt-fc-tick').textContent"), "")
        self.assertEqual(self.h.ev("document.querySelectorAll('.rt-fc-sw.on').length"), 1)
        self.h.ev("document.querySelector('.rt-fc-auto').click(); true")
        self.assertTrue(self.h.until("!document.querySelector('.rt-fc-pal')"))
        self.open_palette()
        self.assertEqual(self.h.ev("document.querySelector('.rt-fc-auto .rt-fc-tick').textContent"), "✓")
        self.assertEqual(self.h.ev("document.querySelector('.rt-fc-auto').getAttribute('aria-checked')"), "true")


class Apply(Base):
    def test_select_text_pick_a_colour_and_the_text_changes_and_automatic_returns_it(self):
        self.h.mount(WORDS)
        self.h.select_all()
        self.pick("Red")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-host .ProseMirror .rt-c-red')"))
        self.assertEqual(self.h.ev("(function(){ var a = document.querySelector('.rt-host .ProseMirror .rt-c-red'); var e = document.createElement('i'); e.style.color = 'var(--tone-red-text)'; document.body.appendChild(e); var w = getComputedStyle(e).color; e.remove(); return getComputedStyle(a).color === w && w !== getComputedStyle(document.querySelector('.rt-host .ProseMirror')).color; })()"), True)
        self.assertEqual(self.h.ev("document.querySelector('.rt-host .ProseMirror .rt-c-red').textContent"), "Hello colourful world")
        self.h.select_all()
        self.pick("Automatic")
        self.assertTrue(self.h.until("!document.querySelector('.rt-host .ProseMirror [class*=rt-c-]')"))
        self.assertEqual(self.h.ev("(function(){ var a = document.querySelector('.rt-host .ProseMirror p'); var e = document.createElement('i'); e.style.color = 'var(--text)'; document.body.appendChild(e); var w = getComputedStyle(e).color; e.remove(); return getComputedStyle(a).color === w; })()"), True)

    def test_it_applies_to_the_selection_only_and_from_the_bubble_too(self):
        self.h.mount("<p>Alpha</p>")
        self.h.select_all()
        self.assertTrue(self.h.until("!!document.querySelector('.rt-bubble')"))
        self.pick("Blue", ".rt-bubble")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-host .ProseMirror .rt-c-blue')"))
        self.assertEqual(self.saved(), '<p><span class="rt-c-blue">Alpha</span></p>')

    def test_what_is_saved_is_a_class_never_a_hex_or_style(self):
        self.h.mount(WORDS)
        self.h.select_all()
        for name in SWATCHES:
            self.pick(name)
            html = self.h.ev("window.CE.clarkEditor && document.querySelector('.rt-host .ProseMirror').cxed.written()")
            self.assertEqual(html, f'<p><span class="rt-c-{name.lower()}">Hello colourful world</span></p>')
            self.assertNotIn("#", html)
            self.assertNotIn("style", html)
            self.assertEqual(self.h.ev(f"CE.cleanHtml({json.dumps(html)})"), html, "the page's cleaner keeps exactly this")
            self.h.select_all()

    def test_colour_and_bold_together_and_it_survives_save_and_reload(self):
        self.h.mount("<p>Alpha beta</p>")
        self.h.select_all()
        self.pick("Green")
        self.h.ev("document.querySelector('.rt-bar [aria-label=Bold]').click(); true")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-host .ProseMirror strong')"))
        html = self.saved()
        self.assertEqual(html, '<p><span class="rt-c-green"><strong>Alpha beta</strong></span></p>')
        self.h.ev("window.unmount(); true")
        self.h.mount(html)                                               # reload: opened again from what was saved
        self.assertEqual(self.h.ev("document.querySelector('.rt-host .ProseMirror strong .rt-c-green, .rt-host .ProseMirror .rt-c-green strong').textContent"), "Alpha beta")
        self.assertEqual(self.h.ev("document.querySelector('.rt-cx, .rt-host .ProseMirror').cxed.html()"), html, "untouched, it is byte for byte")

    def test_typing_at_the_end_of_coloured_text_goes_on_in_that_colour_and_the_other_colours_stay(self):
        self.h.mount('<p><span class="rt-c-red">Hot</span> and <span class="rt-c-blue">cold</span></p>')
        self.h.key("End", self.h.mod, "End", 35)
        self.h.type("!")
        self.assertTrue(self.h.until("document.querySelector('.rt-host .ProseMirror').textContent.endsWith('!')"))
        html = self.saved()
        self.assertEqual(html, '<p><span class="rt-c-red">Hot</span> and <span class="rt-c-blue">cold!</span></p>')


class Keyboard(Base):
    def test_the_button_is_reached_by_tab_and_down_opens_with_the_focus_on_automatic(self):
        self.h.mount(WORDS)
        self.assertGreaterEqual(self.h.ev("document.querySelector('.rt-bar .rt-fc-btn').tabIndex"), 0)
        self.h.ev("document.querySelector('.rt-bar .rt-fc-btn').focus(); true")
        self.press("ArrowDown", 40)
        self.assertTrue(self.h.until("!!document.querySelector('.rt-fc-pal')"))
        self.assertTrue(self.h.until("document.activeElement && document.activeElement.classList.contains('rt-fc-auto')"))

    def test_enter_opens_and_arrows_move_over_automatic_and_the_grid_and_enter_chooses(self):
        self.h.mount(WORDS)
        self.h.select_all()
        self.h.ev("document.querySelector('.rt-bar .rt-fc-btn').focus(); true")
        self.press("Enter", 13, "\r")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-fc-pal')"))
        self.assertTrue(self.h.until("document.activeElement.classList.contains('rt-fc-auto')"))
        path = [("ArrowDown", 40, "Grey"), ("ArrowRight", 39, "Brand"), ("ArrowDown", 40, "Blue"), ("ArrowLeft", 37, "Green"), ("ArrowUp", 38, "Grey"),
                ("ArrowUp", 38, "Automatic"), ("ArrowDown", 40, "Grey"), ("ArrowLeft", 37, "Automatic"), ("ArrowDown", 40, "Grey"), ("ArrowRight", 39, "Brand"),
                ("ArrowDown", 40, "Blue")]
        for key, vk, want in path:
            self.press(key, vk)
            self.assertTrue(self.h.until(f"document.activeElement.getAttribute('aria-label') === {json.dumps(want)} || document.activeElement.textContent.indexOf({json.dumps(want)}) >= 0"), f"{key} -> {want}: now {self.focus_label()}")
        self.press("Enter", 13, "\r")
        self.assertTrue(self.h.until("!document.querySelector('.rt-fc-pal')"))
        self.assertTrue(self.h.until("!!document.querySelector('.rt-host .ProseMirror .rt-c-blue')"))

    def test_escape_closes_the_palette_and_the_focus_returns_to_the_button_without_closing_the_field(self):
        self.h.mount(WORDS)
        self.h.ev("document.querySelector('.rt-bar .rt-fc-btn').focus(); true")
        self.press("ArrowDown", 40)
        self.assertTrue(self.h.until("document.activeElement.classList.contains('rt-fc-auto')"))
        self.press("ArrowDown", 40)
        self.press("Escape", 27)
        self.assertTrue(self.h.until("!document.querySelector('.rt-fc-pal')"))
        self.assertTrue(self.h.until("document.activeElement.classList.contains('rt-fc-btn')"), "focus back on the button")
        self.assertEqual(self.h.ev("window.ended"), 0, "Esc closed the palette, not the field")
        self.assertFalse(self.h.ev("!!document.querySelector('.rt-host .ProseMirror [class*=rt-c-]')"), "nothing was chosen")

    def test_the_first_open_with_a_chosen_colour_puts_the_focus_on_it(self):
        self.h.mount('<p><span class="rt-c-amber">Hello</span></p>')
        self.h.ev("(function(){ var e = document.querySelector('.rt-host .ProseMirror span'); var r = document.createRange(); r.selectNodeContents(e.firstChild); var s = getSelection(); s.removeAllRanges(); s.addRange(r); return true; })()")
        self.assertTrue(self.h.until("document.querySelector('.rt-bar .rt-fc-bar').className.indexOf('rt-c-amber') >= 0"))
        self.open_palette()
        self.assertTrue(self.h.until("document.activeElement.getAttribute('aria-label') === 'Amber'"))


class Contrast(Base):
    LUM = ("(function(){ function lum(c){ var m = c.match(/[\\d.]+/g).map(Number); var f = m.slice(0,3).map(function(v){ v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126*f[0] + 0.7152*f[1] + 0.0722*f[2]; }"
           " return [...document.querySelectorAll('.rt-fc-sw')].map(function(b){ var a = b.firstChild, l1 = lum(getComputedStyle(a).color), l2 = lum(getComputedStyle(b).backgroundColor); var hi = Math.max(l1, l2), lo = Math.min(l1, l2); return [b.title, Math.round((hi + 0.05) / (lo + 0.05) * 100) / 100]; }); })()")

    def test_every_swatch_keeps_4_5_to_1_on_the_surface_light_and_dark_at_1400_and_900(self):
        for w in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode):
                    self.h.resize(w)
                    self.h.theme(mode)
                    self.h.mount(WORDS)
                    self.open_palette()
                    got = self.h.ev(self.LUM)
                    self.assertEqual([n for n, _ in got], SWATCHES)
                    for name, ratio in got:
                        self.assertGreaterEqual(ratio, 4.5, f"{name} {mode}: {ratio}")
                    self.h.ev("window.unmount(); true")


class Cards(Base):
    classic = False

    def test_without_the_theme_there_is_no_font_colour_button_anywhere(self):
        self.h.mount(WORDS)
        self.h.select_all()
        self.assertTrue(self.h.until("!!document.querySelector('.rt-bubble')"))
        self.assertEqual(self.h.ev("document.querySelectorAll('.rt-fc, .rt-fc-btn, [aria-label=\"Font colour\"]').length"), 0)
        self.assertEqual(self.h.ev("[...document.querySelectorAll('.rt-bar button')].slice(0, 5).map(b => b.getAttribute('aria-label'))"),
                         ["Text style: Text", "Bold", "Italic", "Strikethrough", "Bulleted list"])


if __name__ == "__main__":
    unittest.main()
