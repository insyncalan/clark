"""Hardening of the one panel every cell picker opens in (Pop.jsx) and the date panel's keys: what Esc, Tab, a click away, a click inside,
a scroll and a resize do. Browser tests (set CLARK_CHROME to the browser's path); the rig is the one of test_inline_edits.
Run: python3 dev/run_tests.py test_pop_focus
"""
import json
import unittest

import test_inline_edits as ie
from test_inline_edits import chrome, click, key, wait

CELL = "[data-cell='TUL-A-001:due']"
POP = "document.querySelectorAll('[data-pop]')"


class PopFocus(unittest.TestCase):
    setUp, read, row, steps, open_page, until, focused = (ie.Live.setUp, ie.Live.read, ie.Live.row, ie.Live.steps, ie.Live.open_page,
                                                          ie.Live.until, ie.Live.focused)

    def opened(self, cdp, width=1400, height=None):
        sid = self.open_page(cdp, width)
        if height:
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, sid)
        click(cdp, sid, CELL)
        self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-g')", "the date panel opened")
        return sid

    def test_keys_in_the_panel_never_reach_the_page_behind(self):
        # Esc is the panel's own (the peek's Esc must not also fire) and Enter is meant for the panel (the row behind must not take it).
        with chrome() as cdp:
            sid = self.opened(cdp)
            cdp.js("window.__seen = []; document.addEventListener('keydown', e => window.__seen.push(e.key));", sid)
            cdp.js("document.querySelector('[data-pop] .cp-q button').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}))", sid)
            self.assertEqual(cdp.js("window.__seen", sid), [], "Enter in the panel stops at the panel")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, f"{POP}.length === 0", "Esc closes it")
            self.assertEqual(cdp.js("window.__seen", sid), [], "Esc in the panel stops at the panel")
            self.assertEqual(self.focused(cdp, sid), "TUL-A-001:due", "focus is back on the date control")

    def test_a_click_inside_the_panel_keeps_it_open_and_does_not_open_the_peek(self):
        with chrome() as cdp:
            sid = self.opened(cdp)
            n, before = len(self.sent), self.steps()
            click(cdp, sid, "[data-pop] .cp-t")
            click(cdp, sid, "[data-pop] [data-month='1']")
            self.until(cdp, sid, "document.querySelector('[data-pop] .cp-t').textContent === 'December 2026'", "the month button worked")
            self.assertEqual(cdp.js(f"{POP}.length", sid), 1, "still open after clicks inside it")
            self.assertNotIn("item=", cdp.js("location.hash", sid), "the click did not reach the row behind")
            self.assertEqual((len(self.sent), self.steps()), (n, before))

    def test_a_click_away_on_the_page_closes_and_focus_leaves_the_panel(self):
        with chrome() as cdp:
            sid = self.opened(cdp)
            click(cdp, sid, "h1")
            self.until(cdp, sid, f"{POP}.length === 0", "a click outside closes it")
            self.assertEqual(cdp.js("!!document.activeElement && !!document.activeElement.closest('[data-pop]')", sid), False)
            self.assertEqual(self.row("actions", "TUL-A-001")["due_date"], "2026-11-02")

    def test_a_scroll_outside_moves_the_panel_with_its_control_and_one_inside_does_not(self):
        with chrome() as cdp:
            sid = self.opened(cdp, height=500)
            cdp.js("document.querySelector('[data-pop]').style.top = '3px'; document.querySelector('[data-pop] .cp-g').dispatchEvent(new Event('scroll'))", sid)
            self.assertEqual(cdp.js("document.querySelector('[data-pop]').style.top", sid), "3px", "a scroll inside leaves it where it is")
            cdp.js("document.querySelector('[data-pop]').style.top = '3px'; document.body.dispatchEvent(new Event('scroll'))", sid)
            self.assertNotEqual(cdp.js("document.querySelector('[data-pop]').style.top", sid), "3px", "a scroll elsewhere puts it back under its control")
            self.assertEqual(cdp.js(f"{POP}.length", sid), 1)

    def test_a_press_on_the_control_that_opened_it_is_not_a_click_away(self):
        with chrome() as cdp:
            sid = self.opened(cdp)
            cdp.js("window.__box = document.querySelector('[data-pop]'); document.addEventListener('pointerdown', () => window.__seen = window.__box.isConnected, false)", sid)
            click(cdp, sid, CELL)
            self.assertTrue(cdp.js("window.__seen", sid), "the press reached the page")

    def test_the_panel_is_pulled_in_from_the_right_edge_for_a_control_at_it(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            cdp.js("""(() => { const c = document.querySelector(%s); c.style.cssText = 'position:fixed;left:calc(100vw - 30px);top:100px'; c.focus(); })()""" % json.dumps(CELL), sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-g')", "the date panel opened")
            self.assertTrue(cdp.js("document.querySelector('[data-pop]').getBoundingClientRect().right <= innerWidth - 8 + 1", sid), "whole at the right edge")

    def test_a_resize_closes_the_panel(self):
        with chrome() as cdp:
            sid = self.opened(cdp)
            cdp.js("window.dispatchEvent(new Event('resize'))", sid)
            self.until(cdp, sid, f"{POP}.length === 0", "a resize closes it")
            self.assertEqual(self.row("actions", "TUL-A-001")["due_date"], "2026-11-02")

    def test_the_panel_stays_whole_in_a_short_window(self):
        with chrome() as cdp:
            for width, height in ((1400, 640), (1400, 560)):
                sid = self.opened(cdp, width=width, height=height)
                box = cdp.js("(() => { const b = document.querySelector('[data-pop]').getBoundingClientRect(); return [b.top >= 8, b.bottom <= innerHeight - 8 + 1, b.left >= 8, b.right <= innerWidth - 8 + 1]; })()", sid)
                self.assertEqual(box, [True, True, True, True], f"whole in a {width} by {height} window")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, f"{POP}.length === 0", "closed")

    def test_the_panel_opens_above_a_control_near_the_bottom_of_the_window(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            cdp.js("window.__resized = 0; window.addEventListener('resize', () => { window.__resized += 1; })", sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 700, "deviceScaleFactor": 1, "mobile": False}, sid)
            # The window's resize event arrives after the call returns, and a resize closes the panel; wait for it before opening
            self.until(cdp, sid, "window.__resized > 0 && innerHeight === 700", "the window finished resizing")
            cell = cdp.js("""(() => { const c = [...document.querySelectorAll('[data-cell$=":due"]')].pop(); c.scrollIntoView({block: 'end'}); c.focus();
                window.__c = c; return c.getBoundingClientRect().bottom > innerHeight - 100; })()""", sid)
            self.assertTrue(cell, "the control is near the bottom of the window")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-g')", "the date panel opened")
            self.assertTrue(cdp.js("document.querySelector('[data-pop]').getBoundingClientRect().bottom <= window.__c.getBoundingClientRect().top", sid),
                            "no room below, so it opens above the control")

    def test_tab_makes_the_closing_panel_inert_at_once_and_keeps_the_value(self):
        with chrome() as cdp:
            sid = self.opened(cdp)
            cdp.js("window.__box = document.querySelector('[data-pop]')", sid)
            n = len(self.sent)
            key(cdp, sid, "Tab")
            self.until(cdp, sid, f"{POP}.length === 0", "Tab closes it")
            self.assertTrue(cdp.js("window.__box.inert", sid), "the closing panel is inert, so the browser's own Tab step cannot land in it")
            self.assertEqual(len(self.sent), n)
            self.assertEqual(self.row("actions", "TUL-A-001")["due_date"], "2026-11-02")


if __name__ == "__main__":
    unittest.main()
