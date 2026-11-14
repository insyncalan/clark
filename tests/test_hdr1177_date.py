"""Item 1177: the header date. In the one slim sticky header the week is a button (.hdr-date) showing "Week ending DD-MM-YYYY". At
rest it looks like plain text; on hover it shows an underline or a background; a click opens clark's calendar and a Friday changes the
week. The old separate date field and calendar button are gone. Widths 1400 and 900 only. Chrome is required.

Run: python3 dev/run_tests.py test_hdr1177_date
"""
import unittest

from _demo import USER
from test_inline_67 import size
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome

DATE = "document.querySelector('.top .hdr-date')"
PANEL = "document.querySelector('.cpop.cdate')"
LOOK = ("(function(){var s=getComputedStyle(" + DATE + "); return {line: s.textDecorationLine, bg: s.backgroundColor, "
        "shadow: s.boxShadow, bb: s.borderBottomWidth + ' ' + s.borderBottomStyle};})()")


class HeaderDate(Base):
    def set_week(self, iso):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"week_ending": iso})

    def week(self):
        return self.store.read("projects", ref="ABC")["week_ending"]

    def show(self, cdp, width=1400):
        p = self.visit(cdp)
        size(cdp, p, width, 900)
        p.until("!!" + DATE, "the header date drew")
        return p

    def hover(self, p, on):
        if on:
            r = p.js("(function(){var r=" + DATE + ".getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];})()")
        else:
            r = [2, 400]
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, p.sid)

    def test_the_date_is_a_button_in_the_header_reading_week_ending_and_the_day(self):
        self.set_week("2031-05-02")
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.show(cdp, w)
                got = p.js("(function(){var e=" + DATE + "; return [e.tagName, !!e.closest('.top'), e.textContent.replace(/\\s+/g, ' ').trim()];})()")
                self.assertEqual(got, ["BUTTON", True, "Week ending 02-05-2031"], f"{w}: the date is a button in the header with its words")
                self.assertEqual(p.js("document.querySelectorAll('.top .hdr-date').length"), 1, f"{w}: exactly one header date")

    def test_the_old_separate_date_picker_is_gone(self):
        with chrome() as cdp:
            p = self.show(cdp)
            gone = p.js("[document.querySelectorAll('#week-ending-pick').length, document.querySelectorAll('input#week-ending').length, "
                        "document.querySelectorAll('#report-bar input').length, document.querySelectorAll('input[type=date]').length]")
            self.assertEqual(gone, [0, 0, 0, 0], "no calendar button, no date field, no input in the bar, no native date input")
            p.js(DATE + ".click()")
            p.until("!!" + PANEL, "the calendar opened")
            self.assertEqual(p.js("document.querySelectorAll('input[type=date]').length"), 0, "the calendar is clark's own")

    def test_at_rest_it_looks_like_plain_text_and_on_hover_it_shows_an_underline_or_a_background(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.show(cdp, w)
                self.hover(p, False)
                rest = p.js(LOOK)
                self.assertEqual(rest["line"], "none", f"{w}: no underline at rest")
                self.assertIn(rest["bg"], ("rgba(0, 0, 0, 0)", "transparent"), f"{w}: no background at rest")
                self.assertEqual(rest["shadow"], "none", f"{w}: no shadow line at rest")
                self.hover(p, True)
                p.until("(function(){var s=getComputedStyle(" + DATE + "); return s.textDecorationLine !== 'none' || "
                        "(s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'transparent') || s.boxShadow !== 'none';})()",
                        "a visible hover state")
                hov = p.js(LOOK)
                self.assertNotEqual(hov, rest, f"{w}: the hover state differs from rest")

    def test_a_click_opens_the_calendar_and_a_friday_changes_the_week(self):
        self.set_week("2031-05-02")
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.show(cdp, w)
                self.set_week("2031-05-02")
                p.js(DATE + ".click()")
                p.until("!!" + PANEL, "the calendar opened")
                self.assertEqual(p.js(PANEL + ".getAttribute('aria-label')"), "Week ending date", f"{w}: the calendar is named")
                p.js("document.querySelector('.cpop [data-day=\"2031-05-09\"]').click()")
                p.saved()
                self.assertEqual(self.week(), "2031-05-09", f"{w}: the stored week moved to the Friday")
                p.until("/09-05-2031/.test(" + DATE + ".textContent)", "the header shows the new week")
                p.until("!(%s)" % PANEL, "the calendar closed")
                self.assertEqual(p.js("document.querySelectorAll('.top .hdr-date').length"), 1, f"{w}: still one header date")
                self.set_week("2031-05-02")

    def test_a_day_that_is_not_a_friday_keeps_the_old_week(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            p.js(DATE + ".click()")
            p.until("!!" + PANEL, "the calendar opened")
            p.js("document.querySelector('.cpop [data-day=\"2031-05-07\"]').click()")
            p.until("/Friday/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the message")
            self.assertEqual(self.week(), "2031-05-02", "the stored week is unchanged")
            self.assertIn("02-05-2031", p.js(DATE + ".textContent"), "the header still shows the old week")


if __name__ == "__main__":
    unittest.main()
