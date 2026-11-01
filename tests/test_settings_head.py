"""The Settings head: the title, a line of help and one chip for each card on the page, in a real browser at 1400 and 900 px, light and
dark. Run: python3 dev/run_tests.py test_settings_head

What is asserted: the title and the help line; a chip for each card that is on the page (Publishing, Personal, Backups) and none
for a card that is not; a click scrolls the card into view and moves focus to its heading; the keyboard does the same (Tab to a chip,
Enter); the chips wrap and the page has no sideways scroll; each chip is at least 24 px high and wide; the chip text is at least 13 px
and 4.5:1 on its ground; the focus ring is 2 px. Chrome is required: these tests fail, never skip, without it.
"""
import re
import unittest

from test_appearance import scheme
from test_publish_dialog import Base
from test_server import chrome

WIDTHS = (1400, 900)
MODES = ("light", "dark")
HELP = "Where reports are published, how clark looks for you, and your backups. More settings are still to come."
CARDS = [("Publishing", "client-folder-h"), ("Personal", "personal-h"), ("Backups", "safety-h")]


def ratio(a, b):
    def lum(rgb):
        out = []
        for c in rgb:
            c /= 255
            out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def rgb(text):
    return [int(x) for x in re.findall(r"\d+", text)[:3]]


class Head(Base):
    def open_settings(self, p, w, mode="light"):
        p.width(w)
        scheme(p, mode)
        p.js("location.hash = '#settings&p=PUB'")
        p.until("!!document.querySelector('.set-nav .set-chip') && !!document.querySelector('#personal-h') && !!document.querySelector('#safety-h')",
                "Settings and its chips drew")

    def chips(self, p):
        return p.js("[...document.querySelectorAll('.set-nav .set-chip')].map(b => b.textContent)")

    def at_top(self, p, head_id):
        """The card is in view and its heading has the focus."""
        p.until(f"document.activeElement && document.activeElement.id === '{head_id}'", f"focus is on {head_id}")
        p.until(f"(function(){{var r = document.getElementById('{head_id}').getBoundingClientRect(); return r.top >= 56 && r.bottom <= window.innerHeight;}})()",
                "the heading is in view, clear of the top bar")

    def test_C_the_title_the_help_line_and_a_chip_for_each_card_that_exists(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertEqual(p.js("document.querySelector('.set-head h1').textContent"), "Settings")
                    self.assertEqual(p.js("document.querySelector('.set-head p').textContent"), HELP)
                    self.assertEqual(self.chips(p), [name for name, _ in CARDS])
                    for name, head_id in CARDS:
                        self.assertEqual(p.js(f"document.getElementById('{head_id}').textContent"), name, "a chip says what its card's heading says")
                        self.assertEqual(p.js(f"document.getElementById('{head_id}').getAttribute('tabindex')"), "-1")
                    for gone in ("Profile", "AI", "Projects", "People", "Asking", "Published reports", "Data", "Version", "Diagnostics"):
                        self.assertNotIn(gone, self.chips(p), f"no chip for {gone}: there is no such card")
                    self.assertNotIn("Settings are not ready yet.", p.js("document.querySelector('main').innerText"))

    def test_C_a_click_scrolls_to_the_card_and_focuses_its_heading(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                for name, head_id in reversed(CARDS):
                    p.js("window.scrollTo(0, 0)")
                    p.js(f"[...document.querySelectorAll('.set-nav .set-chip')].find(b => b.textContent === '{name}').click()")
                    self.at_top(p, head_id)
                self.assertTrue(p.js("location.hash.indexOf('#settings') === 0"), "the page's own address is kept")

    def test_C_keyboard_tab_to_a_chip_and_enter(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.js("document.querySelector('.set-nav .set-chip').focus()")
            p.key("Tab", code="Tab", vk=9)
            self.assertEqual(p.js("document.activeElement.textContent"), "Personal", "Tab moves from chip to chip")
            self.assertEqual(p.js("document.querySelectorAll('.set-nav .set-chip').length"), len(CARDS))
            p.js("window.scrollTo(0, 0)")
            p.key("Enter", code="Enter", vk=13)
            self.at_top(p, "personal-h")
            self.assertEqual(p.js("getComputedStyle(document.activeElement).outlineWidth"), "2px", "the heading shows the ring after the keyboard")

    def test_C_the_chips_wrap_with_no_sideways_scroll_and_are_big_enough(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                self.assertTrue(p.js("(function(){var n = document.querySelector('.set-nav'); return n.scrollWidth <= n.clientWidth;})()"), "the row does not scroll")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-nav')).flexWrap"), "wrap")
                for h, wd in p.js("[...document.querySelectorAll('.set-nav .set-chip')].map(b => { const r = b.getBoundingClientRect(); return [r.height, r.width]; })"):
                    self.assertGreaterEqual(h, 24)
                    self.assertGreaterEqual(wd, 24)
                p.width(320)
                p.until("(function(){var n = document.querySelector('.set-nav'); return n.scrollWidth <= n.clientWidth;})()", "the chips still wrap when narrow")

    def test_C_text_size_and_contrast_in_light_and_dark(self):
        for mode in MODES:
            with self.subTest(mode=mode), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, 1400, mode)
                got = p.js("""[...document.querySelectorAll('.set-nav .set-chip')].map(b => { const s = getComputedStyle(b);
                    return [parseFloat(s.fontSize), s.color, s.backgroundColor, s.borderTopColor]; })""")
                for size, color, ground, edge in got:
                    self.assertGreaterEqual(size, 13)
                    self.assertGreaterEqual(ratio(rgb(color), rgb(ground)), 4.5, f"{mode}: the chip text on its ground")
                    self.assertGreaterEqual(ratio(rgb(edge), rgb(ground)), 3, f"{mode}: the chip's edge on its ground")
                p.js("document.querySelector('.set-nav .set-chip').focus()")
                p.key("Tab", code="Tab", vk=9)
                p.key("Tab", code="Tab", vk=9, )
                ring = p.js("(function(){var s = getComputedStyle(document.activeElement); return [s.outlineWidth, s.outlineStyle, s.outlineColor];})()")
                self.assertEqual(ring[:2], ["2px", "solid"])
                brand = p.js("(function(){var d = document.createElement('i'); d.style.color = 'var(--brand-blue)'; document.body.appendChild(d); var c = getComputedStyle(d).color; d.remove(); return c;})()")
                self.assertEqual(ring[2], brand, "the ring is the brand blue")


if __name__ == "__main__":
    unittest.main()
