"""Row 774: a tooltip never stays over the open PROFILE menu (the other menus are a follow-up row), at 1400 and 900 px, light and dark, View and Edit.

Run: python3 dev/run_tests.py test_menu_tooltip
The tip is the CSS one drawn from data-tip (shell.css). It must hide when its menu opens, on pointer leave, on Esc and on blur, and
sit under every menu.
"""
import unittest

from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome

AFTER = "getComputedStyle(document.querySelector('#profile-btn'), '::after')"


class MenuTooltip(Base):
    def show(self, cdp, width, dark):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        return p

    def stays_absent(self, p, what, sample=None):
        """The tip is absent now AND for the next three frames: sampled in the page on each frame into window.__tipSeen (null while it runs),
        then read back with ordinary reads (a Promise handed to p.js is NOT awaited and would come back as {}). Fails unless the value IS False."""
        p.js("window.__tipSeen = null; (function () { var n = 0, any = false; (function f() { any = any || " + (sample or AFTER + ".content !== 'none'") + "; "
             "if (++n < 4) requestAnimationFrame(f); else window.__tipSeen = any; })(); })()")
        p.until("window.__tipSeen !== null", "the four frames were sampled")
        seen = p.js("window.__tipSeen")
        self.assertIs(seen, False, what)

    def point(self, p, x, y, hover, what):
        """Move the pointer and wait until the button's :hover state is what the move should make it (it follows the move by a frame)."""
        p.mouse("mouseMoved", x, y)
        p.until("document.querySelector('#profile-btn').matches(':hover') === " + ("true" if hover else "false"), what)

    def test_the_tip_hides_when_the_menu_opens_on_leave_on_esc_and_on_blur_and_sits_under_menus(self):
        for width in (1400, 900):
            for dark in (False, True):
                for edit in (False, True):
                    with self.subTest(width=width, dark=dark, edit=edit), chrome() as cdp:
                        p = self.show(cdp, width, dark)
                        if edit:
                            p.edit()
                        x, y, _ = p.box("#profile-btn")
                        self.point(p, x, y, True, "the pointer is on the button")
                        p.until(AFTER + ".content !== 'none'", "the tip shows on hover")
                        self.assertLess(int(p.js(AFTER + ".zIndex")), 20, "under every menu")
                        p.mouse("mousePressed", x, y, buttons=1)
                        p.mouse("mouseReleased", x, y)
                        p.until("!!document.querySelector('#profile-menu') && document.querySelector('#profile-btn').getAttribute('aria-expanded') === 'true'", "the menu opened")
                        p.until(AFTER + ".content === 'none'", "the tip hid when the menu opened")
                        self.stays_absent(p, "no tip over the open menu while the pointer is still on the button")
                        p.key("Escape", code="Escape", vk=27)
                        p.until("!document.querySelector('#profile-menu') && document.querySelector('#profile-btn').getAttribute('aria-expanded') !== 'true'", "Esc closed the menu")
                        p.until("document.documentElement.hasAttribute('data-tip-off')", "Esc switched the tip off")
                        p.until(AFTER + ".content === 'none'", "the tip is off after Esc")
                        self.stays_absent(p, "no tip after Esc, though focus came back to the button")
                        # inside the window, away from the button (a point below a short window never leaves it)
                        self.point(p, 5, int(p.js("window.innerHeight")) - 5, False, "the pointer has left the button")
                        p.js("document.querySelector('#profile-btn').blur()")
                        p.until("document.activeElement !== document.querySelector('#profile-btn')", "focus left the button")
                        p.until(AFTER + ".content === 'none'", "no tip after the pointer leaves and focus goes")
                        self.stays_absent(p, "no tip stays away after the pointer left and focus went")
                        self.point(p, x, y, True, "the pointer is back on the button")
                        p.until(AFTER + ".content !== 'none'", "the tip is back on hover")


if __name__ == "__main__":
    unittest.main()
