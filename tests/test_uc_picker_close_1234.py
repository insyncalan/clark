"""Row 1234 (A, tests only): the add-a-use-case picker closes on Esc (focus goes back to the button that opened it) and on a click outside it.

Run: python3 dev/run_tests.py test_uc_picker_close_1234
Same page, store and data as test_uc_picker_table. Widths 1400 and 900 only.
"""
import unittest

from test_uc_picker_table import Q, tearDownModule
import test_uc_picker_table as _test_uc_picker_table
from test_server import chrome

OPENER = "document.activeElement === document.querySelector('[data-uc-back]')"
BEHIND = "document.querySelector('#main').inert"


class Close(_test_uc_picker_table.Table):
    def opened(self, p):
        self.show_picker(p)
        p.until("document.activeElement === document.querySelector('form.picker input[type=search]')", "focus in the search")
        self.assertEqual(p.js(BEHIND), True, "the page behind is inert while the picker is open")

    def closed(self, p, how, back=True):
        p.until("!" + Q, how + " closed the picker")
        if back:
            p.until(OPENER, "focus went back to the Add a use case button")
        self.assertEqual(p.js(BEHIND), False, "the page is live again")
        self.assertEqual(self.store.read("use_cases", "ABC") and len([u for u in self.store.read("use_cases", "ABC") if u["client_visible"]]), 2, "nothing was added")

    def test_esc_closes_the_picker_and_gives_focus_back(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.opened(p)
                p.key("Escape", code="Escape", vk=27)
                self.closed(p, "Esc")

    def test_a_click_outside_closes_the_picker(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.opened(p)
                y = p.js("window.innerHeight") - 4
                self.assertEqual(p.js("document.elementFromPoint(4, %d).classList.contains('ad-scrim')" % y), True, "the point is on the backdrop, outside the box")
                p.mouse("mouseMoved", 4, y)
                p.mouse("mousePressed", 4, y, 1)
                p.mouse("mouseReleased", 4, y)
                self.closed(p, "a click outside", back=False)
                # the ticket names no place for focus after a click (the pointer-down closes the box, then the click's own focus step runs): focus is not pinned here

    def test_a_click_inside_the_picker_keeps_it_open(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.opened(p)
                self.click(p, "form.picker h2")
                self.assertEqual(p.js("!!" + Q), True, "a click on the box does not close it")


if __name__ == "__main__":
    unittest.main()
