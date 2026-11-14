"""Command + Option + S opens Settings from any page (v1.0.9), in a real browser against the real page. Chrome is required: these tests fail,
never skip, without it.

Run: python3 dev/run_tests.py test_settings_key
Covers: the chord opens Settings from the Dashboard and from Work items, at 1400 and 900 px; a Mac sends Option + S as the character
"ß" with the code KeyS, and that opens it too; Option + S alone, Command + S alone, Ctrl + Alt + S, Command + Option + Shift + S, a plain S
and a different letter do not; it does nothing from a field, with a menu, Help or a record open, or on a computer that is not a Mac, or when Settings is already showing; it types nothing.
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

    def test_it_does_nothing_from_a_field_a_menu_or_help_and_not_twice(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("var t = document.createElement('textarea'); t.id = 'tt'; document.body.appendChild(t); t.focus()")
            p.key("ß", META | ALT, "KeyS", 83)
            self.stays(p, "not from inside a field")
            self.assertEqual(p.js("document.getElementById('tt').value"), "", "and nothing is typed")
            p.js("document.getElementById('tt').remove(); document.querySelector('#project-name').click()")
            p.until("!!document.querySelector('[role=menu]')", "a menu is open")
            p.key("ß", META | ALT, "KeyS", 83)
            self.stays(p, "not while a menu is open")
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('[role=menu]')", "the menu closed")
            p.key("?", 0, "Slash", 191)
            p.until("!!document.querySelector('#help-peek')", "Help opened")
            p.key("ß", META | ALT, "KeyS", 83)
            self.stays(p, "not while Help is open")
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('#help-peek')", "Help closed")
            p.key("ß", META | ALT, "KeyS", 83)
            p.until(AT_SETTINGS, "opened once nothing was in the way")
            before = p.js("history.length")
            p.key("ß", META | ALT, "KeyS", 83)
            p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))")
            self.assertEqual(p.js("history.length"), before, "on Settings already, it adds no history entry")


if __name__ == "__main__":
    unittest.main()
