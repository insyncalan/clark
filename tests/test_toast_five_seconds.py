"""Row 1075: a message at the foot of the page goes after 5 seconds, with a bar that shrinks to show the time left; the timer waits while
the pointer is over the message or focus is in it; with reduced motion there is no bar; Ctrl+Z still undoes the change after the message
has gone. The real page and a real server over the fictional demo report (the harness of tests/test_report_editor.py), headless Chrome.

Run: python3 dev/run_tests.py test_toast_five_seconds
"""
import time
import unittest

from test_report_editor import Base  # noqa: E402
from test_server import chrome  # noqa: E402

CTRL = 2                                         # Input.dispatchKeyEvent modifiers
BAR = ".toast .toast-bar"
GONE = "!document.querySelector('.toast')"
SECTIONS = "document.querySelectorAll('.secs > .sec[data-type=\"gantt\"]').length"


class ToastFiveSeconds(Base):
    def make_toast(self, p):
        """Add a Gantt section in Edit: a message with Undo appears. Returns when it is on screen."""
        p.edit()
        p.js("document.querySelector('[data-id=\"ABC-S-003\"] [data-options]').click()")
        p.until("!!document.querySelector('[data-id=\"ABC-S-003\"] .menu')", "the menu opened")
        p.js("document.querySelector('[data-id=\"ABC-S-003\"] [data-act=add]').click()")
        p.until("!!document.querySelector('[data-template=gantt] input')", "Add a section offers Gantt")
        p.js("document.querySelector('[data-template=gantt] input').click()")
        p.js("document.querySelector('button[data-place]').click()")
        p.until(f"{SECTIONS} === 1", "the Gantt section is drawn")
        p.until("!!document.querySelector('.toast [data-undo]')", "the message offers Undo")
        self.t0 = time.monotonic()

    def motion(self, cdp, p, value):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": value}]}, p.sid)

    def at(self, seconds):
        wait = self.t0 + seconds - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def test_the_message_is_still_there_at_4_seconds_and_gone_by_6_and_the_bar_shrinks(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.motion(cdp, p, "no-preference")
            self.make_toast(p)
            self.assertTrue(p.js(f"!!document.querySelector('{BAR}') && getComputedStyle(document.querySelector('{BAR}')).display !== 'none'"), "the bar is drawn")
            first = p.js(f"document.querySelector('{BAR}').getBoundingClientRect().width")
            self.assertGreater(first, 20, "the bar starts wide")
            self.at(2.5)
            half = p.js(f"document.querySelector('{BAR}').getBoundingClientRect().width")
            self.assertLess(half, first * 0.75, "the bar has shrunk by 2.5 seconds")
            self.assertGreater(half, first * 0.2, "and is not yet gone")
            self.at(4.0)
            self.assertTrue(p.js("!!document.querySelector('.toast')"), "still there at 4 seconds")
            self.at(6.2)
            self.assertTrue(p.js(GONE), "gone by 6 seconds, not after 20")

    def test_ctrl_z_still_undoes_after_the_message_has_gone(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.make_toast(p)
            p.js("document.activeElement && document.activeElement.blur()")
            p.until(GONE, "the message went by itself", 9)
            self.assertEqual(p.js(SECTIONS), 1)
            p.key("z", CTRL, code="KeyZ", vk=90)
            p.until(f"{SECTIONS} === 0", "Ctrl+Z took the added section back")

    def test_with_reduced_motion_there_is_no_bar_but_the_message_still_goes_after_5_seconds(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.motion(cdp, p, "reduce")
            self.make_toast(p)
            self.assertTrue(p.js(f"!document.querySelector('{BAR}') || getComputedStyle(document.querySelector('{BAR}')).display === 'none'"), "no bar")
            self.at(4.0)
            self.assertTrue(p.js("!!document.querySelector('.toast')"), "still there at 4 seconds")
            p.until(GONE, "gone by itself", 4)

    def test_the_timer_waits_while_the_pointer_is_over_the_message_and_goes_on_when_it_leaves(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.motion(cdp, p, "no-preference")
            self.make_toast(p)
            x, y, _ = p.box(".toast")
            p.mouse("mouseMoved", x, y)
            self.at(1.0)
            p.mouse("mouseMoved", x + 1, y)
            self.at(8.0)
            self.assertTrue(p.js("!!document.querySelector('.toast')"), "still there at 8 seconds while the pointer rests on it")
            w1 = p.js(f"document.querySelector('{BAR}').getBoundingClientRect().width")
            time.sleep(0.6)
            w2 = p.js(f"document.querySelector('{BAR}').getBoundingClientRect().width")
            self.assertEqual(w1, w2, "the bar stands still too")
            p.mouse("mouseMoved", 5, 5)
            time.sleep(2.0)
            self.assertTrue(p.js("!!document.querySelector('.toast')"), "about 4 seconds were left, so it is still there 2 seconds after the pointer left")
            p.until(GONE, "then it goes", 6)

    def test_the_timer_waits_while_focus_is_inside_the_message(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.make_toast(p)
            p.js("document.querySelector('.toast [data-undo]').focus()")
            self.at(7.5)
            self.assertTrue(p.js("!!document.querySelector('.toast')"), "still there at 7.5 seconds with focus on Undo")
            p.js("document.activeElement.blur()")
            p.until(GONE, "it goes once focus has left", 6)


if __name__ == "__main__":
    unittest.main()
