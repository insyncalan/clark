"""#440 (S2): the Settings chips' bar that stays under the top bar, with the chip of the card you are reading marked, in a real
browser at 1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_settings_bar

What is asserted: the bar (the list at the left above 900 px, the row of chips at 900 px and narrower; issue 697) stays under the top bar as you scroll, on the page's own ground, and a card a chip goes to is never hidden by
it; one chip is marked (aria-current="location") and it follows the card you are reading, both as you scroll and when a chip is chosen
(the last chip, near the foot of the page, too); the marked chip's words are 4.5:1 on its fill and its fill 3:1 on the bar; the menu's link still puts the cursor in the name
box, clear of the bar. Chrome is required: these tests fail, never skip, without it.
"""
import time
import unittest

from test_publish_dialog import Base
from test_server import chrome, wait
from test_settings_head import ratio, rgb

WIDTHS = (1400, 901, 900, 800)
MODES = ("light", "dark")
MARKED = "document.querySelector('.set-nav .set-chip[aria-current]')"


def calm(p, mode="light"):
    """Light or dark, with reduced motion: a chip's scroll is then at once, so what is under the bar can be read straight after a click."""
    p.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": mode},
                                                          {"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)


class SettingsBar(Base):
    def open_settings(self, p, w, mode="light"):
        p.width(w)
        calm(p, mode)
        p.js("location.hash = '#settings&p=PUB'")
        p.until("!!document.querySelector('#personal-h') && !!document.querySelector('#ask-settings-h') && !!document.querySelector('.set-nav .set-chip[aria-current]')",
                "Settings, its cards and a marked chip drew")
        self.laid_out(p)

    def laid_out(self, p, seconds=15, frames=6):
        """A card above Personal (Profile) may still grow after the first draw, which moves every card below it: a scroll aimed at a card's top
        read before that lands at the wrong place. Wait until the page height and the tops of three cards are the same on `frames` reads in a row,
        100 ms apart; fail, naming what kept moving, when they do not settle."""
        read = ("[document.documentElement.scrollHeight, ...['personal-h', 'safety-h', 'ask-settings-h'].map(id => Math.round(document.getElementById(id).getBoundingClientRect().top + window.scrollY))].join()")
        seen = []

        def still():
            seen.append(p.js(read))
            time.sleep(0.1)
            return len(seen) >= frames and len(set(seen[-frames:])) == 1
        self.assertTrue(wait(still, seconds), "the layout never settled in %d s (page height, tops of Personal, Backups, Asking, last reads: %s)" % (seconds, seen[-frames:]))

    def marked(self, p):
        return p.js(f"({MARKED} || {{}}).textContent || ''")

    def chip(self, p, name):
        p.js(f"[...document.querySelectorAll('.set-nav .set-chip')].find(b => b.textContent === '{name}').click()")

    def settle(self, p):
        """Wait for the scroll to stop (the same position on two reads): a box the browser scrolls into view may still move smoothly."""
        p.settled("the scroll finished")

    def clear_of_bar(self, p, sel):
        """Clear of the bar: below it when the bar is a row of chips (900 px and narrower), at its right when it is the list at the left."""
        return p.js(f"(() => {{ const h = document.querySelector('{sel}').getBoundingClientRect(), b = document.querySelector('.set-bar').getBoundingClientRect(); "
                    f"return window.innerWidth > 900 ? h.left >= b.right : h.top >= b.bottom; }})()")

    def test_C_the_bar_stays_under_the_top_bar_on_the_page_ground_and_never_hides_a_card(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-bar')).position"), "sticky")
                    self.assertEqual(self.marked(p), "Profile", "at the top of the page the first chip is marked")
                    p.js("window.scrollTo(0, 900)")
                    self.settle(p)
                    self.assertLess(abs(p.js("document.querySelector('.set-bar').getBoundingClientRect().top - document.querySelector('.top').getBoundingClientRect().bottom")), 2,
                                    "the bar is under the top bar")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-bar')).backgroundColor"), p.js("getComputedStyle(document.body).backgroundColor"),
                                     "the bar is on the page's own ground")
                    for name, head_id in (("Backups", "safety-h"), ("Personal", "personal-h"), ("Logs and diagnostics", "diagnostics-h"), ("Publishing", "client-folder-h")):
                        self.chip(p, name)
                        p.until(f"document.activeElement && document.activeElement.id === '{head_id}'", f"focus is on {head_id}")
                        self.settle(p)
                        self.assertTrue(self.clear_of_bar(p, f"#{head_id}"), f"{name}: its heading is clear of the bar")
                        self.assertEqual(self.marked(p), name)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_C_the_marked_chip_follows_the_card_you_are_reading_as_you_scroll(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                for name, head_id in (("Personal", "personal-h"), ("Backups", "safety-h"), ("Logs and diagnostics", "diagnostics-h")):
                    p.js(f"(() => {{ const c = document.getElementById('{head_id}').closest('section'), b = document.querySelector('.set-bar'), room = window.innerWidth > 900 ? 0 : b.offsetHeight; "
                         f"window.scrollTo(0, window.scrollY + c.getBoundingClientRect().top - room - document.querySelector('.top').offsetHeight - 8); }})()")
                    p.until(f"({MARKED} || {{}}).textContent === '{name}'", f"{name} is marked once its card is under the bar")
                    self.assertEqual(p.js("document.querySelectorAll('.set-nav .set-chip[aria-current]').length"), 1, "one chip is marked")
                    self.assertEqual(p.js(f"{MARKED}.getAttribute('aria-current')"), "location")
                p.js("window.scrollTo(0, 0)")
                p.until(f"({MARKED} || {{}}).textContent === 'Profile'", "back at the top, the first chip is marked")
                self.chip(p, "Asking")
                p.until("document.activeElement && document.activeElement.id === 'ask-settings-h'", "focus is on the Asking heading")
                self.settle(p)
                self.assertEqual(self.marked(p), "Asking", "the last chip, near the foot of the page, stays marked")
                self.assertTrue(self.clear_of_bar(p, "#ask-settings-h"))

    def test_C_the_marked_chip_can_be_read_in_light_and_dark(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    size, color, fill = p.js(f"(() => {{ const s = getComputedStyle({MARKED}); return [parseFloat(s.fontSize), s.color, s.backgroundColor]; }})()")
                    ground = p.js("getComputedStyle(document.querySelector('.set-bar')).backgroundColor")
                    self.assertGreaterEqual(size, 13)
                    self.assertGreaterEqual(ratio(rgb(color), rgb(fill)), 4.5, f"{mode}: the marked chip's words on its fill")
                    self.assertGreaterEqual(ratio(rgb(fill), rgb(ground)), 3, f"{mode}: the marked chip's fill on the bar")
                    self.assertNotEqual(fill, p.js("getComputedStyle(document.querySelector('.set-nav .set-chip:not([aria-current])')).backgroundColor"),
                                        "the marked chip does not look like the others")

    def test_C_the_menu_link_puts_the_cursor_in_the_name_box_clear_of_the_bar(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                calm(p)
                p.until("(() => { if (document.querySelector('#profile-menu')) return true; "
                        "if (Date.now() - (window.__menuTried || 0) > 1000) { window.__menuTried = Date.now(); document.querySelector('#profile-btn').click(); } "
                        "return !!document.querySelector('#profile-menu'); })()", "the menu opened")
                p.js("document.querySelector('#profile-menu .who-link').click()")
                p.until("document.activeElement && document.activeElement.id === 'about-name'", "the name box has the cursor")
                self.settle(p)
                self.assertTrue(self.clear_of_bar(p, "#about-name"), "the box is clear of the bar")
                self.assertEqual(self.marked(p), "Profile", "the chip of the card holding the box is marked")


if __name__ == "__main__":
    unittest.main()
