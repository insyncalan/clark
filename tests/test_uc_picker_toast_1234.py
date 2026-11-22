"""Row 1234: the toast after the dashboard's use case picker adds use cases: "1 use case added to the page" / "N use cases added to the page".

The ticket names the toast ("N use case(s) added to the page"); no test read it. Widths 1400 and 900 px.

Run: python3 dev/run_tests.py test_uc_picker_toast_1234
Same harness and fictional data as test_glance_page (two use cases on the dashboard), plus three that are off it.
"""
import json

from _demo import USER
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

TOAST = "(document.querySelector('.toast .toast-text') || {}).textContent"


class PickerToast(Setup):
    seen = 0                                     # the store lasts for the whole file: each case adds its own, with refs not used before

    def off_page(self, n):
        with self.store.step("dashboard", USER) as st:
            for i in range(n):
                PickerToast.seen += 1
                st.create("use_cases", {"project": "ABC", "title": f"Off {PickerToast.seen}", "status": "On track", "ref": f"7.{PickerToast.seen}", "client_visible": 0, "source": "demo"})

    def on_page(self):
        return sum(r["client_visible"] for r in self.store.read("use_cases", "ABC"))

    def add(self, p, ticks):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('[data-uc-back]')", "Edit shows the add-from-record line")
        p.js("document.querySelector('[data-uc-back]').click()")
        p.until("!!document.querySelector('form.picker')", "the picker")
        for i in range(ticks):
            p.js("document.querySelectorAll('form.picker tbody input[type=checkbox]')[%d].click()" % i)
        p.js("document.querySelector('form.picker button[type=submit]').click()")
        p.until("!document.querySelector('form.picker')", "the picker closed")

    def test_the_toast_names_how_many_use_cases_were_added_singular_and_plural(self):
        for width in (1400, 900):
            for ticks, want in ((1, "1 use case added to the page"), (2, "2 use cases added to the page")):
                with self.subTest(width=width, ticks=ticks), chrome() as cdp:
                    self.off_page(3)
                    p = self.show(cdp, width)
                    before = self.on_page()
                    self.add(p, ticks)
                    p.until(TOAST + " === " + json.dumps(want), "the added toast")
                    self.assertEqual(self.on_page(), before + ticks, "their eyes are on")
