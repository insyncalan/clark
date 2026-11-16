"""Row 1234 (merged 1775): a search with no match leaves Select all shown and Add both disabled in the picker table.

Run: python3 dev/run_tests.py test_uc_picker_nomatch_kill_1775
Same page, store and data as test_uc_picker_table_kill_1234. Widths 1400 and 900 only.
"""
import json
import unittest

from _demo import USER
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

Q = "document.querySelector('form.picker')"
ROWS = "document.querySelectorAll('form.picker tbody tr').length"
ALL = "[...document.querySelectorAll('form.picker .pk-search button')].find(b => b.textContent === 'Select all shown')"
ADD = "document.querySelector('form.picker button[type=submit]')"


class Kill(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3,
                                    "headline": "No login for the smallest suppliers", "client_visible": 0, "source": "demo"})

    def picker(self, cdp, width):
        p = self.show(cdp, width)
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit shows the status buttons")
        sel = "[data-uc-back]"
        p.js(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(sel)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)
        p.until("!!" + Q, "the picker")
        return p

    def search(self, p, text):
        p.js("(() => { const i = document.querySelector('form.picker input[type=search]'); i.value = %s; i.dispatchEvent(new Event('input', {bubbles: true})); })()" % json.dumps(text))

    def test_no_match_disables_select_all_shown_and_add(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.picker(cdp, width)
                self.assertEqual(p.js(ALL + ".disabled"), False)
                self.search(p, "zzzz nothing")
                p.until(ROWS + " === 0", "no rows match")
                self.assertEqual(p.js(ALL + ".disabled"), True)
                self.assertEqual(p.js(ADD + ".disabled"), True)

    def test_a_match_brings_select_all_shown_back(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.picker(cdp, width)
                self.search(p, "zzzz nothing")
                p.until(ROWS + " === 0", "no rows match")
                self.search(p, "Supplier")
                p.until(ROWS + " === 1", "one row matches")
                self.assertEqual(p.js(ALL + ".disabled"), False)


if __name__ == "__main__":
    unittest.main()
