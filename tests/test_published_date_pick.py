"""Row 1178: picking a day in the published report's date box (TopBar.jsx, AsAtDate). A picked day that matches a past report of the
file goes to that report; any other day keeps this report and says "No report for DD-MM-YYYY."; the day already shown does nothing.
The date box is set with the page script and a change event (no native popup). In a real browser, at 1400 and 900 px. Fictional data.

Run: python3 dev/run_tests.py test_published_date_pick        (needs Chrome)
"""
import unittest

import test_glance_page
from _publish import PublishedFile
from test_report_editor import EMPTY_BRANDING, tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import publish as publish_module

PAST_DAY = "2026-10-21"
PAST_FILE = "ABC-report-2026-10-21.html"
NOTE = "document.querySelector('.asat-note') ? document.querySelector('.asat-note').textContent : ''"


class PickADay(PublishedFile, test_glance_page.Setup):
    def setUp(self):
        super().setUp()
        self.path = self.publish()
        built = publish_module.build(self.store, "ABC", "2026-10-28", EMPTY_BRANDING, past_reports=[{"week_ending": PAST_DAY, "file": PAST_FILE}])
        self.path.write_bytes(built["body"])
        (self.path.parent / PAST_FILE).write_text("<!doctype html><title>the earlier report</title><p>earlier</p>", encoding="utf-8")

    def page(self, cdp, width):
        p = self.draw(cdp, self.path, width)
        p.until("!!document.querySelector('button.asat')", "the date button drew")
        return p

    def pick(self, p, day):
        p.js("document.querySelector('button.asat').click()")
        p.until("!!document.querySelector('input.asat-box')", "the date box opened")
        p.js("""((day) => { const b = document.querySelector('input.asat-box'); b.value = day;
          b.dispatchEvent(new Event('change', {bubbles: true})); })(%r)""" % day)

    def test_a_day_with_a_past_report_goes_to_that_report(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                self.pick(p, PAST_DAY)
                self.assertTrue(wait(lambda: p.js("location.href").endswith("/" + PAST_FILE), 10), f"went to the earlier report, now at {p.js('location.href')}")
                self.assertTrue(wait(lambda: p.js("document.title") == "the earlier report", 10), "and that report is the page")

    def test_another_day_shows_the_note_and_stays(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                here = p.js("location.href")
                self.pick(p, "2026-10-14")
                p.until("!!document.querySelector('.asat-note')", "the note drew")
                self.assertEqual(p.js(NOTE), "No report for 14-10-2026.")
                self.assertEqual(p.js("document.querySelector('.asat-note').getAttribute('role')"), "status")
                self.assertEqual(p.js("location.href"), here, "this report stays")
                self.assertEqual(p.js("document.querySelectorAll('input.asat-box').length"), 0, "the date box closed")

    def test_a_half_typed_year_is_not_a_pick_and_the_box_stays_open(self):
        """Typing the year 2026 passes through whole dates such as 0202-10-14; none of them may close the box or draw a note."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                here = p.js("location.href")
                self.pick(p, "0202-10-14")
                self.assertEqual(p.js("document.querySelectorAll('input.asat-box').length"), 1, "the date box is still open")
                self.assertEqual(p.js(NOTE), "", "no note for a half-typed year")
                self.assertEqual(p.js("location.href"), here)
                p.js("""((day) => { const b = document.querySelector('input.asat-box'); b.value = day;
                  b.dispatchEvent(new Event('change', {bubbles: true})); })('2026-10-14')""")
                p.until("!!document.querySelector('.asat-note')", "the whole year is a pick")
                self.assertEqual(p.js(NOTE), "No report for 14-10-2026.")

    def test_the_button_does_not_take_focus_from_the_open_box(self):
        """Clicking the button while the box is open must close it: its mouse-down is cancelled, so the box is not blurred (and shut) first."""
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            p.js("document.querySelector('button.asat').click()")
            p.until("!!document.querySelector('input.asat-box')", "the date box opened")
            self.assertTrue(p.js("(() => { const e = new MouseEvent('mousedown', {bubbles: true, cancelable: true}); document.querySelector('button.asat').dispatchEvent(e); return e.defaultPrevented; })()"))

    def test_the_same_day_does_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                here = p.js("location.href")
                self.pick(p, "2026-10-28")
                p.until("document.querySelectorAll('input.asat-box').length === 0", "the date box closed")
                self.assertEqual(p.js(NOTE), "", "no note")
                self.assertEqual(p.js("location.href"), here, "this report stays")
                self.assertRegex(p.js("document.querySelector('button.asat').textContent"), r"28-10-2026")


if __name__ == "__main__":
    unittest.main()
