"""Settings at 900 px by keyboard: a menu that Tab leaves, Esc on the People paste box. Run: python3 dev/run_tests.py test_settings_keys_900

What is asserted (width 900 only): Tab or Shift+Tab out of an open row menu on Projects closes it and goes on from the menu's own button
(not back to the top of the page); Esc in the People paste box closes the box and puts the focus back on the Paste from Excel button.
Chrome is required: these tests fail, never skip, without it.
"""
import time
import unittest

import test_settings_head as H
from test_server import chrome

SHIFT = 8
WHERE = "(function(){var a=document.activeElement; return a ? (a.className || '') + '|' + (a.id || '') + '|' + (a.getAttribute('aria-label') || '') : 'none'; })()"


class Keys(H.Head):
    def open_row_menu(self, p):
        p.js("document.querySelector('[data-row-menu]').focus()")
        p.key("Enter", code="Enter", vk=13)
        p.until("!!document.querySelector('[role=menu]')", "the row menu opened")

    def test_C_tab_out_of_a_row_menu_closes_it_and_goes_on_from_its_button(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 900, "light", "projects")
            p.until("!!document.querySelector('[data-row-menu]')", "the project rows drew")
            self.open_row_menu(p)
            p.key("Tab", code="Tab", vk=9)
            time.sleep(0.5)
            self.assertEqual(p.js("!!document.querySelector('[role=menu]')"), False, "Tab closes the menu")
            self.assertNotIn("skip", p.js(WHERE), "Tab does not throw the focus back to the top of the page")
            p.js("document.querySelector('[data-row-menu]').focus()")
            self.open_row_menu(p)
            for kind in ("keyDown", "keyUp"):
                p.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9, "modifiers": SHIFT}, p.sid)
            time.sleep(0.5)
            self.assertEqual(p.js("document.activeElement.hasAttribute('data-edit')"), True, "Shift+Tab goes to the button before the menu's own (Edit), not to the end of the page")

    def test_C_esc_closes_the_people_paste_box_and_returns_to_its_button(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 900, "light", "people")
            p.js("document.getElementById('ppPasteBtn').focus()")
            p.key("Enter", code="Enter", vk=13)
            p.until("document.activeElement && document.activeElement.id === 'ppText'", "the paste box took the focus")
            p.key("Escape", code="Escape", vk=27)
            time.sleep(0.4)
            self.assertEqual(p.js("document.getElementById('ppPaste').hidden"), True, "Esc closes the paste box")
            self.assertEqual(p.js("document.activeElement.id"), "ppPasteBtn", "the focus is back on the button that opened it")
            self.assertEqual(p.js("document.getElementById('ppPasteBtn').getAttribute('aria-expanded')"), "false")


if __name__ == "__main__":
    unittest.main()
