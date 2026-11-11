"""#912: the Milestones page's Calendar keyboard and focus checks, split out of test_milestones_page.py so the two run side by side.

Run: python3 dev/run_tests.py test_milestones_calendar
The same tests as before, unchanged, on the same real-browser helpers (BrowserBase in test_milestones_page.py).
"""
import itertools
import json
import time
import unittest

from test_milestones_page import BrowserBase
from test_server import chrome, wait

class CalendarKeys(BrowserBase, unittest.TestCase):
    def test_the_keys_move_the_period_and_the_range_message_offers_go_to_today(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            for name, want in (("PageDown", "November 2026"), ("PageDown", "December 2026"), ("PageUp", "November 2026"), ("PageUp", "October 2026")):
                self.key(cdp, sid, name)
                self.assertTrue(wait(lambda: self.title(cdp, sid) == want), f"{name} gives {want}")
            self.key(cdp, sid, "ArrowRight")                  # #481: an arrow on the calendar itself no longer steps a period; it moves a day, from a day
            time.sleep(0.2)
            self.assertEqual(self.title(cdp, sid), "October 2026")
            cdp.js("document.querySelector('[data-scale-b=week]').click()", sid)
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Week of 26-10-2026"))
            self.key(cdp, sid, "PageDown")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Week of 02-11-2026"))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-cal-far]').length", sid), 0)
            cdp.js("document.querySelector('[data-scale-b=quarter]').click()", sid)
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Q4 2026"))
            for _ in range(300):
                self.key(cdp, sid, "PageDown")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-cal-far]')", sid)), "the range message")
            self.assertIn("Go back to today", cdp.js("document.querySelector('[data-cal-far]').textContent", sid))
            far_title = self.title(cdp, sid)
            self.assertTrue(far_title.endswith("2100"), far_title)
            cdp.js("document.querySelector('[data-cal-home]').click()", sid)
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Q4 2026"))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-cal-far]').length", sid), 0)
    def test_the_ghost_chip_says_expected_once_and_no_chip_text_is_cut(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.view(cdp, width, theme)
                    cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)
                    got = cdp.js("""(() => {
                        const out = {ghost: [], cut: []};
                        for (const c of document.querySelectorAll('.cal-ms')) {
                            const sp = c.querySelector('span');
                            if (c.dataset.ghost === '1') out.ghost.push([sp.textContent, c.getAttribute('aria-label')]);
                            const shown = (e) => e && getComputedStyle(e).display !== 'none';
                            if (c.scrollWidth > c.clientWidth + 1) out.cut.push(c.dataset.ms);
                            if (shown(sp) && sp.scrollWidth > sp.clientWidth + 1) out.cut.push(c.dataset.ms);
                        }
                        return out; })()""", sid)
                    self.assertEqual(got["cut"], [], "no chip text is cut off")
                    self.assertTrue(got["ghost"], "there is a slipped milestone's chip to check")
                    for visible, label in got["ghost"]:
                        self.assertTrue(visible.startswith("Expected: "), "the prototype's words: 'Expected: ' then the name")
                        self.assertEqual(visible.count("Expected"), 1)
                        self.assertTrue(label.startswith("Expected: "), "the accessible name says it too")
    def test_the_expected_chip_is_whole_at_900_px_and_in_quarter(self):
        for width, theme, scale in itertools.product((1400, 900), ("light", "dark"), ("month", "quarter")):
            with self.subTest(width=width, theme=theme, scale=scale), chrome() as cdp:
                sid = self.view(cdp, width, theme)
                cdp.js(f"document.querySelector('[data-scale-b={scale}]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('.cal').dataset.scale", sid) == scale))
                if scale == "month":                      # the slipped milestone's expected day is in November (Quarter holds it already)
                    cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-ms.ghost')", sid)))
                got = cdp.js("""[...document.querySelectorAll('.cal-ms.ghost')].map(c => { const sp = c.querySelector('span'), r = c.getBoundingClientRect();
                    return [sp.textContent, getComputedStyle(sp).display, sp.scrollWidth <= sp.clientWidth + 1, r.right <= document.documentElement.clientWidth,
                            c.getAttribute('aria-label') || '', c.title || '', getComputedStyle(c).borderTopStyle]; })""", sid)
                for text, display, fits, inside, label, title, border in got:
                    self.assertTrue(text.startswith("Expected: ") and len(text) > len("Expected: "), "the chip still carries Expected: and the name")
                    self.assertTrue(label.startswith("Expected: "), "the accessible name says it too")
                    self.assertTrue(inside, "not past the page edge")
                    if scale == "month":
                        self.assertNotEqual(display, "none", "shown, not hidden by the scale")
                        self.assertTrue(fits, "not cut off")
                    else:                                  # row 821: Quarter draws the mark only, the words are the tooltip
                        self.assertEqual(display, "none", "Quarter shows the mark only")
                        self.assertEqual(border, "dashed", "a slipped milestone keeps its dashed outline")
                        self.assertIn("expected", title.lower(), "the tooltip says it is expected")
    def test_switching_scale_always_lands_on_the_current_period(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.view(cdp, width, theme)
                    for _ in range(3):
                        before = self.title(cdp, sid)
                        cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)
                        self.assertTrue(wait(lambda: self.title(cdp, sid) != before))
                    self.assertEqual(self.title(cdp, sid), "January 2027")
                    for scale, label in (("quarter", "Q4 2026"), ("week", "Week of 26-10-2026"), ("month", "October 2026")):
                        cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)           # wander off, then switch
                        cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)
                        cdp.js(f"document.querySelector('[data-scale-b={scale}]').click()", sid)
                        self.assertTrue(wait(lambda: self.title(cdp, sid) == label), f"{scale} opens on {label}")
    def test_the_quarter_month_button_has_a_visible_focus_ring(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.view(cdp, width, theme)
                    cdp.js("document.querySelector('[data-scale-b=quarter]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-qm')", sid)))
                    cdp.js("document.querySelector('.cal').focus()", sid)
                    for _ in range(60):                       # a real Tab, so the browser treats it as keyboard focus
                        if cdp.js("document.activeElement.classList.contains('cal-qm')", sid):
                            break
                        for kind in ("rawKeyDown", "keyUp"):
                            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9}, sid)
                        time.sleep(0.03)
                    ring = cdp.js("""(() => { const b = document.activeElement;
                        const s = getComputedStyle(b); return [b.classList.contains('cal-qm') && b.matches(':focus-visible'), s.outlineStyle, parseFloat(s.outlineWidth), s.outlineColor]; })()""", sid)
                    self.assertTrue(ring[0], "focus-visible matches")
                    self.assertEqual(ring[1], "solid")
                    self.assertGreaterEqual(ring[2], 2)
                    self.assertNotIn(ring[3], ("rgba(0, 0, 0, 0)", "transparent"))
    def test_shift_and_typing_in_a_field_or_editable_do_not_move_the_period(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            before = self.title(cdp, sid)
            fire = ("(tag, init) => { const el = document.createElement(tag); if (tag === 'div') el.contentEditable = 'true'; "
                    "document.querySelector('.cal').appendChild(el); el.dispatchEvent(new KeyboardEvent('keydown', Object.assign({key: 'PageDown', bubbles: true, cancelable: true}, init))); el.remove(); }")
            for tag, init in (("input", {}), ("textarea", {}), ("div", {}), ("span", {"shiftKey": True})):
                cdp.js(f"({fire})('{tag}', {json.dumps(init)})", sid)
            cdp.js("document.querySelector('.cal').dispatchEvent(new KeyboardEvent('keydown', {key: 'PageDown', shiftKey: true, bubbles: true, cancelable: true}))", sid)
            time.sleep(0.3)
            self.assertEqual(self.title(cdp, sid), before, "none of those moved the period")
            self.key(cdp, sid, "PageDown")
            self.assertTrue(wait(lambda: self.title(cdp, sid) != before), "a plain Page Down still does")
    def test_one_day_is_the_tab_stop_in_each_scale_and_it_is_today(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            for name in ("month", "week", "quarter", "month"):
                self.scale(cdp, sid, name)
                self.assertEqual(self.stops(cdp, sid), ["2026-10-28"], f"{name}: one tab stop, today")
