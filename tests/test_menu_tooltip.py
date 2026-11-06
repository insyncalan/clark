"""Row 774: a tooltip never stays over an open menu (the profile menu, the Add item menu and the section grip menu), at 1400 and 900 px, light and dark, View and Edit.

Run: python3 dev/run_tests.py test_menu_tooltip
The tip is the CSS one drawn from data-tip (shell.css). It must hide when its menu opens, on pointer leave, on Esc and on blur, and
sit under every menu.
"""
import unittest

from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome

AFTER = "getComputedStyle(document.querySelector('#profile-btn'), '::after')"
ADD = "getComputedStyle(document.querySelector('#newBtn'), '::after')"
GRIP = "getComputedStyle(document.querySelector('.sec-ctl .handle'), '::after')"


class MenuTooltip(Base):
    def show(self, cdp, width, dark):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        return p

    def shown(self, p):
        return p.js(AFTER + ".content") not in ("none", "normal")

    def test_the_tip_hides_when_the_menu_opens_on_leave_on_esc_and_on_blur_and_sits_under_menus(self):
        for width in (1400, 900):
            for dark in (False, True):
                for edit in (False, True):
                    with self.subTest(width=width, dark=dark, edit=edit), chrome() as cdp:
                        p = self.show(cdp, width, dark)
                        if edit:
                            p.edit()
                        x, y, _ = p.box("#profile-btn")
                        p.mouse("mouseMoved", x, y)
                        p.until(AFTER + ".content !== 'none'", "the tip shows on hover")
                        self.assertLess(int(p.js(AFTER + ".zIndex")), 20, "under every menu")
                        p.mouse("mousePressed", x, y, buttons=1)
                        p.mouse("mouseReleased", x, y)
                        p.until("!!document.querySelector('#profile-menu')", "the menu opened")
                        self.assertFalse(self.shown(p), "no tip over the open menu while the pointer is still on the button")
                        p.key("Escape", code="Escape", vk=27)
                        p.until("!document.querySelector('#profile-menu')", "Esc closed the menu")
                        self.assertFalse(self.shown(p), "no tip after Esc, though focus came back to the button")
                        p.mouse("mouseMoved", 5, int(p.js("window.innerHeight")) - 5)           # inside the window, away from the button (a point below a short window never leaves it)
                        p.until("!document.querySelector('#profile-btn').matches(':hover')", "the pointer has left the button")      # the hover state follows the move by a frame: wait for it, not a fixed delay
                        p.js("document.querySelector('#profile-btn').blur()")
                        p.until(AFTER + ".content === 'none'", "no tip after the pointer leaves and focus goes")
                        p.mouse("mouseMoved", x, y)
                        p.until(AFTER + ".content !== 'none'", "the tip is back on hover")

    def test_the_add_item_menu_on_work_items_never_has_a_tip_over_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width, False)
                p.js("location.hash = '#work&p=ABC'")
                p.until("!!document.querySelector('#newBtn[aria-haspopup=menu]')", "the Add item button drew on Work items")
                self.assertEqual(p.js("document.querySelector('#newBtn').dataset.tip"), "Add item")
                gone = lambda: p.js(ADD + ".content") in ("none", "normal")
                x, y, _ = p.box("#newBtn")
                p.mouse("mouseMoved", x, y)
                p.until(ADD + ".content !== 'none'", "the tip shows on hover")
                self.assertLess(int(p.js(ADD + ".zIndex")), 20, "under every menu")
                p.mouse("mousePressed", x, y, buttons=1)
                p.mouse("mouseReleased", x, y)
                p.until("!!document.querySelector('#newBtnMenu')", "the menu opened")
                p.until("document.querySelector('#newBtnMenu').contains(document.activeElement)", "focus went into the menu")
                self.assertTrue(gone(), "no tip over the open Add item menu while the pointer is still on the button")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#newBtnMenu')", "Esc closed the menu")
                self.assertTrue(gone(), "no tip after Esc, though focus came back to the button")
                p.mouse("mouseMoved", 5, int(p.js("window.innerHeight")) - 5)
                p.until("!document.querySelector('#newBtn').matches(':hover')", "the pointer has left the button")
                p.js("document.querySelector('#newBtn').blur()")
                p.until(ADD + ".content === 'none'", "no tip after the pointer leaves and focus goes")
                p.mouse("mouseMoved", x, y)
                p.until(ADD + ".content !== 'none'", "the tip is back on hover")

    def test_the_section_grip_menu_never_has_a_tip_over_it(self):
        """The grip carries a native title, not a data-tip: no drawn tip may appear on it, before, during or after its menu."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width, False)
                p.edit()
                p.until("!!document.querySelector('.sec-ctl .handle')", "the grip drew in Edit")
                self.assertIsNone(p.js("document.querySelector('.sec-ctl .handle').getAttribute('data-tip')"), "the grip has no drawn tip")
                gone = lambda: p.js(GRIP + ".content") in ("none", "normal")
                p.js("document.querySelector('.sec-ctl .handle').scrollIntoView({block: 'center'})")
                x, y, _ = p.box(".sec-ctl .handle")
                p.mouse("mouseMoved", x, y)
                p.until("document.querySelector('.sec-ctl .handle').matches(':hover')", "the pointer is on the grip")
                self.assertTrue(gone(), "no drawn tip on hover")
                p.mouse("mousePressed", x, y, buttons=1)
                p.mouse("mouseReleased", x, y)
                p.until("!!document.querySelector('.sec-ctl .menu')", "the section menu opened")
                p.until("document.querySelector('.sec-ctl .menu').contains(document.activeElement)", "focus went into the menu")
                self.assertTrue(gone(), "no tip over the open section menu")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('.sec-ctl .menu')", "Esc closed the menu")
                self.assertTrue(gone(), "no tip after Esc")
                p.mouse("mouseMoved", 5, int(p.js("window.innerHeight")) - 5)
                p.until("!document.querySelector('.sec-ctl .handle').matches(':hover')", "the pointer has left the grip")
                p.js("document.querySelector('.sec-ctl .handle').blur()")
                self.assertTrue(gone(), "no tip after the pointer leaves and focus goes")


if __name__ == "__main__":
    unittest.main()
