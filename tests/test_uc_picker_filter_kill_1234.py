"""Row 1234: killing tests for four survivors of the picker table: the "is any of" button, the pressed state of the two Match buttons, the sticky header row and its background.

Run: python3 dev/run_tests.py test_uc_picker_filter_kill_1234
Same page, store and data as test_uc_picker_table (two use cases on the dashboard, two more that are not on it). Widths 1400 and 900 only.
"""
import json
import unittest

from _demo import USER
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

Q = "document.querySelector('form.picker')"
ROWS = "document.querySelectorAll('form.picker tbody tr').length"
IS = ".pkt-panel [data-not=\"0\"]"
NOT = ".pkt-panel [data-not=\"1\"]"


class Kill(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3,
                                    "headline": "No login for the smallest suppliers", "client_visible": 0, "source": "demo"})
            st.create("use_cases", {"project": "ABC", "title": "Month end close", "status": "On track", "ref": "2.1", "sort_order": 4,
                                    "headline": "Done in two days", "client_visible": 0, "source": "demo"})

    def edit(self, cdp, width=1400):
        p = self.show(cdp, width)
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit shows the status buttons")
        return p

    def click(self, p, selector):
        p.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)

    def show_picker(self, p):
        self.click(p, "[data-uc-back]")
        p.until("!!" + Q, "the picker")

    def pressed(self, p, sel):
        return p.js("document.querySelector(%s).getAttribute('aria-pressed')" % json.dumps(sel))

    def test_is_any_of_brings_back_the_match_after_is_not_any_of(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.show_picker(p)
                p.js("document.querySelector('[data-filter]').click()")
                p.until("!!document.querySelector('.pkt-panel')", "the panel")
                p.js("document.querySelector('.pkt-panel [data-field=status]').click()")
                p.js("document.querySelector('.pkt-panel input[value=\"High risk\"]').click()")
                p.until(ROWS + " === 1", "is any of High risk shows one row")
                self.assertEqual(p.js("document.querySelector('form.picker tbody tr').textContent.includes('Supplier portal')"), True)
                self.assertEqual((self.pressed(p, IS), self.pressed(p, NOT)), ("true", "false"), "is any of is the pressed one at the start")
                p.js("document.querySelector('%s').click()" % NOT)
                p.until("document.querySelector('form.picker tbody tr').textContent.includes('Month end close')", "is not any of shows the other row")
                self.assertEqual(p.js(ROWS), 1)
                self.assertEqual((self.pressed(p, IS), self.pressed(p, NOT)), ("false", "true"), "pressed state flips with the click on is not any of")
                p.js("document.querySelector('%s').click()" % IS)
                p.until("document.querySelector('form.picker tbody tr').textContent.includes('Supplier portal')", "is any of brings the first row back")
                self.assertEqual(p.js(ROWS), 1)
                self.assertEqual((self.pressed(p, IS), self.pressed(p, NOT)), ("true", "false"), "pressed state flips back with the click on is any of")

    def test_the_header_row_is_sticky_and_painted(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.show_picker(p)
                th = "document.querySelector('form.picker .pkt-table thead th')"
                self.assertEqual(p.js("getComputedStyle(%s).position" % th), "sticky")
                self.assertEqual(p.js("getComputedStyle(%s).top" % th), "0px")
                # the paint is the page surface colour: the rows slide under the header and must not show through
                want = p.js("(() => { const e = document.createElement('i'); e.style.background = 'var(--surface)'; document.body.append(e); const c = getComputedStyle(e).backgroundColor; e.remove(); return c; })()")
                self.assertNotEqual(want, "rgba(0, 0, 0, 0)", "the surface token resolves to a colour")
                self.assertEqual(p.js("getComputedStyle(%s).backgroundColor" % th), want)


if __name__ == "__main__":
    unittest.main()
