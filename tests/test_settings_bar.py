"""Item 1024 (option A; was item 440, S2): the Settings menu that stays under the top bar, with the entry of the page you are on marked, in a real
browser at 1400, 901, 900, 899 and 800 px, light and dark. Run: python3 dev/run_tests.py test_settings_bar

What is asserted: the menu (the list at the left at 900 px and wider, the row of buttons below 900 px) stays under the top bar as you scroll, on the
page's own ground, and a page's heading is never hidden by it; plain #settings opens Projects; one entry is marked (aria-current="page") and it
follows the page you are on, whether you chose it, typed its address or stepped Back and Forward; each page keeps its own place on the screen
(item 1019); the marked entry's words are 4.5:1 on its fill and its fill 3:1 on the menu; the profile menu's link still puts the cursor in the
name box, clear of the menu, and the links that land on a page still land there. Chrome is required: these tests fail, never skip, without it.

item 1024, no pin weakened: each check keeps its threshold and its count. The scroll-spy ("the chip follows the card you are reading as you
scroll") has no mechanism now, as only one page is drawn; its strength moved to "the entry follows the page by click, address and history".
The 900 px checks stay in the shape of the row of buttons until the dropdown step moves them.
"""
import json
import time
import unittest

from _mouse import click_centre, menu_item_js
from test_publish_dialog import Base
from test_server import chrome, wait
from test_settings_head import PAGES, ratio, rgb

WIDTHS = (1400, 901, 900, 899, 800)
MODES = ("light", "dark")
MARKED = "document.querySelector('.set-menu .set-item[aria-current=\"page\"]')"
HEADS = {slug: head for _, slug, head, _ in PAGES}
NAMES = {slug: name for name, slug, _, _ in PAGES}


