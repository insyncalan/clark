"""Row 1234: killing tests for the picker table (components/PickerTable.jsx): the tick box, the disabled buttons, Cancel and the Open steps column.

Run: python3 dev/run_tests.py test_uc_picker_table_kill_1234
Same page, store and data as test_uc_dashboard_edit (two use cases on the dashboard, two more that are not on it). Widths 1400 and 900 only.
"""
import json
import unittest

from _demo import USER
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

Q = "document.querySelector('form.picker')"
ROWS = "document.querySelectorAll('form.picker tbody tr').length"
RESULT = "document.querySelector('form.picker [data-result]').textContent"


class Kill(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            self.uc3 = st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3,
                                               "headline": "No login for the smallest suppliers", "client_visible": 0, "source": "demo"})
            self.uc4 = st.create("use_cases", {"project": "ABC", "title": "Month end close", "status": "On track", "ref": "2.1", "sort_order": 4,
                                               "headline": "Done in two days", "client_visible": 0, "source": "demo"})
            for status in ("Open", "Closed"):
                st.create("actions", {"project": "ABC", "description": "Step " + status, "raised": "2026-10-01", "status": status, "use_case": self.uc3, "source": "demo"})

    def edit(self, cdp, width=1400):
        p = self.show(cdp, width)
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit shows the status buttons")
        return p

    def row(self, uc):
        return self.store.read("use_cases", ref=uc)

    def click(self, p, selector):
        p.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)

    def show_picker(self, p):
        self.click(p, "[data-uc-back]")
        p.until("!!" + Q, "the picker")

    def pick_value(self, p, field, value):
        p.js("document.querySelector('.pkt-panel [data-field=%s]').click()" % field)
        p.js("document.querySelector('.pkt-panel input[value=\"%s\"]').click()" % value)

    def test_open_steps_and_work_items_columns_show_their_own_counts(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.show_picker(p)
                cells = "[...document.querySelectorAll('form.picker tbody tr[data-id=\"%s\"] td')].map(td => td.textContent)" % self.uc3
                self.assertEqual(p.js(cells)[6:8], ["1", "2"], "one open step of two work items")

    def test_a_click_on_the_tick_box_ticks_once(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.show_picker(p)
                sel = "form.picker tbody tr[data-id=\"%s\"] input" % self.uc3
                self.click(p, sel)
                p.until("document.querySelector(%s).checked" % json.dumps(sel), "the box ticked")
                self.assertEqual(p.js("document.querySelector('form.picker button[type=submit]').textContent"), "Add 1")
                self.click(p, sel)
                p.until("!document.querySelector(%s).checked" % json.dumps(sel), "the box unticked")
                self.assertEqual(p.js("document.querySelector('form.picker button[type=submit]').textContent"), "Add selected")

    def test_add_is_disabled_until_something_is_picked(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.show_picker(p)
                add = "document.querySelector('form.picker button[type=submit]')"
                self.assertEqual(p.js(add + ".disabled"), True)
                p.js("document.querySelector('form.picker tbody tr td:nth-child(3)').click()")
                p.until("!" + add + ".disabled", "Add is on once a row is ticked")

    def test_select_all_shown_is_disabled_with_no_rows(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.show_picker(p)
                btn = "[...document.querySelectorAll('form.picker .pk-search button')].find(b => b.textContent === 'Select all shown')"
                self.assertEqual(p.js(btn + ".disabled"), False)
                p.js("(() => { const i = document.querySelector('form.picker input[type=search]'); i.value = 'zzzz nothing'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
                p.until(ROWS + " === 0", "no rows match")
                self.assertEqual(p.js(btn + ".disabled"), True)

    def test_cancel_closes_the_picker_and_adds_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.show_picker(p)
                p.js("document.querySelector('form.picker tbody tr td:nth-child(3)').click()")
                p.until("document.querySelector('form.picker tbody input').checked", "a row ticked")
                self.click(p, "form.picker .pk-foot button:not([type=submit])")
                p.until("!" + Q, "Cancel closed the picker")
                self.assertEqual(self.row(self.uc3)["client_visible"], 0)
                self.assertEqual(self.row(self.uc4)["client_visible"], 0)


if __name__ == "__main__":
    unittest.main()
