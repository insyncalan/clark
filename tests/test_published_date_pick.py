"""Row 1178, kept by row 1253: picking a day in the published report's date box. Row 1253 took the date button out of Classic; the frozen
Cards theme keeps it (components/CardsDate.jsx), and these tests draw the Cards page (page_html with no Theme) so they fail if that button
is removed. A picked day that matches a past report of the
file goes to that report; any other day keeps this report and says "No report for DD-MM-YYYY."; the day already shown does nothing.
The date box is set with the page script and a change event (no native popup). In a real browser, at 1400 and 900 px. Fictional data.

Run: python3 dev/run_tests.py test_published_date_pick        (needs Chrome)
"""
import unittest
from unittest import mock

import test_glance_page
from _publish import PublishedFile
from test_report_editor import EMPTY_BRANDING, tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import publish as publish_module

PAST_DAY = "2026-10-21"
PAST_FILE = "ABC-report-2026-10-21.html"
NOTE = "document.querySelector('.asat-note') ? document.querySelector('.asat-note').textContent : ''"


class PickADay(PublishedFile, test_glance_page.Setup):
    theme = None      # the Cards page is what page_html draws with no Theme; the store's setting cannot ask for it (row 1363), so theme_of is patched below

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(publish_module, "theme_of", lambda store: None)
        patch.start()
        self.addCleanup(patch.stop)
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

    def pick_open(self, p, day):
        """Set the day on the box that is already open (or open it first), and fire change."""
        if not p.js("!!document.querySelector('input.asat-box')"):
            p.js("document.querySelector('button.asat').click()")
            p.until("!!document.querySelector('input.asat-box')", "the date box opened")
        p.js("""((day) => { const b = document.querySelector('input.asat-box'); b.value = day;
          b.dispatchEvent(new Event('change', {bubbles: true})); })(%r)""" % day)

    def test_the_cards_page_has_the_date_button_and_classic_has_none_row_1253(self):
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            self.assertRegex(p.js("document.querySelector('button.asat').textContent"), r"As at 28-10-2026")
        with mock.patch.object(publish_module, "theme_of", lambda store: "prototype-2.0"):
            classic = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, classic, 1400)
            self.assertEqual(p.js("document.querySelectorAll('button.asat').length"), 0, "Classic has no date button")

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

    def test_the_year_rule_has_both_branches(self):
        """A year from 1990 to 1999 (the 199x branch) is a pick; 1980 and 3000 are not (outside both branches), so the box stays open."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                here = p.js("location.href")
                for day in ("1980-06-05", "3000-06-05"):
                    self.pick_open(p, day)
                    self.assertEqual(p.js("document.querySelectorAll('input.asat-box').length"), 1, f"{day} leaves the box open")
                    self.assertEqual(p.js(NOTE), "", f"no note for {day}")
                    self.assertEqual(p.js("location.href"), here)
                self.pick_open(p, "1995-06-05")
                p.until("!!document.querySelector('.asat-note')", "1995 is a pick")
                self.assertEqual(p.js(NOTE), "No report for 05-06-1995.")
                self.assertEqual(p.js("document.querySelectorAll('input.asat-box').length"), 0, "the date box closed")
                self.assertEqual(p.js("location.href"), here)

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
