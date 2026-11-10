"""#179: Appearance (System, Light, Dark) in Settings › Personal and as the same Appearance group in the profile menu, in a real browser at 1400 and
900 px. Run: python3 dev/run_tests.py test_appearance

The choice is one setting for this person on this computer, remembered in the browser as the section style is and applied as
`data-theme` on the page (Light none, Dark "dark", System "auto", which the page's own colour-scheme rule answers). What is asserted:
the group and its words; System is the default and follows the computer both ways with no reload while Light and Dark do not; the
menu has the same three choices, in the same order, below the separator, the one in use marked; a change in either place shows in
the other at once; a reload keeps it; every page is dark when Dark is chosen, with no sideways scroll; a published file never has it.
Chrome is required: these tests fail, never skip, without it.
"""
import re
import unittest

from _paths import SRC
from _new_page import reload_to_new_page
from test_publish_dialog import Base, PAGE_SRC
from test_server import chrome

from clark import page

WIDTHS = (1400, 900)
ORDER = ["System", "Light", "Dark"]


def scheme(p, value):
    p.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": value}]}, p.sid)


class Appearance(Base):
    def open_settings(self, p):
        p.js("document.querySelector('#profile-btn').click()")
        p.until("!!document.querySelector('#profile-menu')", "the menu opened")
        p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
        p.until("!!document.querySelector('#personal')", "Settings › Personal drew")

    def open_menu(self, p):
        """Open the profile menu, clicking again if the first click is lost: right after a page load the button is already in the page before
        the page's own script has taken it, so a click on a slow computer does nothing. It never clicks twice within a second (a second click
        would close a menu that is still drawing), and it stops at once when the menu is there."""
        p.until("(() => { if (document.querySelector('#profile-menu')) return true; "
                "if (Date.now() - (window.__menuTried || 0) > 1000) { window.__menuTried = Date.now(); document.querySelector('#profile-btn').click(); } "
                "return !!document.querySelector('#profile-menu'); })()", "the menu opened")

    def in_settings(self, p):
        return p.js("[...document.querySelectorAll('#personal [data-appearance] .seg button')].filter(i => i.getAttribute('aria-checked') === 'true').map(i => i.dataset.themePick)")

    def in_menu(self, p):
        return p.js("[...document.querySelectorAll('#profile-menu [role=menuitemradio]')].filter(i => i.getAttribute('aria-checked') === 'true').map(i => i.textContent.replace('✓', ''))")

    def paper(self, p):
        """The page's own background, as it is drawn now."""
        return p.js("getComputedStyle(document.body).backgroundColor")

    def lightness(self, p):
        rgb = [int(x) for x in re.findall(r"\d+", self.paper(p))[:3]]
        return sum(rgb) / 3

    def test_C_settings_has_the_appearance_group_with_system_as_the_default(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                self.assertEqual(p.js("document.querySelector('#personal [data-appearance] legend').textContent"), "Appearance")
                self.assertEqual(p.js("[...document.querySelectorAll('#personal [data-appearance] .seg button')].map(b => b.textContent)"), ORDER)
                self.assertEqual(self.in_settings(p), ["system"])
                self.assertEqual(p.js("document.querySelector('#personal [data-appearance-line]').textContent"),
                                 "Follows your Mac's setting.", "the chosen one's line is under the control")
                self.assertEqual(p.js("document.documentElement.dataset.theme"), "auto")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_C_appearance_is_a_segmented_control_not_radio_buttons(self):       # item 677
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                self.assertEqual(p.js("document.querySelectorAll('#personal [data-appearance] input').length"), 0, "no radio buttons")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('#personal [data-appearance] .seg')).borderRadius"), "999px", "the page's .seg pill")
                self.assertEqual(p.js("document.querySelector('#personal [data-appearance] .seg').getAttribute('role')"), "radiogroup")
                self.assertEqual(p.js("[...document.querySelectorAll('#personal [data-appearance] .seg button')].map(b => b.getAttribute('role')).join()"), "radio,radio,radio")
                self.assertEqual(p.js("[...document.querySelectorAll('#personal [data-appearance] .seg button')].map(b => b.tabIndex).join()"), "0,-1,-1", "one tab stop: the chosen")
                p.js("document.querySelector('#personal [data-appearance] button[data-theme-pick=dark]').click()")
                self.assertEqual(self.in_settings(p), ["dark"], "one is pressed")
                self.assertEqual(p.js("document.querySelector('#personal [data-appearance-line]').textContent"), "Always dark.", "the line follows the choice")

    def test_C_appearance_arrow_keys_move_and_pick_row_902(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            # A hosted runner can draw late and does not always give the page the keyboard: ask for the page to be focused, and before every key
            # wait until the radio the key starts from really holds focus (put it back there if a late redraw took it), so the key goes to the group.
            p.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
            p.cdp.call("Page.bringToFront", {}, p.sid)
            at = "system"
            for key, want in (("ArrowRight", "light"), ("ArrowRight", "dark"), ("ArrowRight", "system"), ("ArrowLeft", "dark")):
                p.until(f"(() => {{ const b = document.querySelector('#personal [data-appearance] button[data-theme-pick={at}]'); if (!b) return false;"
                        f" if (document.activeElement !== b) b.focus(); return document.activeElement === b; }})()", f"before {key}: focus is on the {at} radio")
                p.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "code": key, "windowsVirtualKeyCode": {"ArrowRight": 39, "ArrowLeft": 37}[key]}, p.sid)
                p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": key, "windowsVirtualKeyCode": {"ArrowRight": 39, "ArrowLeft": 37}[key]}, p.sid)
                p.until(f"document.querySelector('#personal [data-appearance] button[data-theme-pick={want}]').getAttribute('aria-checked') === 'true'", f"{key} picked {want} (the radio is checked)")
                p.until(f"document.documentElement.dataset.theme === '{ {'light': '', 'dark': 'dark', 'system': 'auto'}[want] }' || ('{want}' === 'light' && !document.documentElement.dataset.theme)", f"{key} picked {want}")
                self.assertEqual(self.in_settings(p), [want])
                p.until(f"document.activeElement && document.activeElement.dataset.themePick === '{want}'", f"{key}: focus follows to the {want} radio")
                self.assertEqual(p.js("document.activeElement.dataset.themePick"), want, "focus follows")
                at = want
            self.open_menu(p)
            self.assertEqual(self.in_menu(p), ["Dark"], "the menu agrees")

    def test_C_chosen_appearance_segment_keeps_the_pill_look_row_902(self):
        for scheme_name in ("light", "dark"):
            for w in WIDTHS:
                with self.subTest(scheme=scheme_name, width=w), chrome() as cdp:
                    p = self.page(cdp)
                    p.width(w)
                    scheme(p, scheme_name)
                    self.open_settings(p)
                    p.js("document.querySelector('#personal [data-appearance] button[data-theme-pick=light]').click()")
                    got = p.js("(() => { const on = document.querySelector('#personal [data-appearance] button[aria-checked=true]'), off = document.querySelector('#personal [data-appearance] button[aria-checked=false]');"
                               " return [getComputedStyle(on).backgroundImage, getComputedStyle(on).color, getComputedStyle(off).backgroundImage, getComputedStyle(on).fontWeight]; })()")
                    self.assertIn("gradient", got[0], "the chosen segment has the pill gradient")
                    self.assertNotEqual(got[1], p.js("getComputedStyle(document.querySelector('#personal [data-appearance] button[aria-checked=false]')).color"), "the chosen text colour differs")
                    self.assertNotIn("gradient", got[2], "the others have none")
                    p.js("document.querySelector('#personal [data-appearance] button[data-theme-pick=system]').focus()")
                    p.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End", "windowsVirtualKeyCode": 35}, p.sid)
                    p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "End", "code": "End", "windowsVirtualKeyCode": 35}, p.sid)
                    p.until("document.documentElement.dataset.theme === 'dark'", "End picks the last")

    def key(self, p, name, code, mods=0):
        for kind in ("keyDown", "keyUp"):
            p.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": name, "windowsVirtualKeyCode": code, "modifiers": mods}, p.sid)

    def test_C_home_picks_the_first_choice_and_focus_follows_row_902(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("document.querySelector('#personal [data-appearance] button[data-theme-pick=dark]').click()")
            p.js("document.querySelector('#personal [data-appearance] button[data-theme-pick=dark]').focus()")
            self.key(p, "Home", 36)
            p.until("document.documentElement.dataset.theme === 'auto'", "Home picks System, the first")
            self.assertEqual(self.in_settings(p), ["system"])
            self.assertEqual(p.js("document.activeElement.dataset.themePick"), "system", "focus follows")

    def test_C_a_key_with_a_modifier_held_does_not_change_the_choice_row_902(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("document.querySelector('#personal [data-appearance] button[data-theme-pick=system]').focus()")
            p.js("window.__swallowed = []; document.addEventListener('keydown', e => window.__swallowed.push(e.defaultPrevented), false)")
            for mods in (1, 2, 4, 8):                      # alt, ctrl, meta, shift
                self.key(p, "ArrowRight", 39, mods)
                self.key(p, "End", 35, mods)
            self.assertEqual(self.in_settings(p), ["system"], "the choice is unchanged")
            self.assertEqual(p.js("document.documentElement.dataset.theme"), "auto")
            self.assertEqual(p.js("window.__swallowed.some(Boolean)"), False, "no key was swallowed")

    def test_C_system_follows_the_computer_both_ways_with_no_reload_and_light_and_dark_do_not(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("window.__same = 1")
            scheme(p, "dark")
            p.until("window.__same === 1", "no reload")
            dark = self.lightness(p)
            scheme(p, "light")
            light = self.lightness(p)
            self.assertLess(dark, 90, "System: dark when the computer is dark")
            self.assertGreater(light, 200, "System: light when the computer is light")
            self.assertEqual(p.js("window.__same"), 1, "the same page throughout: no reload")
            for choice, want in (("light", "light"), ("dark", "dark")):
                p.js(f"document.querySelector('#personal [data-appearance] button[data-theme-pick={choice}]').click()")
                for computer in ("dark", "light"):
                    scheme(p, computer)
                    self.assertEqual("dark" if self.lightness(p) < 90 else "light", want, f"{choice} chosen, computer {computer}")

    def test_C_the_menu_has_dark_mode_with_the_same_three_in_the_same_order_below_the_separator(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_menu(p)
                roles = p.js("[].map.call(document.querySelector('#profile-menu').children, function(e){return e.getAttribute('role')})")
                self.assertEqual(roles[:8], ["menuitem", "menuitem", "menuitem", "menuitem", "menuitem", "menuitem", "separator", "group"])     # the name line, Publish, Preview, Export to Excel, Export to Word (#48), Published reports (#443); Settings and Help follow the group
                self.assertEqual(p.js("[].map.call(document.querySelector('#profile-menu [role=group]').children, function(e){return e.getAttribute('role')}).join()"),
                                 "presentation,menuitemradio,menuitemradio,menuitemradio", "the label and the three radios are one group")
                self.assertEqual(p.js("document.querySelectorAll('#profile-menu .lab')[0].textContent"), "Appearance", "the group has the same name in the menu as in Settings")
                self.assertEqual(p.js("[...document.querySelectorAll('#profile-menu [role=menuitemradio]')].map(i => i.textContent.replace('✓', ''))"), ORDER)
                self.assertEqual(self.in_menu(p), ["System"], "the one in use is marked")

    def test_C_one_setting_two_places_both_ways_with_no_reload(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("window.__same = 1")
            p.js("document.querySelector('#personal [data-appearance] button[data-theme-pick=dark]').click()")
            self.open_menu(p)
            self.assertEqual(self.in_menu(p), ["Dark"], "a change in Settings shows in the menu")
            p.js("document.querySelector('#profile-menu [data-kind=look-light]').click()")
            p.until("!document.querySelector('#profile-menu')", "picking closed the menu")
            self.assertEqual(self.in_settings(p), ["light"], "a change in the menu shows in Settings")
            self.assertEqual(p.js("document.documentElement.dataset.theme || 'none'"), "none", "Light sets no attribute")
            self.assertEqual(p.js("window.__same"), 1)

    def test_C_the_choice_is_remembered_across_a_reload(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.js("document.querySelector('#profile-menu [data-kind=look-dark]').click()")
            p.until("document.documentElement.dataset.theme === 'dark'", "Dark applied")
            self.assertEqual(p.js("localStorage.getItem('clark.appearance')"), "dark")
            reload_to_new_page(p.js)
            p.until("!!document.querySelector('#profile-btn') && document.documentElement.dataset.theme === 'dark'", "Dark again after a reload")
            self.open_menu(p)
            self.assertEqual(self.in_menu(p), ["Dark"])

    def test_C_with_dark_chosen_every_page_is_dark_and_does_not_scroll_sideways(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                scheme(p, "light")                                   # the computer is light: only the choice can make it dark
                self.open_menu(p)
                p.js("document.querySelector('#profile-menu [data-kind=look-dark]').click()")
                p.until("document.documentElement.dataset.theme === 'dark'", "Dark applied")
                for view in ("dashboard", "work", "milestones"):
                    p.js(f"document.querySelector('[data-view={view}]').click()")
                    p.until(f"!!document.querySelector('#{ 'report' if view == 'dashboard' else view }')", f"{view} drew")
                    self.assertLess(self.lightness(p), 90, f"{view} is dark")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{view}: no sideways scroll")
                self.open_settings(p)
                self.assertLess(self.lightness(p), 90, "Settings is dark")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "Settings: no sideways scroll")


class Source(unittest.TestCase):
    def test_a_published_file_has_no_appearance_setting(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        self.assertNotIn("clark.appearance", view)
        self.assertNotIn("data-appearance", view)
        for path in PAGE_SRC.rglob("*.js*"):
            if path.name == "appearance.js":
                continue
            text = path.read_text(encoding="utf-8")
            if "stores/appearance.js" in text:
                self.assertIn("/edit/", path.as_posix(), f"{path.name} is not an Edit part but imports the appearance setting")

    def test_the_words_are_pinned(self):
        text = (PAGE_SRC / "edit" / "Personal.jsx").read_text(encoding="utf-8")
        for words in ('["system", "System", "Follows your Mac\'s setting."]', '["light", "Light", "Always light."]', '["dark", "Dark", "Always dark."]',
                      "<legend>Appearance</legend>"):
            self.assertIn(words, text)
        self.assertIn('lab: "Appearance"', (PAGE_SRC / "edit" / "ProfileMenu.jsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
