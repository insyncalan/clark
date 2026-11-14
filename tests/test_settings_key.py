"""Command + Option + S opens Settings from any page (v1.0.9), in a real browser against the real page. Chrome is required: these tests fail,
never skip, without it.

Run: python3 dev/run_tests.py test_settings_key
Covers: the chord opens Settings from the Dashboard and from Work items, at 1400 and 900 px; a Mac sends Option + S as the character
"ß" with the code KeyS, and that opens it too; Option + S alone, Command + S alone, Ctrl + Alt + S, Command + Option + Shift + S, a plain S
and a different letter do not; it does nothing from a field, with a menu or Help open and focus on the page body, or with a record open, or on a computer that is not a Mac, or when Settings is already showing; it types nothing.
Only 1400 and 900 px are tested.
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

META, ALT, CTRL, SHIFT = 4, 1, 2, 8
AT_SETTINGS = "location.hash.indexOf('settings') >= 0"


class SettingsKey(Base):
    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until("!!document.querySelector('#pal-btn')", "the top bar is there")
        self.as_a_mac(p)
        return p

    def as_a_mac(self, p):
        p.js("Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel', configurable: true})")

    def stays(self, p, message):
        p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))")      # two frames, not a sleep
        self.assertFalse(p.js(AT_SETTINGS), message)

    def test_the_chord_opens_settings_at_1400_and_900(self):
        for width in (1400, 900):
            for name, key in (("s", "s"), ("the Mac character", "ß")):
                with self.subTest(width=width, key=name), chrome() as cdp:
                    p = self.at(cdp, width)
                    self.assertFalse(p.js(AT_SETTINGS))
                    p.key(key, META | ALT, "KeyS", 83)
                    p.until(AT_SETTINGS, "Command + Option + S opened Settings")

    def test_it_does_nothing_on_a_computer_that_is_not_a_mac(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("Object.defineProperty(navigator, 'platform', {get: () => 'Win32', configurable: true})")
            p.key("s", META | ALT, "KeyS", 83)      # the Windows key reads as Meta
            self.stays(p, "Windows key + Alt + S must not open Settings")

    def test_it_does_nothing_while_a_record_is_open_and_leaves_it_open(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            item = self.store.data_for("ABC")["milestones"][0]["id"]
            p.js(f"clarkPage.openPeek('{item}')")
            p.until("!!clarkPage.peek()", "the record opened")
            p.js("document.activeElement.blur()")
            p.key("ß", META | ALT, "KeyS", 83)
            self.stays(p, "not while a record is open")
            self.assertTrue(p.js("!!clarkPage.peek()"), "and the record stays open")

    def test_it_opens_settings_from_work_items(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("location.hash = '#work'")
            p.until("location.hash.indexOf('work') >= 0", "on Work items")
            p.key("ß", META | ALT, "KeyS", 83)
            p.until(AT_SETTINGS, "opened Settings from Work items")

    def test_other_chords_do_not(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            for mods, key, code, name in ((ALT, "ß", "KeyS", "Option + S"), (META, "s", "KeyS", "Command + S"), (CTRL | ALT, "s", "KeyS", "Ctrl + Alt + S"),
                                          (META | ALT | SHIFT, "Í", "KeyS", "Command + Option + Shift + S"), (0, "s", "KeyS", "S alone"),
                                          (META | ALT, "d", "KeyD", "Command + Option + D")):
                p.key(key, mods, code, 83)
                self.stays(p, name + " must not open Settings")

    def on_body(self, p):
        p.js("document.activeElement && document.activeElement.blur()")
        self.assertTrue(p.js("document.activeElement === document.body"), "focus is on the page body, not in a field")

    def test_it_does_nothing_from_a_field_and_types_nothing(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("var t = document.createElement('textarea'); t.id = 'tt'; document.body.appendChild(t); t.focus()")
            p.key("\u00df", META | ALT, "KeyS", 83)
            self.stays(p, "not from inside a field")
            self.assertEqual(p.js("document.getElementById('tt').value"), "", "and nothing is typed")

    def test_it_does_nothing_while_a_menu_is_open_with_focus_on_the_body(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("document.querySelector('#project-name').click()")
            p.until("!!document.querySelector('[role=menu]')", "a menu is open")
            self.on_body(p)
            self.assertTrue(p.js("!!document.querySelector('[role=menu]')"), "the menu is still open")
            p.key("\u00df", META | ALT, "KeyS", 83)
            self.stays(p, "not while a menu is open")

    def test_it_does_nothing_while_help_is_open_with_focus_on_the_body(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            self.on_body(p)
            p.key("?", 0, "Slash", 191)
            p.until("!!document.querySelector('#help-peek')", "Help opened")
            self.on_body(p)
            self.assertTrue(p.js("!!document.querySelector('#help-peek')"), "Help is still open")
            p.key("\u00df", META | ALT, "KeyS", 83)
            self.stays(p, "not while Help is open")

    def test_it_does_nothing_while_help_is_open_even_with_no_help_peek_element(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("clarkPage.help.open()")
            p.until("clarkPage.help.isOpen()", "Help opened")
            p.js("var h = document.getElementById('help-peek'); if (h) h.remove()")      # only the open flag is left to stop it
            self.on_body(p)
            self.assertTrue(p.js("clarkPage.help.isOpen() && !document.getElementById('help-peek')"), "Help is open and there is no peek element")
            p.key("\u00df", META | ALT, "KeyS", 83)
            self.stays(p, "the open flag alone stops it")

    def test_it_does_nothing_with_a_help_peek_element_and_help_not_open(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("var d = document.createElement('div'); d.id = 'help-peek'; document.body.appendChild(d)")
            self.on_body(p)
            self.assertTrue(p.js("!clarkPage.help.isOpen() && !!document.getElementById('help-peek')"), "the peek element is there and Help is not open")
            p.key("\u00df", META | ALT, "KeyS", 83)
            self.stays(p, "the peek element alone stops it")

    def test_on_settings_already_it_does_not_act_again(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.key("\u00df", META | ALT, "KeyS", 83)
            p.until(AT_SETTINGS, "opened Settings")
            self.on_body(p)
            # window listeners run after the page's own capture listener: defaultPrevented is set only when the chord got past every guard
            p.js("window.__seen = {prevented: [], pushes: 0, hashes: 0};"
                 "window.addEventListener('keydown', e => { if (e.code === 'KeyS') window.__seen.prevented.push(e.defaultPrevented); });"
                 "window.addEventListener('hashchange', () => { window.__seen.hashes++; });"
                 "var push = history.pushState; history.pushState = function () { window.__seen.pushes++; return push.apply(this, arguments); }")
            p.key("\u00df", META | ALT, "KeyS", 83)
            self.assertEqual(p.js("window.__seen.prevented.length"), 1, "the chord reached the page")
            self.assertEqual(p.js("window.__seen.prevented[0]"), False, "the Settings guard stopped it before it acted")
            self.assertEqual(p.js("window.__seen.pushes"), 0, "and added no history entry")
            self.assertEqual(p.js("window.__seen.hashes"), 0, "and changed no address")

    def test_it_acts_once_nothing_is_in_the_way(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("window.__seen = [];window.addEventListener('keydown', e => { if (e.code === 'KeyS') window.__seen.push(e.defaultPrevented); })")
            p.key("\u00df", META | ALT, "KeyS", 83)
            p.until(AT_SETTINGS, "opened once nothing was in the way")
            self.assertEqual(p.js("window.__seen"), [True], "the chord was taken, so the spy in the test above can tell the two apart")

if __name__ == "__main__":
    unittest.main()