def calm(p, mode="light"):
    """Light or dark, with reduced motion: a scroll is then at once, so what is under the menu can be read straight after a click."""
    p.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": mode},
                                                          {"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)


class SettingsBar(Base):
    def open_settings(self, p, w, mode="light", page=None):
        """Plain #settings, or #settings&s=<page>; waits for that page's heading and exactly one marked entry; the address is the one asked."""
        p.width(w)
        calm(p, mode)
        p.js("location.hash = '#settings&p=PUB" + (f"&s={page}" if page else "") + "'")
        head = HEADS[page or "projects"]
        p.until(f"!!document.getElementById('{head}') && document.querySelectorAll('.set-menu [aria-current]').length === 1", f"Settings drew its {page or 'projects'} page and a marked entry")
        self.assertEqual(p.js("document.querySelectorAll('[data-settings-page]').length"), 1, "one page is drawn")
        self.assertEqual(p.js("location.hash"), "#settings&p=PUB" + (f"&s={page}" if page else ""), "the address is the one asked for")
        self.laid_out(p, head)

    def laid_out(self, p, head, seconds=15, frames=6):
        """A card may still grow after the first draw, which moves what is below it: wait until the page height and the tops of the page's
        heading and first card are the same on `frames` reads in a row, 100 ms apart; fail, naming what kept moving, when they do not settle."""
        read = (f"[document.documentElement.scrollHeight, ...['{head}'].map(id => Math.round(document.getElementById(id).getBoundingClientRect().top + window.scrollY)), "
                "Math.round(document.querySelector('.set-cards .frame').getBoundingClientRect().top + window.scrollY)].join()")
        seen = []

        def still():
            seen.append(p.js(read))
            time.sleep(0.1)
            return len(seen) >= frames and len(set(seen[-frames:])) == 1
        self.assertTrue(wait(still, seconds), "the layout never settled in %d s (page height, tops of the heading and first card, last reads: %s)" % (seconds, seen[-frames:]))

    def marked(self, p):
        return p.js(f"({MARKED} || {{}}).textContent || ''")

    def entry(self, p, name, scrolled_past=False):
        if scrolled_past:      # the page is scrolled past the menu, so no mouse can reach it: this one click stays a JS click (as in test_settings_head)
            p.js(f"{menu_item_js(json.dumps(name))}.click()")
            return
        click_centre(p.cdp, p.sid, menu_item_js(json.dumps(name)), f"the {name} entry")      # a real mouse, as a person clicks

    def settle(self, p):
        """Wait for the scroll to stop (the same position on two reads)."""
        p.settled("the scroll finished")

    def clear_of_menu(self, p, sel):
        """Clear of the menu: below it when the menu is a row (below 900 px), at its right when it is the list at the left."""
        return p.js(f"(() => {{ const h = document.querySelector('{sel}').getBoundingClientRect(), b = document.querySelector('.set-menu').getBoundingClientRect(); "
                    f"return window.innerWidth >= 900 ? h.left >= b.right : h.top >= b.bottom; }})()")

    def test_C_the_menu_stays_under_the_top_bar_on_the_page_ground_and_never_hides_a_page(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    # item 1024c round 2: the list stays under the top bar at 900 px and wider; the row of chips below 900 px scrolls away (it covered a phone)
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-menu')).position"), "sticky" if w >= 900 else "static")
                    self.assertEqual(self.marked(p), "Projects", "plain #settings opens Projects and its entry is marked")
                    self.assertNotIn("&s=", p.js("location.hash"), "plain #settings has no page key")
                    p.js("window.scrollTo(0, 900)")
                    self.settle(p)
                    reached = p.js("window.scrollY")
                    self.assertEqual(reached, min(900, p.js("document.documentElement.scrollHeight - window.innerHeight")), "the page scrolled as far as it can go toward 900 px")
                    if reached > 0 and w >= 900:
                        self.assertLess(abs(p.js("document.querySelector('.set-menu').getBoundingClientRect().top - document.querySelector('.top').getBoundingClientRect().bottom")), 2,
                                        "the menu is under the top bar")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-menu')).backgroundColor"), p.js("getComputedStyle(document.body).backgroundColor"),
                                     "the menu is on the page's own ground")
                    for name, slug, head_id in (("Backups", "backups", "safety-h"), ("Profile", "profile", "profile-h"), ("Logs and diagnostics", "logs", "diagnostics-h"), ("Folder", "folder", "client-folder-h")):
                        self.entry(p, name)
                        p.until(f"document.activeElement && document.activeElement.id === '{head_id}'", f"focus is on {head_id}")
                        self.settle(p)
                        self.assertEqual(p.js("location.hash"), f"#settings&p=PUB&s={slug}")
                        self.assertEqual(p.js("document.querySelectorAll('[data-settings-page]').length"), 1, "one page is drawn")
                        self.assertTrue(self.clear_of_menu(p, f"#{head_id}"), f"{name}: its heading is clear of the menu")
                        self.assertEqual(self.marked(p), name)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_C_the_marked_entry_follows_the_page_you_are_on_by_click_address_and_history(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                trio = (("Profile", "profile", "profile-h"), ("Backups", "backups", "safety-h"), ("Logs and diagnostics", "logs", "diagnostics-h"))
                for name, slug, head_id in trio:      # by a click
                    self.entry(p, name)
                    p.until(f"({MARKED} || {{}}).textContent === '{name}'", f"{name} is marked once chosen")
                    self.assertEqual(p.js("document.querySelectorAll('.set-menu [aria-current]').length"), 1, "one entry is marked")
                    self.assertEqual(p.js(f"{MARKED}.getAttribute('aria-current')"), "page")
                    self.assertTrue(p.js(f"!!document.getElementById('{head_id}')"), "its heading is shown")
                for name, slug, head_id in trio:      # by the address, with no click
                    p.js(f"location.hash = '#settings&p=PUB&s={slug}'")
                    p.until(f"({MARKED} || {{}}).textContent === '{name}'", f"{name} is marked once its address is set")
                    self.assertTrue(p.js(f"!!document.getElementById('{head_id}')"))
                # Back and Forward: each page change was one history step
                p.js("history.back()")
                p.until(f"({MARKED} || {{}}).textContent === 'Backups'", "Back marks the page before")
                p.js("history.back()")
                p.until(f"({MARKED} || {{}}).textContent === 'Profile'", "Back again")
                p.js("history.forward()")
                p.until(f"({MARKED} || {{}}).textContent === 'Backups'", "Forward marks the page after")
                self.assertTrue(p.js("!!document.getElementById('safety-h')"), "and shows it")
                # an unknown page opens Projects, and the address is not left broken
                p.js("location.hash = '#settings&p=PUB&s=nonsense'")
                p.until(f"({MARKED} || {{}}).textContent === 'Projects'", "an unknown page opens Projects")
                p.until("location.hash.indexOf('nonsense') < 0 || document.querySelectorAll('[data-settings-page]').length === 1", "the page is drawn")
                # the last entry, the foot of the menu
                self.entry(p, "Version and updates")
                p.until("document.activeElement && document.activeElement.id === 'update-h'", "focus is on the Version and updates heading")
                self.settle(p)
                self.assertEqual(self.marked(p), "Version and updates", "the last entry stays marked")
                self.assertTrue(self.clear_of_menu(p, "#update-h"))

    def test_C_each_page_keeps_its_own_place_on_the_screen(self):
        # item 1019, for Settings: scroll a page, go to another, come back by Back, and the page is where it was
        for w in (1400, 800):
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w, page="backups")
                p.js("document.body.style.minHeight = (window.innerHeight + 1200) + 'px'")      # room to scroll, whatever the page holds
                p.js("window.scrollTo(0, 400)")
                self.settle(p)
                at = p.js("window.scrollY")
                self.assertGreaterEqual(at, 300, "the page scrolled")
                self.entry(p, "Profile", scrolled_past=True)
                p.until("document.activeElement && document.activeElement.id === 'profile-h'", "the other page is shown")
                self.settle(p)
                self.assertLess(p.js("window.scrollY"), 5, "a page not seen before starts at the top")
                p.js("history.back()")
                p.until(f"({MARKED} || {{}}).textContent === 'Backups'", "Back shows Backups")
                p.until(f"Math.abs(window.scrollY - {at}) <= 3", "and its place is given back")

    def test_C_the_marked_entry_can_be_read_in_light_and_dark(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    size, color, fill = p.js(f"(() => {{ const s = getComputedStyle({MARKED}); return [parseFloat(s.fontSize), s.color, s.backgroundColor]; }})()")
                    ground = p.js("getComputedStyle(document.querySelector('.set-menu')).backgroundColor")
                    self.assertGreaterEqual(size, 13)
                    self.assertGreaterEqual(ratio(rgb(color), rgb(fill)), 4.5, f"{mode}: the marked entry's words on its fill")
                    self.assertGreaterEqual(ratio(rgb(fill), rgb(ground)), 3, f"{mode}: the marked entry's fill on the menu")
                    self.assertNotEqual(fill, p.js("getComputedStyle(document.querySelector('.set-menu .set-item:not([aria-current])')).backgroundColor"),
                                        "the marked entry does not look like the others")

    def test_C_the_menu_link_puts_the_cursor_in_the_name_box_clear_of_the_menu(self):
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
                self.assertTrue(self.clear_of_menu(p, "#about-name"), "the box is clear of the menu")
                self.assertEqual(self.marked(p), "Profile", "the entry of the page holding the box is marked")
                self.assertIn("&s=profile", p.js("location.hash"), "the address names the Profile page")
                self.assertEqual(p.js("document.querySelectorAll('[data-settings-page]').length"), 1, "only the Profile page is shown")

    def test_C_every_entry_is_reachable_and_the_links_that_land_on_a_page_still_land(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            for name, slug, head_id, _ in PAGES:      # all 13 are reachable, each shows a heading and is marked when chosen
                self.entry(p, name)
                p.until(f"!!document.getElementById('{head_id}') && ({MARKED} || {{}}).textContent === '{name}'", f"{name} is reachable")
            p.js("location.hash = '#work&p=PUB'")
            p.until("!document.querySelector('.set-menu')", "left Settings")
            # Settings is no tab (row 976): the profile menu's link lands on Profile with the name box, and a plain #settings address opens Projects
            p.until("(() => { if (document.querySelector('#profile-menu')) return true; "
                    "if (Date.now() - (window.__menuTried || 0) > 1000) { window.__menuTried = Date.now(); document.querySelector('#profile-btn').click(); } "
                    "return !!document.querySelector('#profile-menu'); })()", "the menu opened")
            p.js("document.querySelector('#profile-menu .who-link').click()")
            p.until(f"({MARKED} || {{}}).textContent === 'Profile'", "the profile menu's link lands on Profile")
            p.js("location.hash = '#settings&p=PUB'")
            p.until(f"({MARKED} || {{}}).textContent === 'Projects'", "plain #settings lands on Projects")
            self.assertEqual(p.js("location.hash"), "#settings&p=PUB")
            # a page that was visited before does not decide the next plain #settings
            self.entry(p, "People")
            p.until(f"({MARKED} || {{}}).textContent === 'People'", "People")
            p.js("location.hash = '#settings&p=PUB'")
            p.until(f"({MARKED} || {{}}).textContent === 'Projects'", "plain #settings opens Projects again")


if __name__ == "__main__":
    unittest.main()
