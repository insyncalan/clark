"""Row 758: the demo-remove confirm is a proper dialog that starts BELOW the top bar, never over it, at 1400, 901, 900 and 800 px, light and dark.

Run: python3 dev/run_tests.py test_demo_dialog_place
"""
import unittest

from test_demo_banner import DemoLine
from test_page import navigate
from test_server import chrome, wait

KEYS = {"Escape": 27, "Tab": 9}


def key(cdp, sid, name, shift=False):
    common = {"key": name, "code": name, "windowsVirtualKeyCode": KEYS[name], **({"modifiers": 8} if shift else {})}
    cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common}, sid)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


class DemoDialogPlace(unittest.TestCase):
    setUp = DemoLine.setUp

    def show(self, cdp, sid):
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#demo-remove')", sid), 30), "the banner")
        cdp.js("document.querySelector('#demo-remove').focus(); document.querySelector('#demo-remove').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#demo-confirm')", sid), 30), "the dialog")

    def test_the_dialog_starts_below_the_top_bar_at_every_width_in_light_and_dark(self):
        for theme in ("light", "dark"):
            for w in (1400, 901, 900, 800):
                with self.subTest(theme=theme, width=w), chrome() as cdp:
                    sid = navigate(cdp, self.s.port, "#dashboard")
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.js(f"document.documentElement.setAttribute('data-theme', '{theme}')", sid)
                    self.show(cdp, sid)
                    bar, box = cdp.js("(() => { const a = document.querySelector('.top').getBoundingClientRect(), b = document.querySelector('#demo-confirm').getBoundingClientRect(); return [[a.top, a.bottom], [b.top, b.bottom, b.left, b.right]]; })()", sid)
                    self.assertGreaterEqual(box[0], bar[1], f"the dialog top {box[0]} is under the bar bottom {bar[1]}")
                    self.assertLessEqual(box[1], 900, "the dialog ends inside the window")
                    self.assertGreaterEqual(box[2], 0)
                    self.assertLessEqual(box[3], w)

    def focused(self, cdp, sid, want, what=""):
        """Wait (10 s at most) for the focus to be on `want`: the dialog moves it after it is drawn, and a key lands a moment later under load."""
        ok = wait(lambda: cdp.js("document.activeElement && document.activeElement.id", sid) == want, 10)
        self.assertTrue(ok, f"{what or 'focus'}: wanted {want}, it is on {cdp.js('document.activeElement && document.activeElement.id', sid)}")

    def test_focus_goes_in_esc_closes_only_the_dialog_tab_stays_inside_and_focus_returns_to_the_button(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#dashboard")
            self.show(cdp, sid)
            box = cdp.js("(() => { const d = document.querySelector('#demo-confirm'); return [d.getAttribute('role'), d.getAttribute('aria-modal'), document.getElementById(d.getAttribute('aria-labelledby')).innerText]; })()", sid)
            self.assertEqual(box, ["dialog", "true", "Remove demo data?"])
            self.focused(cdp, sid, "demo-cancel")
            self.assertTrue(cdp.js("document.querySelector('#main').hasAttribute('inert') && document.querySelector('.top').hasAttribute('inert')", sid), "the page behind is inert")
            key(cdp, sid, "Tab")
            self.focused(cdp, sid, "demo-go")
            key(cdp, sid, "Tab")
            self.focused(cdp, sid, "demo-cancel", "Tab wraps inside")
            key(cdp, sid, "Tab", shift=True)
            self.focused(cdp, sid, "demo-go", "Shift+Tab wraps inside")
            hash_ = cdp.js("location.hash", sid)
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: cdp.js("!document.querySelector('#demo-confirm')", sid), 10), "Esc closed the dialog")
            self.assertEqual(cdp.js("location.hash", sid), hash_, "and only the dialog")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.id === 'demo-remove'", sid), 10), "focus is back on the button")
            self.assertFalse(cdp.js("document.querySelector('#main').hasAttribute('inert')", sid))


if __name__ == "__main__":
    unittest.main()
