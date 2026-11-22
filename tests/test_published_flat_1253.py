"""Row 1253: the Published reports page in Classic, in a real browser at 1400 and 900 px, light and dark. No cover band (so the logo that the band draws is not drawn
a second time), no card, the page starts with its own heading, the sections are flat and line-divided, the intro is readable, nothing runs sideways.
Cards (no Theme) keeps its card and cover band. The 900 px cases are paused by PAUSED_900 in test_server.py.

Run: python3 dev/run_tests.py test_published_flat_1253        (needs Chrome)
"""
import unittest

from _paths import SRC

from test_past_reports_card import InBrowser, LIST, OK, lit

RULES2 = (SRC / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")
CONTRAST = """(() => { const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number).map(n => c.startsWith("color(") ? n * 255 : n);
  const lum = (c) => { const [r, g, b] = rgb(c).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
  let bg = document.querySelector('#pubs-page'); while (bg && getComputedStyle(bg).backgroundColor === 'rgba(0, 0, 0, 0)') bg = bg.parentElement;
  const back = bg ? getComputedStyle(bg).backgroundColor : 'rgb(255, 255, 255)';      // no painted ancestor: the canvas, white
  const a = lum(getComputedStyle(document.querySelector('#pubs-page .pubs-intro')).color), b = lum(back);
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); })()"""


class ClassicPage(InBrowser):
    def classic(self):
        # the served page's script-src/style-src refuses a style element added by script: the Theme's rules are adopted as a sheet, and an empty #theme element marks Classic (as classicTheme() reads it)
        self.js(f"(() => {{ const s = document.createElement('style'); s.id = 'theme'; document.head.appendChild(s); const c = new CSSStyleSheet(); c.replaceSync({lit(RULES2)}); document.adoptedStyleSheets = [c]; }})()")

    def test_no_cover_band_no_card_one_heading_and_the_intro_under_it(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.load(width=width, theme=theme)
                    self.classic()
                    self.replies(list=OK(LIST), tab=True)
                    self.mount()
                    self.assertFalse(self.present("#pubs-page .cover"), "no cover band, so no second logo")
                    self.assertFalse(self.present("#pubs-page .pp-frame"), "no card")
                    self.assertEqual(self.val("document.querySelectorAll('#pubs-page h1').length"), 1)
                    self.assertEqual(self.text("#pubs-page h1"), "Published reports")
                    self.assertEqual(self.text("#pubs-page .pubs-intro"), self.val("T.logic.INTRO"))
                    self.assertEqual(self.val("document.querySelector('#pubs-page').firstElementChild.tagName"), "H1", "the page starts directly with its heading")
                    self.assertEqual(self.val("getComputedStyle(document.querySelector('#pubs-page'), '::before').content"), "none")

    def test_the_list_page_has_no_frame_no_logo_no_as_at_button_and_no_date_of_its_own(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.load(width=width)
                self.classic()
                self.replies(list=OK(LIST), tab=True)
                self.mount()
                self.assertEqual(self.val("document.querySelectorAll('#pubs-page .frame, #pubs-page .cover, #pubs-page .logo, #pubs-page header').length"), 0, "no frame, no cover band, no second logo, no second bar")
                self.assertEqual(self.val("document.querySelectorAll('button.asat, input[type=date]').length"), 0, "no As at date button or date box")
                self.assertEqual(self.val("document.querySelectorAll('header.top').length"), 0, "the page itself draws no bar: the one slim bar is the shell's")

    def test_sections_are_flat_and_the_intro_is_readable(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.load(width=width, theme=theme)
                    self.classic()
                    self.replies(list=OK(LIST), tab=True)
                    self.mount()
                    got = self.val("(() => { const c = getComputedStyle(document.querySelector('#pubs-latest')); return [c.borderTopWidth, c.borderLeftWidth, c.borderRadius, c.borderBottomWidth]; })()")
                    self.assertEqual(got, ["0px", "0px", "0px", "1px"], "a flat section with one line under it")
                    self.assertGreaterEqual(self.val(CONTRAST), 4.5, "the intro is readable on the page")
                    self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")

    def test_cards_keeps_the_cover_band_and_the_card(self):
        self.load()
        self.replies(list=OK(LIST), tab=True)
        self.mount()
        self.assertTrue(self.present("#pubs-page .cover"))
        self.assertTrue(self.present("#pubs-page .pp-frame"))


if __name__ == "__main__":
    unittest.main()
