"""Row 1075, mutation audit: tests that kill the changes to the five-second message that test_toast_five_seconds let through.
Run: python3 dev/run_tests.py test_toast_five_seconds_mutants

A problem message has no bar and stays until Close; the time already spent is kept while the pointer holds the message; a held message
stays held until every hold (pointer, focus) is let go; the bar stands still while focus is inside the message. The real page and a real
server over the fictional demo report, headless Chrome.
"""
import time
import unittest

from test_report_editor import Base  # noqa: E402
from test_server import chrome  # noqa: E402
import test_toast_five_seconds as first  # noqa: E402

BAR, GONE = ".toast .toast-bar", "!document.querySelector('.toast')"


class Mutants(Base):
    make_toast = first.ToastFiveSeconds.make_toast
    motion = first.ToastFiveSeconds.motion
    at = first.ToastFiveSeconds.at

    def test_a_problem_message_has_no_bar_and_stays_until_it_is_closed(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.motion(cdp, p, "no-preference")
            p.edit()
            p.js("document.getElementById('clark-boot').textContent = JSON.stringify({token: 'from an earlier run'})")
            p.menu("ABC-S-002", "up")
            p.until("!!document.querySelector('.toast.problem')", "a problem message")
            self.t0 = time.monotonic()
            self.assertFalse(p.js(f"!!document.querySelector('{BAR}')"), "a problem has no bar")
            self.at(6.5)
            self.assertTrue(p.js("!!document.querySelector('.toast.problem')"), "still there after 6 seconds: it waits for Close")

    def test_the_time_already_gone_is_kept_while_the_pointer_holds_the_message(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.motion(cdp, p, "no-preference")
            self.make_toast(p)
            x, y, _ = p.box(".toast")
            self.at(3.5)
            p.mouse("mouseMoved", x, y)
            self.at(6.5)
            self.assertTrue(p.js("!!document.querySelector('.toast')"), "held")
            p.mouse("mouseMoved", 5, 5)
            time.sleep(3.2)
            self.assertTrue(p.js(GONE), "about 1.5 seconds were left, so it is gone 3 seconds after the pointer left, not 5")

    def test_a_message_held_by_the_pointer_and_by_focus_waits_for_both(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
            self.motion(cdp, p, "no-preference")
            self.make_toast(p)
            x, y, _ = p.box(".toast")
            p.mouse("mouseMoved", x, y)
            p.js("document.querySelector('.toast [data-undo]').focus()")
            self.at(1.0)
            p.mouse("mouseMoved", 5, 5)                    # the pointer leaves; focus still holds
            self.at(8.0)
            self.assertTrue(p.js("!!document.querySelector('.toast')"), "focus alone still holds it")
            p.js("document.activeElement.blur()")
            p.until(GONE, "it goes once focus has left too", 7)

    def test_the_bar_stands_still_while_focus_is_inside_the_message(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
            self.motion(cdp, p, "no-preference")
            self.make_toast(p)
            p.js("document.querySelector('.toast [data-undo]').focus()")
            time.sleep(0.5)
            w1 = p.js(f"document.querySelector('{BAR}').getBoundingClientRect().width")
            time.sleep(1.0)
            w2 = p.js(f"document.querySelector('{BAR}').getBoundingClientRect().width")
            self.assertEqual(w1, w2, "the bar stands still with focus on Undo")


if __name__ == "__main__":
    unittest.main()
