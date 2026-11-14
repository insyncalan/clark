"""Issue 672, moved by item 1177: the header's date button (.hdr-date, id week-ending-pick) opens clark's own date picker (never the browser's), in a real browser.

Run: python3 dev/run_tests.py test_report_bar_pick
"""
import re
import unittest

from _paths import SRC
from test_report_bar import Bar
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

PAGE = SRC / "clark" / "page"
PANEL = "document.querySelector('.cpop.cdate')"


class Pick(Bar):
    def opened(self, p):
        p.js("document.querySelector('#week-ending-pick').click()")
        p.until("!!" + PANEL, "the panel opened")

    def press(self, p, key, code, vk, text):
        """A key that types (Enter, Space) carries its text, as a real keyboard's does, so a button takes it as a click."""
        p.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "code": code, "windowsVirtualKeyCode": vk, "text": text}, p.sid)
        p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": code, "windowsVirtualKeyCode": vk}, p.sid)

    def test_the_button_has_its_words_and_there_is_no_browser_calendar(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelector('#week-ending-pick').getAttribute('aria-label')"), "Week ending 02-05-2031. Click to change date")
            self.assertEqual(p.js("document.querySelector('#week-ending-pick').title"), "Click to change date")
            self.assertEqual(p.js("document.querySelectorAll('#report-bar input').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('#report-bar input[type=date], #report-bar input[type=hidden]').length"), 0)
            self.opened(p)
            self.assertEqual(p.js("document.querySelectorAll('input[type=date]').length"), 0)

    def test_the_panel_is_named_and_offers_only_friday(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            self.opened(p)
            self.assertEqual(p.js(PANEL + ".getAttribute('aria-label')"), "Week ending date")
            self.assertEqual(p.js("[...document.querySelectorAll('.cpop .cp-q button span:not(.mi-i)')].map((e) => e.textContent)"), ["Friday"])

    def test_a_friday_is_saved_like_typing_it(self):
        self.set_week("2031-05-02")
        for how in ("day", "quick"):
            with self.subTest(how=how), chrome() as cdp:
                p = self.show(cdp)
                self.opened(p)
                if how == "day":
                    p.js("document.querySelector('.cpop [data-day=\"2031-05-09\"]').click()")
                else:
                    p.js("document.querySelector('.cpop [data-quick]').click()")
                p.saved()
                want = "2031-05-09" if how == "day" else self.store.read("projects", ref="ABC")["week_ending"]
                self.assertEqual(self.week(), want)
                self.assertRegex(p.toast(), r"^Week ending changed to \d\d-\d\d-\d{4}\.$")
                p.until("!(%s)" % PANEL, "the panel closed")      # it closes a frame after the save is shown
                self.assertIsNone(p.js(PANEL))
                self.assertEqual(p.js("document.activeElement.id"), "week-ending-pick")
                self.set_week("2031-05-02")

    def test_a_day_that_is_not_a_friday_keeps_the_old_value(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            self.opened(p)
            p.js("document.querySelector('.cpop [data-day=\"2031-05-07\"]').click()")
            p.until("/Week ending is a Friday\\. Pick Friday 09-05-2031\\./.test((document.querySelector('.toast-text') || {}).textContent || '')", "the message")
            self.assertEqual(self.week(), "2031-05-02")
            self.assertEqual(p.js("document.querySelector('.hdr-date').textContent"), "Week ending 02-05-2031")

    def test_esc_closes_only_the_panel_and_keys_work(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.until("!!document.querySelector('#report-hint')", "Edit")
            p.js("document.querySelector('#week-ending-pick').focus()")
            self.press(p, "Enter", "Enter", 13, "\r")
            p.until("!!" + PANEL, "Enter on the button opened it")
            p.until("document.querySelector('.cpop').contains(document.activeElement)", "focus is in the panel")
            p.key("ArrowRight", code="ArrowRight", vk=39)
            p.until("document.activeElement.dataset.day === '2031-05-03'", "an arrow moved a day")
            p.key("Escape", code="Escape", vk=27)
            p.until("!" + PANEL, "Esc closed the panel")
            self.assertEqual(p.js("document.querySelector('#report').dataset.mode"), "edit", "Edit stays")
            self.assertTrue(p.js("!!document.querySelector('#report-bar')"))
            self.assertEqual(p.js("document.activeElement.id"), "week-ending-pick")
            self.assertEqual(self.week(), "2031-05-02")
            self.press(p, " ", "Space", 32, " ")
            p.until("!!" + PANEL, "Space on the button opened it")


class Source(unittest.TestCase):
    def test_the_bar_has_no_browser_date_input(self):
        text = (PAGE / "src" / "edit" / "ReportBar.jsx").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"type\s*[=:]\s*[\"'](date|datetime-local|month|week|hidden)[\"']|showPicker", text))

    def test_due_pick_defaults_are_unchanged(self):
        text = (PAGE / "src" / "edit" / "cells" / "DuePick.jsx").read_text(encoding="utf-8")
        self.assertIn('choices || quickDates(today).concat(canClearDue(row) ? [["No date", ""]] : [])', text)
        self.assertIn("label || `${what} of ${row.id}`", text)


if __name__ == "__main__":
    unittest.main()
