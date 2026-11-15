"""Row 1234: the add-a-use-case picker as a table with a filter panel (components/PickerTable.jsx, PickerFilters.jsx).

Run: python3 dev/run_tests.py test_uc_picker_table
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


class Table(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            self.uc3 = st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3,
                                               "headline": "No login for the smallest suppliers", "client_visible": 0, "source": "demo"})
            self.uc4 = st.create("use_cases", {"project": "ABC", "title": "Month end close", "status": "On track", "ref": "2.1", "sort_order": 4,
                                               "headline": "Done in two days", "client_visible": 0, "source": "demo"})

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

    def open(self, p):
        self.click(p, "[data-uc-back]")
        p.until("!!" + Q, "the picker")

    def pick_value(self, p, field, value):
        p.js("document.querySelector('.pkt-panel [data-field=%s]').click()" % field)
        p.js("document.querySelector('.pkt-panel input[value=\"%s\"]').click()" % value)

    def test_filters_result_badge_and_the_way_back(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.open(p)
                self.assertEqual(p.js(ROWS), 2)
                self.assertEqual(p.js(RESULT), "Result: 2 of 2 shown")
                self.assertEqual(p.js("document.querySelectorAll('form.picker thead th').length"), 9, "a tick column and the eight named")
                self.assertEqual(p.js("!!document.querySelector('[data-badge]')"), False, "no badge before a filter")
                self.assertEqual(p.js("document.activeElement === document.querySelector('form.picker input[type=search]')"), True, "focus in the search")
                self.assertEqual(p.js("document.querySelector('form.picker').getBoundingClientRect().right <= window.innerWidth"), True, "the picker fits the window")
                p.js("document.querySelector('[data-filter]').click()")
                p.until("!!document.querySelector('.pkt-panel')", "the panel")
                self.assertEqual(p.js("document.querySelector('[data-filter]').getAttribute('aria-expanded')"), "true")
                self.assertEqual(p.js("[...document.querySelectorAll('.pkt-field')].map(b => b.textContent).join()"), "Status,Commitment,Open steps,Work items")
                self.pick_value(p, "status", "High risk")
                p.until("document.querySelector('[data-badge]') && document.querySelector('[data-badge]').textContent === '1'", "the badge says 1")
                self.assertEqual(p.js(ROWS), 1)
                self.assertEqual(p.js(RESULT), "Result: 1 of 2 shown")
                p.js("document.querySelector('.pkt-panel [data-not=\"1\"]').click()")
                p.until(ROWS + " === 1 && document.querySelector('form.picker tbody tr').dataset.id === %r" % self.uc4, "is not any of keeps the other one")
                self.assertEqual(p.js("document.querySelector('.pkt-panel [data-not=\"1\"]').getAttribute('aria-pressed')"), "true")
                p.js("document.querySelector('.pkt-panel [data-none]').click()")
                p.until(ROWS + " === 2 && !document.querySelector('[data-badge]')", "Clear drops the filter")
                p.js("document.querySelector('.pkt-panel [data-all]').click()")
                p.until(RESULT + " === 'Result: 2 of 2 shown' && document.querySelector('[data-badge]').textContent === '1'", "Select all on Status keeps both and counts one filter")
                # Esc closes the panel only, and focus goes back to the icon
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('.pkt-panel')", "Esc closed the panel")
                self.assertEqual(p.js("!!" + Q), True, "the picker stays")
                self.assertEqual(p.js("document.activeElement === document.querySelector('[data-filter]')"), True, "focus is back on the icon")
                # Done does the same
                p.js("document.querySelector('[data-filter]').click()")
                p.until("!!document.querySelector('.pkt-panel')", "the panel again")
                p.js("document.querySelector('.pkt-panel [data-done]').click()")
                p.until("!document.querySelector('.pkt-panel')", "Done closed the panel")
                self.assertEqual(p.js("document.activeElement === document.querySelector('[data-filter]')"), True, "focus is back on the icon after Done")
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")

    def test_search_by_status_and_add_still_saves_the_pick(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.open(p)
            p.js("(() => { const i = document.querySelector('form.picker input[type=search]'); i.value = 'high risk'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
            p.until(ROWS + " === 1", "search by status")
            p.js("document.querySelector('form.picker tbody tr td:nth-child(3)').click()")        # a click on the row ticks it
            p.until("document.querySelector('form.picker tbody input').checked", "the row ticked")
            p.js("document.querySelector('form.picker button[type=submit]').click()")
            p.until("!" + Q, "the picker closed")
            p.saved()
            self.assertEqual(self.row(self.uc3)["client_visible"], 1)
            self.assertEqual(self.row(self.uc4)["client_visible"], 0)


if __name__ == "__main__":
    unittest.main()
