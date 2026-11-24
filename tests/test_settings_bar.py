"""#440 (S2): the Settings chips' bar that stays under the top bar, with the item of the open page marked, in a real
browser at 1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_settings_bar

What is asserted: the bar (the list at the left at 900 px and wider, the row of chips below 900 px is not tested: only 1400 and 900 px are; issues 697 and 842) stays under the top bar as you scroll, on the page's own ground, and a card a chip goes to is never hidden by
it; one chip is marked (aria-current="location") and it follows the card you are reading, both as you scroll and when a chip is chosen
(the last chip, near the foot of the page, too); the marked chip's words are 4.5:1 on its fill and its fill 3:1 on the bar; the menu's link still puts the cursor in the name
box, clear of the bar. Chrome is required: these tests fail, never skip, without it.
"""
import time
import unittest

from test_publish_dialog import Base
from test_server import chrome, wait
from test_settings_head import FIRST, PAGES, address, ratio, rgb

WIDTHS = (1400, 900)
MODES = ("light", "dark")
MARKED = "document.querySelector('.set-nav .set-chip[aria-current]')"


def calm(p, mode="light"):
    """Light or dark, with reduced motion: a chip's scroll is then at once, so what is under the bar can be read straight after a click."""
    p.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": mode},
                                                          {"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)


class SettingsBar(Base):
    def open_settings(self, p, w, mode="light", page=FIRST):
        p.width(w)
        calm(p, mode)
        p.js(f"location.hash = '{address(page)}'")
        heads = " && ".join(f"!!document.getElementById('{head}')" for _, head in dict((s, c) for s, _, c in PAGES)[page])
        p.until(f"{heads} && !!document.querySelector('.set-nav .set-chip[aria-current]')", "Settings, the page's cards and a marked item drew")
        self.laid_out(p, heads=[head for _, head in dict((s, c) for s, _, c in PAGES)[page]])

    def laid_out(self, p, seconds=15, frames=6, heads=("projects-h",)):
        """A card above Personal (Profile) may still grow after the first draw, which moves every card below it: a scroll aimed at a card's top
        read before that lands at the wrong place. Wait until the page height and the tops of three cards are the same on `frames` reads in a row,
        100 ms apart; fail, naming what kept moving, when they do not settle."""
        read = ("[document.documentElement.scrollHeight, ...%s.map(id => Math.round(document.getElementById(id).getBoundingClientRect().top + window.scrollY))].join()") % list(heads)
        seen = []

        def still():
            seen.append(p.js(read))
            time.sleep(0.1)
            return len(seen) >= frames and len(set(seen[-frames:])) == 1
        self.assertTrue(wait(still, seconds), "the layout never settled in %d s (page height, tops of the page's cards, last reads: %s)" % (seconds, seen[-frames:]))

    def marked(self, p):
        return p.js(f"({MARKED} || {{}}).textContent || ''")

    def chip(self, p, name):
        p.js(f"[...document.querySelectorAll('.set-nav .set-chip')].find(b => b.textContent === '{name}').click()")

    def settle(self, p):
        """Wait for the scroll to stop (the same position on two reads): a box the browser scrolls into view may still move smoothly."""
        p.settled("the scroll finished")

    def clear_of_bar(self, p, sel):
        """Clear of the bar: at its right, the list at the left (the only shape at 1400 and 900 px); the row-of-chips branch is never reached."""
        return p.js(f"(() => {{ const h = document.querySelector('{sel}').getBoundingClientRect(), b = document.querySelector('.set-bar').getBoundingClientRect(); "
                    f"return window.innerWidth >= 900 ? h.left >= b.right : h.top >= b.bottom; }})()")

    def test_C_the_bar_stays_under_the_top_bar_on_the_page_ground_and_never_hides_a_card(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode, page="claude")      # a page with room to scroll (row 1485 took a card off Version and updates, which left it too short for the 10 px past the bar)
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-bar')).position"), "sticky")
                    self.assertEqual(self.marked(p), "Claude and AI", "the open page's item is marked")
                    # a page is short, and the list is as tall as the window: it is under the top bar only for the few pixels the page can still be scrolled after the list reaches the top bar, so scroll 10 px past that
                    p.js("window.scrollTo(0, window.scrollY + document.querySelector('.set-bar').getBoundingClientRect().top - document.querySelector('.top').getBoundingClientRect().bottom + 10)")
                    self.settle(p)
                    self.assertLess(abs(p.js("document.querySelector('.set-bar').getBoundingClientRect().top - document.querySelector('.top').getBoundingClientRect().bottom")), 2,
                                    "the bar is under the top bar: " + p.js("'scrollY=' + scrollY + ' docH=' + document.documentElement.scrollHeight + ' bar top=' + document.querySelector('.set-bar').getBoundingClientRect().top + ' top bar bottom=' + document.querySelector('.top').getBoundingClientRect().bottom + ' --topbar=' + getComputedStyle(document.documentElement).getPropertyValue('--topbar')"))
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-bar')).backgroundColor"), p.js("getComputedStyle(document.body).backgroundColor"),
                                     "the bar is on the page's own ground")
                    for name, head_id in (("Backups", "safety-h"), ("Appearance", "personal-h"), ("Logs and diagnostics", "diagnostics-h"), ("Folder", "client-folder-h")):
                        self.chip(p, name)
                        p.until(f"!!document.getElementById('{head_id}') && ({MARKED} || {{}}).textContent === '{name}'", f"{name} opened its page")
                        self.settle(p)
                        self.assertTrue(self.clear_of_bar(p, f"#{head_id}"), f"{name}: its heading is clear of the bar")
                        self.assertEqual(self.marked(p), name)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_C_the_marked_item_is_the_open_page_and_only_one(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w, page="logs")
                self.assertEqual(self.marked(p), "Logs and diagnostics", "a page opened by its address is the marked one")
                for slug, name, cards in PAGES:
                    self.chip(p, name)
                    p.until(f"({MARKED} || {{}}).textContent === '{name}' && !!document.getElementById('{cards[0][1]}')", f"{name} is marked once its page is open")
                    self.assertEqual(p.js("document.querySelectorAll('.set-nav .set-chip[aria-current]').length"), 1, "one item is marked")
                    self.assertEqual(p.js(f"{MARKED}.getAttribute('aria-current')"), "page")
                    self.assertEqual(p.js("document.querySelector('.set-cards').getAttribute('data-page')"), slug, "only this page's cards are drawn")

    def test_row_1041_scrolled_to_the_very_foot_of_the_longest_page_the_marked_item_is_still_that_page(self):
        """Scrolled by hand (no item chosen) to the very bottom of Version and updates, the page with the most cards: with one page at a time the
        marked item follows the open page, not the card under the bar, so it stays Version and updates. Mutation tried: mark the first item at the
        foot: the marked item is then Projects."""
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode, page="version")
                    self.assertEqual(self.marked(p), "Version and updates")
                    self.assertIn("Version and updates", p.js("[...document.querySelectorAll('.set-nav .set-chip')].slice(-3).map(b => b.textContent)"), "Version and updates is among the last three pages")
                    p.js("window.scrollTo(0, document.documentElement.scrollHeight)")
                    self.settle(p)
                    self.assertTrue(p.js("window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2"), "the page is at its very foot")
                    self.assertEqual(self.marked(p), "Version and updates", "the foot of the page keeps its own item marked")
                    self.assertEqual(p.js("document.querySelectorAll('.set-nav .set-chip[aria-current]').length"), 1, "one item is marked")

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
                    marker = p.js(f"getComputedStyle({MARKED}, '::before').backgroundColor")      # item 1200: the fill is a soft tint; the violet marker carries the 3:1
                    self.assertGreaterEqual(ratio(rgb(marker), rgb(ground)), 3, f"{mode}: the marked chip's marker on the bar")
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
                # row 1024: the link opens the Profile page, which holds the name box, and that page's item is the marked one
                self.assertEqual(self.marked(p), "Profile", "the item of the page that holds the name box is marked")


if __name__ == "__main__":
    unittest.main()
