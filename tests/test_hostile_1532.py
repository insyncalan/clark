"""Hostile tests, Row 1532: the Classic Milestones timeline hides its bar but must still scroll by real keys, wheel and Earlier/Later; Cards keeps its bar."""
import unittest

import test_server  # noqa: F401  (marks this file as a browser test for the tiers)

from test_ms_timeline_classic_1315 import Base

LEFT = "document.querySelector('.mv-wrap').scrollLeft"
ZOOM = "document.querySelector('[data-grip]').focus()"
FOCUS = "(() => { const w = document.querySelector('.mv-wrap'); w.focus(); w.scrollLeft = 0; return w.scrollWidth > w.clientWidth; })()"


def widen(cdp, sid):
    import time
    cdp.js(ZOOM, sid)
    for kind in ("rawKeyDown", "keyUp"):
        cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "End", "code": "End", "windowsVirtualKeyCode": 35}, sid)
    time.sleep(0.5)


class Classic(Base, unittest.TestCase):
    def test_arrow_keys_move_the_strip(self):
        for cdp, sid, w in self.every():
            widen(cdp, sid)
            self.assertTrue(cdp.js(FOCUS, sid), f'zoomed strip is wider at {w}')
            before = cdp.js(LEFT, sid)
            for kind in ("rawKeyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}, sid)
            import time; time.sleep(0.6)
            self.assertGreater(cdp.js(LEFT, sid), before, f"ArrowRight at {w}")

    def test_wheel_sideways_and_later_button_move_the_strip(self):
        for cdp, sid, w in self.every():
            widen(cdp, sid)
            self.assertTrue(cdp.js(FOCUS, sid), f'zoomed strip is wider at {w}')
            b = cdp.js("(() => { const r = document.querySelector('.mv-wrap').getBoundingClientRect(); return [r.left + 100, r.top + 40]; })()", sid)
            before = cdp.js(LEFT, sid)
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": b[0], "y": b[1], "deltaX": 120, "deltaY": 0}, sid)
            import time; time.sleep(0.5)
            self.assertGreater(cdp.js(LEFT, sid), before, f"wheel at {w}")
            before = cdp.js(LEFT, sid)
            cdp.js("document.querySelector('[data-mv=\"1\"]').click()", sid)
            time.sleep(0.8)
            self.assertGreater(cdp.js(LEFT, sid), before, f"Later at {w}")
            before = cdp.js(LEFT, sid)
            cdp.js("document.querySelector('[data-mv=\"-1\"]').click()", sid)
            time.sleep(0.8)
            self.assertLess(cdp.js(LEFT, sid), before, f"Earlier at {w}")

    def test_no_bar_on_any_scroller_inside_the_timeline_and_no_visible_bar_pseudo(self):
        probe = """(() => [...document.querySelectorAll('.mv, .mv *')].filter((e) => { const c = getComputedStyle(e); return /auto|scroll/.test(c.overflowX) && e.scrollWidth > e.clientWidth && c.scrollbarWidth !== 'none'; }).map((e) => e.className)).call ? 1 : 1)()"""
        probe = """[...document.querySelectorAll('.mv, .mv *')].filter((e) => { const c = getComputedStyle(e); return /auto|scroll/.test(c.overflowX) && e.scrollWidth > e.clientWidth && c.scrollbarWidth !== 'none'; }).map((e) => e.className)"""
        for cdp, sid, w in self.every():
            self.assertEqual(cdp.js(probe, sid), [], f"width {w}")

    def test_hidden_bar_is_not_replaced_by_visible_overflow_or_clipping(self):
        for cdp, sid, w in self.every():
            r = cdp.js("(() => { const e = document.querySelector('.mv-wrap'), c = getComputedStyle(e), r = e.getBoundingClientRect(); return [c.overflowX, c.overflowY, r.right <= innerWidth + 1, e.scrollWidth - e.clientWidth]; })()", sid)
            self.assertEqual(r[:2], ["auto", "hidden"], w)
            self.assertTrue(r[2], f"wrap fits the viewport at {w}")


class Cards(Base, unittest.TestCase):
    THEME = "cards"

    def test_cards_bar_is_not_hidden_by_display_none_either(self):
        for cdp, sid, w in self.every():
            self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('.mv-wrap'), '::-webkit-scrollbar').display", sid), "none", w)


if __name__ == "__main__":
    unittest.main()
